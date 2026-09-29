"""
Step 4: build data/dataset_v1.csv (one row per token_id x date) and data/data_dictionary_v1.csv
from the raw pulls under data/raw/. Pure local computation; no API calls.

Conventions (verified against the raw data on 2026-09-14):
- emission row with startDate D covers [D, D+1). totalCumulativeUnlockedAmount on row D already
  includes D's unlockAmount (SUI 2024-10-01 cliff shows in the 2024-10-01 row) -> it is an
  end-of-day-D quantity, i.e. known at the Binance daily close of D.
- Feature "at date D" uses information up to and including the close of D.
  Forward windows are D+1 .. D+k. Backward windows are D-k+1 .. D.
- Realized vol: sqrt(365/n * sum(r^2)) over the n daily log returns, no mean subtraction.
- Parkinson: sqrt(365/(4 n ln2) * sum(ln(H/L)^2)).
- No shuffling, no winsorizing, no imputation.
"""
import json, os, math, csv
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
TODAY = pd.Timestamp("2026-09-14")
FWD_END = pd.Timestamp("2027-06-29")   # last emission day the plan serves; schedules that end earlier are extended with zeros
ANN = 365.0
STD_BUCKETS = {"Founder / Team": "founderTeam", "Private Investors": "privateInvestors", "Community": "community",
               "Public Investors": "publicInvestors", "Reserve": "reserve", "Others": "others"}


def rv(r, n):
    """Annualized RV of a window of n log returns; NaN unless all n present."""
    s = r.rolling(n, min_periods=n).apply(lambda x: math.sqrt(ANN / n * float(np.sum(x * x))), raw=True)
    return s


def load_prices(path):
    p = pd.read_csv(path, parse_dates=["date"]).sort_values("date").set_index("date")
    p = p[~p.index.duplicated()]
    return p


def price_features(p, prefix=""):
    """Backward-looking (up to close D) and forward-looking (D+1..D+k) price features."""
    out = pd.DataFrame(index=p.index)
    r = np.log(p["close"]).diff()               # r_t = ln(C_t / C_{t-1}), defined for t>=2
    hl2 = np.log(p["high"] / p["low"]) ** 2
    for k in (7, 14, 30):
        past = rv(r, k)                          # window D-k+1..D  (uses closes D-k..D)
        out[f"{prefix}rv_past_{k}d"] = past
        # forward window D+1..D+k: shift the trailing window ending at D+k back by k
        out[f"{prefix}rv_fwd_{k}d"] = past.shift(-k)
    park = hl2.rolling(14, min_periods=14).apply(lambda x: math.sqrt(ANN / (4 * 14 * math.log(2)) * float(np.sum(x))), raw=True)
    out[f"{prefix}rv_fwd_14d_parkinson"] = park.shift(-14)
    lc = np.log(p["close"])
    out[f"{prefix}fwd_ret_14d"] = lc.shift(-14) - lc
    out[f"{prefix}ret_past_7d"] = lc - lc.shift(7)
    out[f"{prefix}ret_past_30d"] = lc - lc.shift(30)
    out[f"{prefix}close"] = p["close"]
    return out


