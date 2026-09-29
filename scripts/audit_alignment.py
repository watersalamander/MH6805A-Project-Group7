"""
Audit of date alignment between Tokenomist (emission / unlock events) and Binance (klines)
in data/dataset_v1.csv. Read-only; no API calls. Prints a PASS/FAIL line per check.
"""
import json, os, math, collections
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data"); RAW = os.path.join(DATA, "raw")
ds = pd.read_csv(os.environ.get("DATASET_PATH", os.path.join(DATA, "dataset_v1.csv")))
uni = pd.read_csv(os.path.join(DATA, "universe.csv"))
ds["date"] = pd.to_datetime(ds["date"])
rng = np.random.default_rng(0)   # only used to pick rows to re-verify; nothing is shuffled in the dataset


def line(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


# ------------------------------------------------------------------ 1. timestamp conventions
bad_start = collections.Counter(); bad_len = 0; n_rows = 0; gaps_em = 0; dup_em = 0
for tid in uni.token_id:
    em = json.load(open(f"{RAW}/{tid}/emission_daily.json"))
    ds_ = []
    for r in em:
        n_rows += 1
        if not r["startDate"].endswith("T00:00:00Z"):
            bad_start[r["startDate"][10:]] += 1
        if (pd.Timestamp(r["endDate"]) - pd.Timestamp(r["startDate"])) != pd.Timedelta(days=1):
            bad_len += 1
        ds_.append(r["startDate"][:10])
    s = pd.to_datetime(pd.Series(ds_))
    dup_em += int(s.duplicated().sum())
    gaps_em += int((s.sort_values().diff().dt.days.dropna() != 1).sum())
line("1a emission startDate is always 00:00:00Z", not bad_start, f"{n_rows} rows, offenders {dict(bad_start)}")
line("1b emission bucket is always exactly 1 day", bad_len == 0, f"{bad_len} offenders")
line("1c emission series have no duplicate or missing calendar days", dup_em == 0 and gaps_em == 0, f"dups={dup_em} gaps={gaps_em}")

# ------------------------------------------------------------------ 2. Binance calendar continuity
gap_tokens = {}
prices = {}
for tid in list(uni.token_id) + ["BTCUSDT", "ETHUSDT"]:
    path = f"{RAW}/{tid}_prices.csv" if tid.endswith("USDT") else f"{RAW}/{tid}/prices.csv"
    p = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    prices[tid] = p.set_index("date")
    p = p.reset_index(drop=True)
    d = p["date"].diff().dt.days.dropna()
    allg = [(str(p.loc[i - 1, "date"].date()), str(p.loc[i, "date"].date())) for i in d.index[d != 1]]
    if allg:
        gap_tokens[tid] = allg
WINDOW_START = "2024-08-01"   # earliest close any panel feature can touch (2024-09-14 minus 30 days, with margin)
in_window = {t: [g for g in gs if g[1] >= WINDOW_START] for t, gs in gap_tokens.items()}
in_window = {t: g for t, g in in_window.items() if g}
print(f"   (info) gaps anywhere in price history: {gap_tokens}")
line("2a Binance daily klines have no missing days from 2024-08-01 on (row windows == calendar windows)", not in_window,
     f"{in_window}")
zero_vol = {t: int((p["volume"] == 0).sum()) for t, p in prices.items() if (p["volume"] == 0).any()}
line("2b no zero-volume (halted) candles inside the panel window", not zero_vol, f"{zero_vol}")

# ------------------------------------------------------------------ 3. independent price cross-check
# Tokenomist emission rows carry their own daily referencePrice. Compare with Binance close at lags.
res = []
for tid in uni.token_id:
    em = json.load(open(f"{RAW}/{tid}/emission_daily.json"))
    ref = pd.Series({pd.Timestamp(r["startDate"][:10]): r.get("referencePrice") for r in em}, dtype=float).dropna()
    ref = ref[ref > 0]
    p = prices[tid]
    row = {"token_id": tid}
    for name, series in (("close", p["close"]), ("open", p["open"])):
        for lag in (-1, 0, 1):
            b = series.copy(); b.index = b.index + pd.Timedelta(days=lag)   # lag=+1: Binance value of D-1 placed on D
            j = pd.concat([ref, b], axis=1, join="inner").dropna()
            j = j[j.index <= pd.Timestamp("2026-09-13")]
            row[f"{name}_lag{lag:+d}"] = float(np.median(np.abs(np.log(j.iloc[:, 0] / j.iloc[:, 1])))) if len(j) > 30 else np.nan
            row["n"] = len(j)
    res.append(row)
x = pd.DataFrame(res).set_index("token_id")
cols = [c for c in x.columns if c != "n"]
nodata = x[x[cols].isna().all(axis=1)].index.tolist()
print("   tokens with no usable referencePrice overlap:", nodata)
x = x.drop(index=nodata)
best = x[cols].idxmin(axis=1)
print("\n3. Tokenomist referencePrice(D) vs Binance price: median |log ratio| across tokens (smaller = better match)")
print(x[cols].median().round(4).to_string())
print("   best-matching Binance series per token:", best.value_counts().to_dict())
wrong_asset = x[x[cols].min(axis=1) > 0.10]
line("3a every token's Binance series matches Tokenomist's own price (no symbol collision)", len(wrong_asset) == 0,
     f"{len(wrong_asset)} tokens with best median |log ratio| > 10%: {wrong_asset[cols].min(axis=1).round(3).to_dict()}")

# ------------------------------------------------------------------ 4. cliff event date vs emission spike date
hit = miss = 0; off = collections.Counter(); miss_ex = []
for tid in uni.token_id:
    ev = json.load(open(f"{RAW}/{tid}/unlock_events.json"))
    em = {r["startDate"][:10]: r["unlockAmount"] for r in json.load(open(f"{RAW}/{tid}/emission_daily.json"))}
    for e in ev:
        d = pd.Timestamp(e["unlockDate"]).tz_convert(None).normalize(); amt = e["cliffAmount"]
        if amt <= 0: continue
        found = None
        for k in (0, -1, 1, -2, 2):
            v = em.get((d + pd.Timedelta(days=k)).strftime("%Y-%m-%d"))
            if v is not None and v >= amt * 0.999:
                found = k; break
        if found is None:
            miss += 1
            if len(miss_ex) < 5: miss_ex.append((tid, e["unlockDate"], amt, em.get(d.strftime("%Y-%m-%d"))))
        else:
            hit += 1; off[found] += 1
print(f"\n4. cliff events located in emission series by day offset (0 = same UTC date): {dict(off)}, not found: {miss}")
line("4a cliff events land on the same UTC date in the emission series", off.get(0, 0) >= 0.99 * max(hit, 1),
     f"{off.get(0, 0)}/{hit} at offset 0; unmatched examples {miss_ex}")

# ------------------------------------------------------------------ 5. recompute features by calendar lookup
def rv(closes, dates, n):
    r = [math.log(closes[d] / closes[d - pd.Timedelta(days=1)]) for d in dates]
    return math.sqrt(365 / n * sum(v * v for v in r))

checks = collections.Counter(); fails = []
sample = pd.concat([g.iloc[rng.choice(len(g), size=min(5, len(g)), replace=False)] for _, g in ds.groupby("token_id")])
em_cache = {}
for _, r in sample.iterrows():
    tid, D = r["token_id"], r["date"]
    if tid not in em_cache:
        e = json.load(open(f"{RAW}/{tid}/emission_daily.json"))
        em_cache[tid] = ({pd.Timestamp(q["startDate"][:10]): q["unlockAmount"] for q in e},
                         {pd.Timestamp(q["startDate"][:10]): q["totalCumulativeUnlockedAmount"] for q in e})
    ua, cum = em_cache[tid]; c = prices[tid]["close"]; h = prices[tid]["high"]; l = prices[tid]["low"]
    day = lambda k: D + pd.Timedelta(days=k)
    last = max(ua)
    exp = {}
    exp["emis_next_7d"] = sum(ua.get(day(k), 0.0) for k in range(1, 8))
    exp["emis_next_30d"] = sum(ua.get(day(k), 0.0) for k in range(1, 31))
    exp["emis_next_90d"] = sum(ua.get(day(k), 0.0) for k in range(1, 91))
    exp["float_pit"] = cum[D] if D in cum else cum[last]
    exp["rv_fwd_14d"] = rv(c, [day(k) for k in range(1, 15)], 14)
    exp["rv_fwd_30d"] = rv(c, [day(k) for k in range(1, 31)], 30)
    exp["fwd_ret_14d"] = math.log(c[day(14)] / c[D])
    exp["rv_fwd_14d_parkinson"] = math.sqrt(365 / (4 * 14 * math.log(2)) * sum(math.log(h[day(k)] / l[day(k)]) ** 2 for k in range(1, 15)))
    if not pd.isna(r["rv_past_14d"]):
        exp["rv_past_14d"] = rv(c, [day(-k) for k in range(0, 14)], 14)
    if not pd.isna(r["ret_past_30d"]):
        exp["ret_past_30d"] = math.log(c[D] / c[day(-30)])
    exp["btc_rv_past_14d"] = rv(prices["BTCUSDT"]["close"], [day(-k) for k in range(0, 14)], 14)
    exp["eth_rv_past_14d"] = rv(prices["ETHUSDT"]["close"], [day(-k) for k in range(0, 14)], 14)
    exp["log_mcap_pit"] = math.log(exp["float_pit"] * c[D])
    for k, v in exp.items():
        got = r[k]
        ok = abs(got - v) <= 1e-9 * max(1.0, abs(v))
        checks[k, ok] += 1
        if not ok and len(fails) < 10:
            fails.append((tid, str(D.date()), k, got, v))
print(f"\n5. independent recomputation on {len(sample)} rows ({sample.token_id.nunique()} tokens, 5 dates each), by calendar-date lookup:")
for k in sorted({a for a, _ in checks}):
    print(f"   {k:24s} match {checks[k, True]:4d}  mismatch {checks[k, False]:4d}")
line("5a every recomputed value equals the dataset value", not fails, f"first mismatches: {fails}")

# ------------------------------------------------------------------ 6. panel-level structure
d = ds.groupby("token_id")["date"].apply(lambda s: int((s.sort_values().diff().dt.days.dropna() != 1).sum()))
line("6a each token's panel dates are consecutive calendar days", int(d.sum()) == 0, f"{int((d > 0).sum())} tokens with breaks: {d[d > 0].to_dict()}")
line("6b (token_id, date) is unique", not ds.duplicated(["token_id", "date"]).any())
first = ds.groupby("token_id")["date"].min()
lst = pd.to_datetime(uni.set_index("token_id")["binance_listing_date"])
early = first[first < lst.reindex(first.index)]
line("6c no panel row precedes the token's first Binance candle", len(early) == 0, f"{early.to_dict()}")
line("6d last panel date is 30 days before the last price date for every token", (ds.groupby("token_id")["date"].max() == pd.Timestamp("2026-08-15")).all(),
     f"{ds.groupby('token_id')['date'].max().value_counts().to_dict()}")
