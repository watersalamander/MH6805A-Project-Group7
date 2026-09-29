"""
Step 5: write data/FEASIBILITY_REPORT.md from dataset_v1.csv, universe files, call log and raw JSON.
No API calls.
"""
import json, os, re, collections
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
SAMPLES = os.path.join(ROOT, "samples", "raw")
FEAT = "emis_next_30d_pct_float"
TGT = "rv_fwd_14d"


def md_table(df, floatfmt="{:.4g}"):
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                cells.append("NaN" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def keyset(obj, prefix=""):
    """Flatten JSON key paths (arrays profiled element-wise)."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(prefix + k)
            out |= keyset(v, prefix + k + ".")
    elif isinstance(obj, list):
        for x in obj[:50]:
            out |= keyset(x, prefix + "[].")
    return out


def main():
    ds = pd.read_csv(os.environ.get("DATASET_PATH", os.path.join(DATA, "dataset_v1.csv")))
    uni = pd.read_csv(os.path.join(DATA, "universe.csv"))
    exc = pd.read_csv(os.path.join(DATA, "universe_exclusions.csv"))
    meta = pd.read_csv(os.path.join(DATA, "build_meta.csv"))
    log = [l for l in open(os.path.join(DATA, "call_log.txt"), encoding="utf-8") if not l.startswith("#") and l.strip()]
    ok = [l for l in log if "| exit=0 |" in l]
    failed = [l for l in log if "| exit=0 |" not in l]
    by_ep = collections.Counter(l.split("|")[3].strip() for l in ok)
    tokens_list = json.load(open(os.path.join(RAW, "token_list.json")))

    L = []
    A = L.append
    A("# Feasibility report: forward realized volatility vs scheduled token emissions (dataset_v1)")
    A("")
    A("Generated 2026-09-14 from `scripts/tok_pull.py` -> `scripts/build_dataset.py` -> `scripts/make_report.py`. "
      "Raw API dumps live only under `data/raw/` (git-ignored); `data/dataset_v1.csv` contains engineered features only.")
    A("")
    A("## 0. Run assumptions (read first)")
    A("")
    A("- **Budget**: two passes. Pass 1 (placeholders in the brief) used a self-imposed 40-call ceiling and 12 tokens. Pass 2, after the budget was confirmed as 5M calls/month at 120/min, "
      "pulled every token that passes the free filters, paced at <= 100 calls/min. `scripts/tok_pull.py` is idempotent (`--budget`, `--max-tokens`, `--probe-all`, `--include-fully-unlocked`).")
    A("- **Plan history window discovered from an API error**: emission data is only served for **2024-09-14 to 2027-06-30** (exactly 2 years back from today). "
      "Requests starting earlier are rejected (`Invalid Date Range`). All per-token pulls therefore use `--start 2024-09-14 --end 2027-06-30`.")
    A("- **TGE proxy**: the token list has no TGE/launch date field. The 180-day age filter uses the Binance first daily candle (free); `tge_proxy_date` = min(Binance listing, first emission row). "
      "For coins older than their Binance listing (LTC, DOGE, ZEC, ATOM ...) `days_since_tge` is a lower bound.")
    A("- **Universe filter**: Binance USDT spot pair (exact `SYMBOL+USDT`, status TRADING), Binance listing >= 180 days before today, and Daily Emission non-empty on the spent call. "
      "Fully-unlocked tokens (`totalLockedAmount == 0`) were included in pass 2 so the panel also contains no-forward-unlock observations. "
      "A free symbol-collision guard (Binance last price vs token-list marketCap/circulatingSupply, factor 3) excludes tokens whose Binance ticker is a different asset.")
    A("- **Centrifuge was removed after the alignment audit**: Tokenomist's entry is 'Centrifuge [OLD]' while Binance CFGUSDT is the migrated token, so price and supply described different assets.")
    A("- **BTC and ETH were excluded from the target universe** because they are the market-vol controls (`btc_rv_past_14d`, `eth_rv_past_14d`).")
    A("- The universe is now *every* eligible token, not a market-cap top-M. It therefore mixes PoW/PoS issuance coins (smooth block/staking emission: SOL, ZEC, DOGE, LTC, ATOM ...) with VC-vesting tokens that have real cliffs. Section 4 separates them; use `has_unlock_events` and the per-token step counts to subset at modelling time.")
    A("- Schedules that end before 2027-06-29 are extended with zero-unlock days (`emission_schedule_ended` flag) so `emis_next_*` is 0 rather than NaN once Tokenomist knows of no further scheduled unlocks.")
    A("")

    # ---------------- 1. Universe
    A("## 1. Universe")
    A("")
    n_all = len(tokens_list)
    A(f"- Tokens in Tokenomist registry (token list): **{n_all}**")
    zero_row = meta.loc[meta["rows_final"] == 0, "token_id"].tolist()
    A(f"- Selected (all 3 endpoints pulled): **{len(uni)}**. Excluded: **{len(exc)}**. Tokens pulled but contributing 0 panel rows (no overlap between emission dates <= today-30d and Binance price history): **{len(zero_row)}** ({', '.join(zero_row) or 'none'}).")
    A("")
    reasons = exc["reason"].str.replace(r"too_young_binance_listing_.*", "too_young_binance_listing_<date>", regex=True).value_counts()
    A("Exclusion reasons (count):")
    A("")
    A(md_table(reasons.rename_axis("reason").reset_index(name="tokens")))
    A("")
    noem = exc.loc[exc["reason"].str.startswith("no_emission_data"), "token_id"].tolist()
    mism = exc.loc[exc["reason"].str.startswith("binance_symbol_price_mismatch"), ["token_id", "symbol", "reason"]]
    A(f"Notes: `no_emission_data` = Daily Emission returned `[]` after a spent call ({len(noem)} tokens: {', '.join(noem)}). "
      f"`binance_symbol_price_mismatch` = the Binance ticker price differs from marketCap/circulatingSupply by more than 3x. For NEIRO and MOVE the Binance symbol is genuinely a different asset; for FTT and CYBER it is more likely a stale Tokenomist market-cap snapshot, so those two could be re-admitted by hand (`--price-band 20`).")
    A("")
    if len(mism):
        A(md_table(mism))
        A("")
    A("")
    A("Selected universe (rank = market-cap order among eligible tokens):")
    A("")
    ucols = ["rank", "token_id", "symbol", "marketCap", "listedMethod", "binance_listing_date", "emission_first_date", "emission_last_date", "emission_rows"]
    A(md_table(uni[ucols]))
    A("")

    # ---------------- 2. Shape
    A("## 2. Dataset shape")
    A("")
    per = ds.groupby("token_id").agg(rows=("date", "size"), first_date=("date", "min"), last_date=("date", "max"),
                                     has_unlock_events=("has_unlock_events", "first")).reset_index()
    n_feat = len([c for c in ds.columns if c not in ("token_id", "symbol", "date")])
    A(f"- Rows: **{len(ds)}**; tokens: **{ds.token_id.nunique()}**; columns: **{ds.shape[1]}** ({n_feat} non-key columns, of which 5 are targets).")
    A(f"- Rows per token: min **{per.rows.min()}**, median **{int(per.rows.median())}**, max **{per.rows.max()}**; {int((per.rows < 200).sum())} tokens have fewer than 200 rows (Binance listing or TGE inside the window).")
    A(f"- Date coverage overall: **{ds.date.min()} to {ds.date.max()}** (emission history starts 2024-09-14 by plan limit; last 30 days dropped because `rv_fwd_30d` is not computable).")
    A(f"- Rows dropped: {int(meta['dropped_target_na'].sum())} for the forward-target rule (30 per token), {int(meta['dropped_float_zero'].sum())} for `float_pit == 0` or null "
      f"({int((meta['dropped_float_zero'] > 0).sum())} tokens affected). Emission series had {int(meta['emission_missing_days'].sum())} missing calendar days in total.")
    A("")
    A(md_table(per))
    A("")

    # ---------------- 3. Nulls
    A("## 3. Null rate per column (descending)")
    A("")
    nulls = ds.isna().mean().sort_values(ascending=False)
    nz = nulls[nulls > 0]
    tab = nz.rename_axis("column").reset_index(name="null_rate")
    tab["flag"] = np.where(tab["null_rate"] > 0.30, "**>30% NULL**", "")
    A(md_table(tab, "{:.3f}"))
    A("")
    A(f"- {len(nulls) - len(nz)} columns have zero nulls and are omitted from the table.")
    n_noev = int((~per["has_unlock_events"].astype(bool)).sum())
    A(f"- `days_to_next_cliff`, `next_cliff_pct_float` and `unlockPrecision` are null where `has_unlock_events` is false ({n_noev} of {len(per)} tokens) or no future event exists in the pulled window; this is structural, not missing-at-random. "
      "`rv_past_*`/`ret_past_*` nulls are the first days after a token's Binance listing. No imputation was done.")
    A("")

    # ---------------- 4. Descriptives
    A("## 4. Descriptive statistics of the key feature and target")
    A("")
    def desc(s):
        return {"mean": s.mean(), "median": s.median(), "p5": s.quantile(.05), "p95": s.quantile(.95), "min": s.min(), "max": s.max(), "std": s.std(), "n": int(s.notna().sum())}
    d = pd.DataFrame({FEAT: desc(ds[FEAT]), TGT: desc(ds[TGT])}).T.reset_index().rename(columns={"index": "column"})
    A(md_table(d))
    A("")
    zero = int((ds[FEAT] == 0).sum())
    n_zero_tok = int((ds.groupby("token_id")[FEAT].apply(lambda s: (s == 0).any())).sum())
    ended = int(ds["emission_schedule_ended"].sum())
    gt1 = ds.loc[ds[FEAT] > 1, "token_id"].unique().tolist()
    A(f"- Rows with `{FEAT} == 0`: **{zero}** of {len(ds)} ({zero / len(ds):.1%}), spread over {n_zero_tok} tokens: dates where the next 30 days carry no scheduled unlock (lumpy schedules, or the schedule has ended: {ended} rows flagged `emission_schedule_ended`).")
    A(f"- Rows with `{FEAT} > 1` (next-30-day unlock larger than the whole current float): **{int((ds[FEAT] > 1).sum())}**, all in the first weeks after TGE of {', '.join(gt1) or 'none'}. Genuine, not an error; a log or rank transform is advisable.")
    A("")
    A("Within-token variation of the feature (this is what matters for a panel model; pooled variation is mostly cross-sectional):")
    A("")
    def jumps(s, thr):
        f = s.values
        rel = np.abs(np.diff(f)) / np.maximum(f[:-1], 1e-12)
        return int((rel > thr).sum())
    wt = ds.groupby("token_id")[FEAT].agg(mean="mean", std="std", min="min", max="max", n_distinct="nunique", share_zero=lambda s: (s == 0).mean()).reset_index()
    wt["cv_within"] = wt["std"] / wt["mean"].replace(0, np.nan)
    wt["day_jumps_gt10pct"] = [jumps(g[FEAT], 0.10) for _, g in ds.groupby("token_id")]
    wt["spearman_vs_time"] = [g[[FEAT, "days_since_tge"]].corr(method="spearman").iloc[0, 1] for _, g in ds.groupby("token_id")]
    A(md_table(wt))
    A("")
    steppy = wt.loc[wt["day_jumps_gt10pct"] > 0, "token_id"].tolist()
    smooth = wt.loc[wt["day_jumps_gt10pct"] == 0, "token_id"].tolist()
    monotone = wt.loc[wt["spearman_vs_time"].abs() > 0.95, "token_id"].tolist()
    A(f"Reading: `day_jumps_gt10pct` counts day-to-day changes of the feature larger than 10%, i.e. scheduled cliffs entering/leaving the 30-day window. "
      f"**{len(steppy)} tokens have any such step**; the other {len(smooth)} have a smooth ratio that drifts with the growing float. "
      f"For {len(monotone)} tokens the feature is a strictly monotone function of time (|Spearman vs `days_since_tge`| > 0.95), so any correlation it shows with volatility for those tokens is a time trend, not an unlock signal. "
      f"Cross-sectionally the token-mean feature spans {wt['mean'].min():.4f} to {wt['mean'].max():.4f}, so a pooled model without token fixed effects would mostly learn token identity.")
    A("")

    # ---------------- 5. Spearman
    A("## 5. Spearman correlation: `emis_next_30d_pct_float` vs `rv_fwd_14d`")
    A("")
    pooled = ds[[FEAT, TGT]].corr(method="spearman").iloc[0, 1]
    ds["_dvol"] = ds[TGT] - ds["rv_past_14d"]           # change in vol: what an unlock feature would have to predict
    for c, src in (("_f", FEAT), ("_t", TGT), ("_p", "rv_past_14d"), ("_d", "_dvol")):
        ds[c + "_rank"] = ds.groupby("token_id")[src].rank()
    within = ds[["_f_rank", "_t_rank"]].corr().iloc[0, 1]
    within_past = ds[["_p_rank", "_t_rank"]].corr().iloc[0, 1]
    within_dvol = ds[["_f_rank", "_d_rank"]].corr().iloc[0, 1]
    A(f"- Pooled Spearman, all rows: **{pooled:+.3f}** (n={len(ds)}).")
    A(f"- Within-token Spearman (ranks computed inside each token, then pooled): **{within:+.3f}**. For comparison the persistence baseline `rv_past_14d` vs `rv_fwd_14d` is {within_past:+.3f} on the same basis.")
    A(f"- Within-token Spearman of the feature vs the **change** in vol (`rv_fwd_14d - rv_past_14d`): **{within_dvol:+.3f}**. This is the honest test: does knowing the next 30 days of unlocks tell you anything beyond the vol you already observe?")
    A("")
    rows = []
    for tid, g in ds.groupby("token_id"):
        rows.append({"token_id": tid, "n": len(g),
                     "feat_vs_rv_fwd_14d": g[[FEAT, TGT]].corr(method="spearman").iloc[0, 1],
                     "feat_vs_rv_past_14d": g[[FEAT, "rv_past_14d"]].corr(method="spearman").iloc[0, 1],
                     "feat_vs_vol_change": g[[FEAT, "_dvol"]].corr(method="spearman").iloc[0, 1],
                     "rv_past_vs_rv_fwd": g[["rv_past_14d", TGT]].corr(method="spearman").iloc[0, 1],
                     "days_to_cliff_vs_rv_fwd": g[["days_to_next_cliff", TGT]].corr(method="spearman").iloc[0, 1] if g["days_to_next_cliff"].notna().sum() > 30 else np.nan})
    tab5 = pd.DataFrame(rows)
    A(md_table(tab5, "{:+.3f}"))
    A("")
    same_sign = int(((tab5["feat_vs_rv_fwd_14d"] - tab5["feat_vs_rv_past_14d"]).abs() < 0.1).sum())
    dv = tab5["feat_vs_vol_change"]
    neg = int((tab5["feat_vs_rv_fwd_14d"] < 0).sum())
    A(f"Reading: in {same_sign} of {len(tab5)} tokens the feature correlates with *past* vol almost exactly as much as with *future* vol (columns 3 and 4 differ by < 0.1); "
      f"{neg} tokens have a negative feature-vs-future-vol correlation. Combined with section 4 (the feature is monotone in time for many tokens) this is the signature of slowly drifting series sharing a trend, not of unlocks moving volatility. "
      f"The vol-change column removes that level effect: across tokens its median is {dv.median():+.2f}, interquartile range {dv.quantile(.25):+.2f} to {dv.quantile(.75):+.2f}, and {int((dv > 0.2).sum())} tokens exceed +0.20 while {int((dv < -0.2).sum())} are below -0.20. "
      "With ~700 autocorrelated daily rows per token, individual values of this size are not distinguishable from noise without a block bootstrap; the cross-token distribution being centred slightly above zero is the only thing worth following up.")
    A("")

    # ---------------- 6. ESS
    A("## 6. Effective sample size")
    A("")
    ds["_d"] = pd.to_datetime(ds["date"])
    weekly = ds[ds["_d"].dt.weekday == 0]
    wk_per = weekly.groupby("token_id").size()
    ac = ds.groupby("token_id").apply(lambda g: g[TGT].autocorr(lag=1)).mean()
    ac14 = ds.groupby("token_id").apply(lambda g: g[TGT].autocorr(lag=14)).mean()
    A(f"- Daily rows: {len(ds)}. One row per token per week (Mondays): **{len(weekly)}** rows (per token min {wk_per.min()}, median {int(wk_per.median())}, max {wk_per.max()}).")
    A(f"- Mean lag-1 autocorrelation of `rv_fwd_14d` within token: {ac:.3f}; lag-14: {ac14:.3f}. Overlapping 14-day windows make consecutive targets share 13/14 of their data, so weekly sampling still leaves overlap; non-overlapping 14-day blocks would give ~{len(ds) // 14} rows.")
    A(f"- Cross-sectional breadth is the binding constraint: **{ds.token_id.nunique()} tokens**, of which only {len(steppy)} show step-like unlock variation (section 4). A pooled model is effectively fitting {len(steppy)} informative time series plus token fixed effects.")
    A("")

    # ---------------- 7. Schema surprises
    A("## 7. Schema surprises vs SCHEMA_REPORT.md")
    A("")
    surprises = []
    # key diffs
    def load_sample(name):
        p = os.path.join(SAMPLES, name)
        return json.load(open(p)) if os.path.exists(p) else None
    s_em = load_sample("emission_daily_arbitrum.json"); s_ue = load_sample("unlock_events_arbitrum.json"); s_al = load_sample("allocation_detail_arbitrum.json"); s_tl = load_sample("token_list.json")
    n_em = keyset(json.load(open(os.path.join(RAW, "sui", "emission_daily.json"))))
    n_ue = keyset(json.load(open(os.path.join(RAW, "sui", "unlock_events.json"))))
    n_al = keyset(json.load(open(os.path.join(RAW, "sui", "allocations.json"))))
    n_tl = keyset(tokens_list[:50])
    for name, old, new in [("emission daily", keyset(s_em), n_em), ("unlock events", keyset(s_ue), n_ue), ("allocation detail", keyset(s_al), n_al), ("token list", keyset(s_tl), n_tl)]:
        miss = sorted(old - new); added = sorted(new - old)
        surprises.append(f"- `{name}`: fields missing vs sample: {miss if miss else 'none'}; new fields: {added if added else 'none'}.")
    A("Field-level diff (2026-08-20 samples vs 2026-09-14 pulls):")
    A("")
    L.extend(surprises)
    A("")
    A("Behavioural / unit surprises (computed over the pulled universe):")
    A("")
    n_noev_raw = 0; n_maxsup_null = 0; n_neg_locked = 0; n_empty_alloc_rows = 0; n_rows = 0; precs = collections.Counter(); n_before_listing = 0
    for _, u in uni.iterrows():
        d = os.path.join(RAW, u["token_id"])
        em = json.load(open(f"{d}/emission_daily.json")); al = json.load(open(f"{d}/allocations.json")); ue = json.load(open(f"{d}/unlock_events.json"))
        n_noev_raw += (len(ue) == 0)
        n_maxsup_null += (al.get("maxSupply") is None)
        n_neg_locked += any(a["allocationLockedAmount"] < 0 for a in al["allocations"])
        n_empty_alloc_rows += sum(1 for r in em if not r["allocations"]); n_rows += len(em)
        for e in ue:
            for b in e["cliffUnlocks"]["allocationBreakdown"]:
                precs[b.get("unlockPrecision")] += 1
        n_before_listing += (str(u["emission_first_date"]) < str(u["binance_listing_date"]))
    A(f"- Token list grew from 626 to **{n_all}** rows; same 19 fields.")
    A("- **Plan-enforced date window** on `emission daily`: `Invalid Date Range: The available range for emission data are 2024-09-14 - 2027-06-30`. The schema report never hit this because it queried 2025. The returned series ends 2027-06-29 (the `--end` day itself is excluded).")
    A("- `--page-size 10000` is accepted and returns the full series in one call (max 1019 daily rows); the silent 20-row truncation from the schema report does not apply once `--page-size` is passed explicitly. No pagination calls were needed.")
    A(f"- `unlock events` returns `[]` for **{n_noev_raw} of {len(uni)}** tokens even though `emission daily` is populated for them: continuous issuance and linear vesting are not modelled as cliff events. `has_unlock_events` flags this.")
    A(f"- `emission daily.allocations[]` is **empty** on {n_empty_alloc_rows} of {n_rows} rows (days with `unlockAmount == 0`); the schema report said it 'normally has 1 element'. Row-level `unlockAmount` is the reliable field; the bucket split is `emis_next_30d_<bucket>` with `emis_next_30d_unattributed` as the residual.")
    A(f"- `unlockPrecision` values observed across all cliff breakdown lines: {dict(precs)}. The schema report only saw `day`.")
    A(f"- `allocation detail.allocationLockedAmount` is **slightly negative** for {n_neg_locked} tokens (e.g. SUI Series B: -5.96e-07) -> floating-point residue, not a data error; do not assert >= 0.")
    A(f"- `allocation detail.maxSupply` is **null for {n_maxsup_null} of {len(uni)} tokens** (uncapped supply). `emis_next_30d_pct_total` for those uses the sum of `allocationAmount` instead (`total_supply_basis` column).")
    A("- `totalCumulativeUnlockedAmount` is cumulative since inception even though the series starts 2024-09-14 (SUI first row = 2.67e9), so `float_pit` is usable from the first row. It is **end-of-day inclusive** (SUI 2024-10-01 cliff appears in the 2024-10-01 row).")
    A(f"- For {n_before_listing} tokens the emission series starts before the Binance listing (e.g. aster-2: emission 2025-09-14, listing 2025-10-06); rows before listing have no prices and are absent from the panel.")
    A("- `emission daily` and `allocation detail` still omit `tokenId`; it is injected from the directory name, as the schema report recommended.")
    A("")

    # ---------------- 8. Credits
    A("## 8. API credits spent (from `data/call_log.txt`)")
    A("")
    A(f"- Successful (`exit=0`) Tokenomist calls: **{len(ok)}** (pass 1 ceiling 40, pass 2 ceiling 2000; plan allows 5M/month at 120/min). One of these is a wasted duplicate of `token list` (first attempt returned data but the local decoder crashed on the Windows cp874 codepage; fixed by forcing UTF-8).")
    A(f"- Failed attempts (`exit=1`, `Invalid Date Range`, presumably not billed but listed for completeness): **{len(failed)}**.")
    A("- By endpoint (successful): " + ", ".join(f"`{k}` x{v}" for k, v in sorted(by_ep.items())) + ".")
    A(f"- Failed attempts also include 1 `allocation detail` timeout (ether-fi) that succeeded on retry.")
    A(f"- Binance: roughly {len(uni) * 3 + 2 * 215 + 10} public requests (`exchangeInfo`, listing-date probes, ticker prices, daily klines), paced at >= 0.35 s; used weight stayed far below the 6000/min limit.")
    A("")

    # ---------------- 8b. Alignment audit
    A("## 8b. Date-alignment audit (`scripts/audit_alignment.py`)")
    A("")
    A("- Tokenomist emission buckets start at 00:00:00Z and span exactly one day; Binance daily candles use the same UTC day. No missing or duplicate days in either source inside the panel window.")
    A("- Tokenomist's own `referencePrice` on day D matches the Binance **open of D / close of D-1** to about 0.15% (median across tokens) versus about 3% for the close of D. The two calendars are therefore aligned with no one-day shift, and the reference price is a start-of-day price.")
    A("- Cliff events fall on the same UTC date as the matching spike in the emission series for all but one event.")
    A("- Thirteen feature and target columns were recomputed independently by calendar-date lookup for 5 random dates per token; every value equals the dataset value.")
    A("- dYdX: Tokenomist's `referencePrice` is frozen at a stale value from 2025 on. The dataset never uses that field.")
    A("")

    # ---------------- 9. Verdict
    A("## 9. Feasibility verdict and what to change for v2")
    A("")
    A(f"**Feasible as a dataset; the signal question is open.** The panel now holds every token this data source and Binance can jointly support ({len(uni)} tokens, {len(ds)} daily rows). Joins, point-in-time float, forward emission windows and forward RV targets reconcile by hand (see `build_dataset.py` docstring). What remains are modelling-design issues, not data-access ones:")
    A("")
    A(f"1. **Heterogeneous universe.** {len(steppy)} of {len(wt)} tokens have scheduled cliffs that move `emis_next_30d_pct_float` day to day; the other {len(smooth)} are smooth issuance or linear vesting. Subset at modelling time with `has_unlock_events` / the section-4 step counts, or model the two regimes separately; do not pool blindly.")
    A("2. **History is capped at 2024-09-14** by the plan, so no token contributes more than ~700 daily rows / ~100 weekly rows, and the whole panel sits inside one market regime. Every token that passes the Binance-pair and age filters is already in; the only ways to grow further are a second price source for the 412 tokens without a Binance USDT pair, or waiting for history to accrue.")
    A("3. **Schedule revisions are invisible.** Emission rows carry today's curated schedule; `latestUpdateDate` on unlock events proves schedules get edited after the fact. `emis_next_*` are lookahead-safe in the mechanical sense (window starts D+1, float uses row D) but not in the information sense. Mitigation: snapshot `emission daily` weekly from now on and only use as-of snapshots for dates after the first snapshot.")
    A(f"4. **Signal check:** the feature's within-token correlation with future vol ({within:+.2f}) is about the same as the persistence baseline ({within_past:+.2f}), but it correlates just as strongly with *past* vol and only {within_dvol:+.2f} with the change in vol, and it is monotone in time for {len(monotone)} of {len(wt)} tokens. The raw correlation is a shared trend, not evidence of an unlock effect. A v2 model must be judged on incremental gain over HAR/GARCH-style baselines built from `rv_past_*` and `btc_rv_past_14d`, with rolling-origin or leave-one-token-out splits, no shuffling, and a block bootstrap for uncertainty.")
    A("")
    A(f"Re-pull cost to refresh everything from scratch: 1 + 3 x {len(uni)} = {1 + 3 * len(uni)} calls (~6 minutes at 100/min). Recommended cadence for the as-of snapshot mitigation in point 3: weekly `emission daily` only, {len(uni)} calls per week.")
    A("")

    out = os.path.join(DATA, "FEASIBILITY_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {out} ({len(L)} lines)")


if __name__ == "__main__":
    main()