def build_token(tid, urow, btc, eth):
    d = os.path.join(RAW, tid)
    emis = json.load(open(f"{d}/emission_daily.json"))
    alloc = json.load(open(f"{d}/allocations.json"))
    events = json.load(open(f"{d}/unlock_events.json")) or []
    if not isinstance(alloc, dict) or "allocations" not in alloc:
        alloc = {"maxSupply": None, "allocations": []}
    prices = load_prices(f"{d}/prices.csv")

    # ---- emission daily table -------------------------------------------------
    rows = []
    for r in emis:
        row = {"date": pd.Timestamp(r["startDate"][:10]), "unlock_amount": r["unlockAmount"],
               "cum_unlocked": r["totalCumulativeUnlockedAmount"], "ref_price": r.get("referencePrice")}
        for b in STD_BUCKETS.values():
            row[f"ua_{b}"] = 0.0
        attributed = 0.0
        for a in r["allocations"]:
            b = STD_BUCKETS.get(a["standardAllocationName"], "others")
            row[f"ua_{b}"] += a["unlockAmount"]
            attributed += a["unlockAmount"]
        resid = r["unlockAmount"] - attributed
        # floating-point residue of the bucket sum is not real unattributed emission
        row["ua_unattributed"] = 0.0 if abs(resid) <= 1e-9 * max(1.0, abs(r["unlockAmount"])) else resid
        rows.append(row)
    em = pd.DataFrame(rows).sort_values("date").drop_duplicates("date").set_index("date")
    full_idx = pd.date_range(em.index.min(), em.index.max(), freq="D")
    n_missing_days = len(full_idx) - len(em)
    em = em.reindex(full_idx)  # gaps -> NaN (none observed, but keep explicit)
    # A schedule that ends before the plan's forward limit means Tokenomist knows of no further scheduled
    # unlocks: extend with zero-unlock rows so emis_next_* is 0 (not NaN) and float_pit carries forward.
    last_sched = em.index.max()
    if last_sched < FWD_END:
        ext = pd.date_range(last_sched + pd.Timedelta(days=1), FWD_END, freq="D")
        em = em.reindex(em.index.append(ext))
        zero_cols = ["unlock_amount", "ua_unattributed"] + [f"ua_{b}" for b in STD_BUCKETS.values()]
        em.loc[ext, zero_cols] = 0.0
        em["cum_unlocked"] = em["cum_unlocked"].ffill()
    em.index.name = "date"

    # forward emission sums over D+1..D+k: trailing rolling sum ending at D+k, shifted back by k
    feats = pd.DataFrame(index=em.index)
    feats["float_pit"] = em["cum_unlocked"]
    for k in (7, 30, 90):
        feats[f"emis_next_{k}d"] = em["unlock_amount"].rolling(k, min_periods=k).sum().shift(-k)
    for b in STD_BUCKETS.values():
        feats[f"emis_next_30d_{b}"] = em[f"ua_{b}"].rolling(30, min_periods=30).sum().shift(-30)
    feats["emis_next_30d_unattributed"] = em["ua_unattributed"].rolling(30, min_periods=30).sum().shift(-30)

    total_supply = alloc.get("maxSupply")
    tracked_total = sum(a["allocationAmount"] for a in alloc["allocations"])
    supply_basis = "maxSupply"
    if total_supply is None or total_supply <= 0:
        total_supply = tracked_total
        supply_basis = "sum_allocationAmount (maxSupply null)"
    for k in (7, 30, 90):
        feats[f"emis_next_{k}d_pct_float"] = feats[f"emis_next_{k}d"] / feats["float_pit"].replace(0, np.nan)
    feats["emis_next_30d_pct_total"] = feats["emis_next_30d"] / total_supply

    # ---- cliff events (unlock events endpoint) ---------------------------------
    ev = []
    precisions = []
    for e in events:
        ev.append({"unlock_ts": pd.Timestamp(e["unlockDate"]).tz_convert(None), "cliff_amount": e["cliffAmount"]})
        for b in e["cliffUnlocks"]["allocationBreakdown"]:
            precisions.append(b.get("unlockPrecision"))
    ev = pd.DataFrame(ev).sort_values("unlock_ts") if ev else pd.DataFrame(columns=["unlock_ts", "cliff_amount"])
    has_events = len(ev) > 0
    unlock_precision_mode = pd.Series(precisions).mode().iloc[0] if precisions else None

    dnc, npf = [], []
    ev_dates = ev["unlock_ts"].dt.normalize().values if has_events else np.array([], dtype="datetime64[ns]")
    ev_amt = ev["cliff_amount"].values if has_events else np.array([])
    for D in feats.index:
        if has_events:
            m = ev_dates > np.datetime64(D)          # strictly after D (an unlock dated D has occurred by close D)
            if m.any():
                i = np.argmax(m)                       # first True (sorted ascending)
                days = (pd.Timestamp(ev_dates[i]) - D).days
                dnc.append(days)
                f = feats.at[D, "float_pit"]
                npf.append(ev_amt[i] / f if f and f > 0 else np.nan)
                continue
        dnc.append(np.nan); npf.append(np.nan)
    feats["days_to_next_cliff"] = dnc
    feats["next_cliff_pct_float"] = npf
    feats["has_unlock_events"] = has_events
    feats["emission_schedule_ended"] = feats.index > last_sched

    # ---- static token features -------------------------------------------------
    share = {b: 0.0 for b in STD_BUCKETS.values()}
    for a in alloc["allocations"]:
        share[STD_BUCKETS.get(a["standardAllocationName"], "others")] += a["allocationAmount"]
    for b, v in share.items():
        feats[f"alloc_share_{b}"] = v / tracked_total if tracked_total else np.nan
    feats["listedMethod"] = urow["listedMethod"]
    feats["unlockPrecision"] = unlock_precision_mode
    feats["total_supply"] = total_supply
    feats["total_supply_basis"] = supply_basis
    tge_proxy = min(pd.Timestamp(urow["binance_listing_date"]), em.index.min())
    feats["tge_proxy_date"] = tge_proxy.date().isoformat()
    feats["days_since_tge"] = (feats.index - tge_proxy).days

    # ---- prices ----------------------------------------------------------------
    pf = price_features(prices)
    df = feats.join(pf, how="inner")               # rows need both emission and price data
    df = df.join(btc[["rv_past_14d"]].rename(columns={"rv_past_14d": "btc_rv_past_14d"}), how="left")
    df = df.join(eth[["rv_past_14d"]].rename(columns={"rv_past_14d": "eth_rv_past_14d"}), how="left")
    df["log_mcap_pit"] = np.log(df["float_pit"].replace(0, np.nan) * df["close"])
    df = df[df.index <= TODAY]

    n_before = len(df)
    df = df[df["rv_fwd_30d"].notna()]              # target not computable (last 30 days)
    n_after_target = len(df)
    df = df[df["float_pit"].notna() & (df["float_pit"] > 0)]
    n_after_float = len(df)

    df.insert(0, "token_id", tid)
    df.insert(1, "symbol", urow["symbol"])
    df = df.reset_index().rename(columns={"index": "date"})
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    meta = {"token_id": tid, "emission_missing_days": n_missing_days, "rows_with_price_and_emission": n_before,
            "dropped_target_na": n_before - n_after_target, "dropped_float_zero": n_after_target - n_after_float,
            "rows_final": n_after_float, "has_unlock_events": has_events, "n_unlock_events": len(ev),
            "total_supply_basis": supply_basis}
    return df, meta


