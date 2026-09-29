"""
Final ML-readiness check on the panel dataset. Read-only. Prints PASS / WARN / FAIL per check
and a suggested chronological split. Dataset path: env DATASET_PATH or data/dataset_v1.csv.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.environ.get("DATASET_PATH", os.path.join(ROOT, "data", "dataset_v1.csv"))
ds = pd.read_csv(PATH)
dic = pd.read_csv(os.path.join(ROOT, "data", "data_dictionary_v1.csv"))
ds["_d"] = pd.to_datetime(ds["date"])
TARGETS = ["rv_fwd_7d", "rv_fwd_14d", "rv_fwd_30d", "rv_fwd_14d_parkinson", "fwd_ret_14d"]
KEYS = ["token_id", "symbol", "date"]
STR = ["listedMethod", "unlockPrecision", "total_supply_basis", "tge_proxy_date"]
BOOL = ["has_unlock_events", "emission_schedule_ended"]
num = [c for c in ds.columns if c not in KEYS + STR + BOOL + ["_d"]]
feats = [c for c in num if c not in TARGETS]
status = {"FAIL": 0, "WARN": 0, "PASS": 0}


def line(level, name, detail=""):
    status[level] += 1
    print(f"[{level}] {name}" + (f" -- {detail}" if detail else ""))


def check(ok, name, detail="", warn=False):
    line("PASS" if ok else ("WARN" if warn else "FAIL"), name, detail)


print(f"dataset: {PATH}\nshape: {ds.shape[0]} rows x {ds.shape[1] - 1} cols, {ds.token_id.nunique()} tokens, {ds.date.min()} .. {ds.date.max()}\n")

# ---- structure
check("centrifuge" not in set(ds.token_id), "centrifuge removed")
check(not ds.duplicated(["token_id", "date"]).any(), "(token_id, date) unique")
check(ds[["token_id", "date"]].equals(ds.sort_values(["token_id", "date"])[["token_id", "date"]].reset_index(drop=True)), "rows sorted by token_id, date (no shuffling)")
check(set(ds.columns) - {"_d"} == set(dic["column"]), "data dictionary covers exactly the dataset columns", str(set(ds.columns) - {"_d"} ^ set(dic["column"])))
check(all(pd.api.types.is_numeric_dtype(ds[c]) for c in num), "all numeric columns parse as numeric", str([c for c in num if not pd.api.types.is_numeric_dtype(ds[c])]))
brk = ds.groupby("token_id")["_d"].apply(lambda s: int((s.diff().dt.days.dropna() != 1).sum())).sum()
check(brk == 0, "dates consecutive within every token", f"{brk} breaks")

# ---- values
inf = {c: int(np.isinf(ds[c]).sum()) for c in num if np.isinf(ds[c]).any()}
check(not inf, "no infinite values", str(inf))
check(not ds[TARGETS].isna().any().any(), "targets have no nulls", str(ds[TARGETS].isna().sum().to_dict()))
neg = {c: int((ds[c] < 0).sum()) for c in num if c.startswith(("rv_", "emis_", "float_", "btc_rv", "eth_rv", "alloc_share", "next_cliff", "days_")) and (ds[c] < 0).any()}
check(not neg, "no negative values in vol / emission / supply / share columns", str(neg))
check((ds[[c for c in ds.columns if c.startswith("alloc_share_")]].sum(axis=1).sub(1).abs() < 1e-6).all(), "allocation shares sum to 1")
resid = (ds["emis_next_30d"] - ds[[c for c in ds.columns if c.startswith("emis_next_30d_") and "pct" not in c]].sum(axis=1)).abs()
check((resid <= 1e-6 * ds["emis_next_30d"].clip(lower=1)).all(), "bucket split sums to emis_next_30d", f"max residual {resid.max():.3g}")
check((ds["emis_next_7d"] <= ds["emis_next_30d"] * (1 + 1e-9) + 1e-6).all() and (ds["emis_next_30d"] <= ds["emis_next_90d"] * (1 + 1e-9) + 1e-6).all(), "emis_next_7d <= 30d <= 90d")
mono = ds.groupby("token_id")["float_pit"].apply(lambda s: int((s.diff().dropna() < -1e-6 * s.abs().max()).sum()))
check(mono.sum() == 0, "float_pit never decreases within a token", f"{int((mono > 0).sum())} tokens, {int(mono.sum())} rows: {mono[mono > 0].to_dict()}", warn=True)
const = [c for c in feats if ds[c].nunique(dropna=True) <= 1]
check(not const, "no constant feature columns", str(const), warn=True)

# ---- nulls in features
nul = ds[feats + STR].isna().mean()
print("\nfeature null rates > 0:")
print(nul[nul > 0].sort_values(ascending=False).round(4).to_string())
check((nul[nul > 0.30].index.isin(["days_to_next_cliff", "next_cliff_pct_float", "unlockPrecision"])).all(), "only the structurally-null cliff columns exceed 30% null", str(nul[nul > 0.30].to_dict()))

# ---- outliers (informational)
print("\nheavy tails (not altered, per the no-winsorize rule):")
for c in ["rv_fwd_14d", "rv_past_14d", "emis_next_30d_pct_float", "next_cliff_pct_float", "fwd_ret_14d"]:
    s = ds[c].dropna()
    print(f"   {c:26s} p50={s.median():.4g}  p99={s.quantile(.99):.4g}  max={s.max():.4g}  min={s.min():.4g}  rows>p99*5: {int((s > s.quantile(.99) * 5).sum())}")
big = ds[ds["rv_fwd_14d"] > 5]
line("WARN" if len(big) else "PASS", "extreme targets (rv_fwd_14d > 500% annualized)", f"{len(big)} rows in {big.token_id.nunique()} tokens: {big.groupby('token_id').size().sort_values(ascending=False).head(8).to_dict()}")

# ---- leakage screen: a feature that is nearly identical to a target is a bug
leak = []
for f in feats:
    for t in TARGETS:
        j = ds[[f, t]].dropna()
        if len(j) > 100 and j[f].nunique() > 1:
            r = j[f].rank().corr(j[t].rank())
            if abs(r) > 0.9:
                leak.append((f, t, round(r, 3)))
check(not leak, "no feature has |Spearman| > 0.9 with any target (leakage screen)", str(leak))
unsafe = dic[~dic["lookahead_safe"].astype(str).str.startswith("yes")]["column"].tolist()
check(set(unsafe) == set(TARGETS), "dictionary marks exactly the 5 targets as not lookahead-safe", str(unsafe))

# ---- chronological split proposal with 30-day embargo (targets look 30 days ahead)
d0, d1 = ds["_d"].min(), ds["_d"].max()
span = (d1 - d0).days
train_end = d0 + pd.Timedelta(days=int(span * 0.70))
val_start = train_end + pd.Timedelta(days=31)
val_end = d0 + pd.Timedelta(days=int(span * 0.85))
test_start = val_end + pd.Timedelta(days=31)
parts = {"train": ds[ds["_d"] <= train_end], "val": ds[(ds["_d"] >= val_start) & (ds["_d"] <= val_end)], "test": ds[ds["_d"] >= test_start]}
print("\nsuggested chronological split (30-day embargo between blocks, because rv_fwd_30d looks 30 days ahead):")
for k, g in parts.items():
    print(f"   {k:5s} {g['_d'].min().date()} .. {g['_d'].max().date()}  rows={len(g):6d}  tokens={g.token_id.nunique():3d}  weekly_rows={int((g['_d'].dt.weekday == 0).sum()):5d}  mean rv_fwd_14d={g['rv_fwd_14d'].mean():.3f}  share emis_pct_float==0: {(g['emis_next_30d_pct_float'] == 0).mean():.2f}")
new_in_test = set(parts["test"].token_id) - set(parts["train"].token_id)
line("WARN" if new_in_test else "PASS", "tokens that appear in test but never in train (cold start)", f"{len(new_in_test)}: {sorted(new_in_test)[:12]}")
short = ds.groupby("token_id").size()
line("WARN" if (short < 200).any() else "PASS", "tokens with fewer than 200 rows", f"{int((short < 200).sum())}: {short[short < 200].to_dict()}")

print(f"\nSUMMARY: {status['PASS']} pass, {status['WARN']} warn, {status['FAIL']} fail")