COLS = ["token_id", "symbol", "date",
        "rv_fwd_7d", "rv_fwd_14d", "rv_fwd_30d", "rv_fwd_14d_parkinson", "fwd_ret_14d",
        "emis_next_7d", "emis_next_30d", "emis_next_90d", "float_pit",
        "emis_next_7d_pct_float", "emis_next_30d_pct_float", "emis_next_90d_pct_float", "emis_next_30d_pct_total",
        "days_to_next_cliff", "next_cliff_pct_float", "has_unlock_events", "emission_schedule_ended",
        "emis_next_30d_founderTeam", "emis_next_30d_privateInvestors", "emis_next_30d_community",
        "emis_next_30d_publicInvestors", "emis_next_30d_reserve", "emis_next_30d_others", "emis_next_30d_unattributed",
        "rv_past_7d", "rv_past_14d", "rv_past_30d", "ret_past_7d", "ret_past_30d",
        "btc_rv_past_14d", "eth_rv_past_14d", "log_mcap_pit",
        "days_since_tge", "listedMethod", "unlockPrecision",
        "alloc_share_founderTeam", "alloc_share_privateInvestors", "alloc_share_community",
        "alloc_share_publicInvestors", "alloc_share_reserve", "alloc_share_others",
        "total_supply", "total_supply_basis", "tge_proxy_date"]


DICT = [
    # column, type, unit, source/derivation, lookahead_safe, reason
    ("token_id", "string", "-", "Tokenomist token list `id`", "yes", "identifier"),
    ("symbol", "string", "-", "Tokenomist token list `symbol`", "yes", "identifier"),
    ("date", "date (ISO, UTC)", "day", "panel date D; features use info through Binance close of D", "yes", "index"),
    ("rv_fwd_7d", "float", "annualized vol (decimal)", "sqrt(365/7 * sum r^2), r = daily close-to-close log return over D+1..D+7 (Binance klines)", "no", "TARGET: uses closes after D"),
    ("rv_fwd_14d", "float", "annualized vol (decimal)", "same, D+1..D+14", "no", "TARGET: uses closes after D"),
    ("rv_fwd_30d", "float", "annualized vol (decimal)", "same, D+1..D+30", "no", "TARGET: uses closes after D"),
    ("rv_fwd_14d_parkinson", "float", "annualized vol (decimal)", "sqrt(365/(4*14*ln2) * sum ln(H/L)^2) over D+1..D+14 (Binance daily high/low)", "no", "TARGET: uses H/L after D"),
    ("fwd_ret_14d", "float", "log return", "ln(close[D+14]/close[D])", "no", "TARGET: uses close after D"),
    ("emis_next_7d", "float", "tokens", "sum of emission daily `unlockAmount` for startDate in D+1..D+7", "yes", "schedule as curated today; forward window starts D+1 (see caveat: schedule revisions not versioned)"),
    ("emis_next_30d", "float", "tokens", "sum of `unlockAmount`, D+1..D+30", "yes", "as above"),
    ("emis_next_90d", "float", "tokens", "sum of `unlockAmount`, D+1..D+90", "yes", "as above"),
    ("float_pit", "float", "tokens", "emission daily `totalCumulativeUnlockedAmount` on row D (end-of-day D, verified inclusive of D's unlock)", "yes", "cumulative through D only"),
    ("emis_next_7d_pct_float", "float", "ratio (0-1)", "emis_next_7d / float_pit", "yes", "both components at D"),
    ("emis_next_30d_pct_float", "float", "ratio (0-1)", "emis_next_30d / float_pit", "yes", "both components at D"),
    ("emis_next_90d_pct_float", "float", "ratio (0-1)", "emis_next_90d / float_pit", "yes", "both components at D"),
    ("emis_next_30d_pct_total", "float", "ratio (0-1)", "emis_next_30d / total_supply", "yes", "denominator is static"),
    ("days_to_next_cliff", "float", "days", "min(unlockDate - D) over unlock events with unlockDate > D (unlock events endpoint, cliff events)", "yes", "next scheduled event after D; NaN if no future event or token has no events"),
    ("next_cliff_pct_float", "float", "ratio (0-1)", "cliffAmount of that next event / float_pit", "yes", "as above"),
    ("has_unlock_events", "bool", "-", "unlock events endpoint returned >=1 event in 2024-09-14..2027-06-30", "yes", "static flag"),
    ("emission_schedule_ended", "bool", "-", "True when D is after the last row Tokenomist returned for the token emission schedule; emis_next_* are then 0 by construction (no scheduled unlocks known) and float_pit is carried forward", "yes", "derived from schedule end date"),
    ("emis_next_30d_founderTeam", "float", "tokens", "emis_next_30d restricted to allocations[].standardAllocationName == 'Founder / Team'", "yes", "same window as emis_next_30d"),
    ("emis_next_30d_privateInvestors", "float", "tokens", "... == 'Private Investors'", "yes", "same"),
    ("emis_next_30d_community", "float", "tokens", "... == 'Community'", "yes", "same"),
    ("emis_next_30d_publicInvestors", "float", "tokens", "... == 'Public Investors'", "yes", "same"),
    ("emis_next_30d_reserve", "float", "tokens", "... == 'Reserve'", "yes", "same"),
    ("emis_next_30d_others", "float", "tokens", "... == 'Others' or any unmapped label", "yes", "same"),
    ("emis_next_30d_unattributed", "float", "tokens", "emis_next_30d minus the sum of the six buckets (row-level unlockAmount not covered by allocations[])", "yes", "same"),
    ("rv_past_7d", "float", "annualized vol (decimal)", "sqrt(365/7 * sum r^2) over D-6..D", "yes", "closes D-7..D only"),
    ("rv_past_14d", "float", "annualized vol (decimal)", "same, D-13..D", "yes", "closes through D"),
    ("rv_past_30d", "float", "annualized vol (decimal)", "same, D-29..D", "yes", "closes through D"),
    ("ret_past_7d", "float", "log return", "ln(close[D]/close[D-7])", "yes", "closes through D"),
    ("ret_past_30d", "float", "log return", "ln(close[D]/close[D-30])", "yes", "closes through D"),
    ("btc_rv_past_14d", "float", "annualized vol (decimal)", "rv_past_14d of BTCUSDT", "yes", "closes through D"),
    ("eth_rv_past_14d", "float", "annualized vol (decimal)", "rv_past_14d of ETHUSDT", "yes", "closes through D"),
    ("log_mcap_pit", "float", "ln(USDT)", "ln(float_pit * close[D])", "yes", "both at D"),
    ("days_since_tge", "int", "days", "D - tge_proxy_date", "yes", "static date"),
    ("listedMethod", "string", "-", "Tokenomist token list `listedMethod` (INTERNAL/AI/EXTERNAL)", "yes", "static; note it is a current curation flag, not historical"),
    ("unlockPrecision", "string", "-", "mode of unlock events allocationBreakdown[].unlockPrecision; NaN when no events", "yes", "static"),
    ("alloc_share_founderTeam", "float", "ratio (0-1)", "allocation detail: sum allocationAmount for 'Founder / Team' / sum of all allocationAmount", "yes*", "static snapshot as of pull date (allocation detail has no history); treated as time-invariant"),
    ("alloc_share_privateInvestors", "float", "ratio (0-1)", "same for 'Private Investors'", "yes*", "same caveat"),
    ("alloc_share_community", "float", "ratio (0-1)", "same for 'Community'", "yes*", "same caveat"),
    ("alloc_share_publicInvestors", "float", "ratio (0-1)", "same for 'Public Investors'", "yes*", "same caveat"),
    ("alloc_share_reserve", "float", "ratio (0-1)", "same for 'Reserve'", "yes*", "same caveat"),
    ("alloc_share_others", "float", "ratio (0-1)", "same for 'Others' / unmapped", "yes*", "same caveat"),
    ("total_supply", "float", "tokens", "allocation detail `maxSupply`, else sum of allocationAmount (see total_supply_basis)", "yes*", "static snapshot"),
    ("total_supply_basis", "string", "-", "which denominator was used for total_supply", "yes", "metadata"),
    ("tge_proxy_date", "date", "day", "min(Binance first daily candle, first emission row). Lower bound on age for tokens older than their Binance listing", "yes", "static"),
]


def main():
    uni = pd.read_csv(os.path.join(DATA, "universe.csv"))
    btc = price_features(load_prices(os.path.join(RAW, "BTCUSDT_prices.csv")))
    eth = price_features(load_prices(os.path.join(RAW, "ETHUSDT_prices.csv")))
    frames, metas = [], []
    for _, u in uni.iterrows():
        df, meta = build_token(u["token_id"], u, btc, eth)
        frames.append(df); metas.append(meta)
        print(f"{u['token_id']:26s} rows={meta['rows_final']} (dropped target={meta['dropped_target_na']}, float0={meta['dropped_float_zero']}) events={meta['n_unlock_events']}", flush=True)
    ds = pd.concat(frames, ignore_index=True)[COLS]
    ds = ds.sort_values(["token_id", "date"]).reset_index(drop=True)   # deterministic order, no shuffling
    ds.to_csv(os.environ.get("DATASET_PATH", os.path.join(DATA, "dataset_v1.csv")), index=False)
    pd.DataFrame(metas).to_csv(os.path.join(DATA, "build_meta.csv"), index=False)
    with open(os.path.join(DATA, "data_dictionary_v1.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["column", "type", "unit", "source_endpoint_or_derivation", "lookahead_safe", "reason"])
        for row in DICT:
            w.writerow(row)
    assert set(ds.columns) == {d[0] for d in DICT}, set(ds.columns) ^ {d[0] for d in DICT}
    print(f"dataset_v1.csv: {ds.shape[0]} rows x {ds.shape[1]} cols", flush=True)


if __name__ == "__main__":
    main()
