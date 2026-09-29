"""Step 2 - exploratory data analysis. Run from the repo root:
    python scripts/01_eda.py
Writes figures/eda_*.png and results/eda_summary.csv.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import spearmanr

import common as C

t0 = time.perf_counter()
C.set_style()
daily = C.load_data(freq="daily")
weekly = C.load_data(freq="weekly")

rv = np.exp(daily["y"])                                # rv_fwd_14d, level
emis = np.expm1(daily["emis_next_30d_pct_float"])      # raw fraction of float

# ---- 1. histograms, raw and log ------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
panels = [
    (rv, "rv_fwd_14d (raw, annualized)", C.PALETTE[0]),
    (daily["y"], "log(rv_fwd_14d)  = target y", C.PALETTE[0]),
    (emis, "emis_next_30d_pct_float (raw)", C.PALETTE[1]),
    (daily["emis_next_30d_pct_float"], "log1p(emis_next_30d_pct_float)", C.PALETTE[1]),
]
for ax, (s, label, color) in zip(axes.ravel(), panels):
    ax.hist(s, bins=80, color=color, edgecolor=C.SURFACE, linewidth=0.3)
    ax.set_title(label)
    ax.set_ylabel("rows")
    ax.text(0.98, 0.95, f"median {s.median():.3f}\nmean {s.mean():.3f}\n"
            f"max {s.max():.2f}\nzeros {(s == 0).mean():.1%}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=C.INK_2)
axes[1, 0].set_yscale("log")
axes[1, 1].set_yscale("log")
axes[1, 0].set_ylabel("rows (log scale)")
axes[1, 1].set_ylabel("rows (log scale)")
fig.suptitle("Target and main emission feature: raw vs log (daily panel, "
             f"{len(daily):,d} rows)", x=0.01, ha="left", fontweight="bold")
fig.tight_layout()
C.savefig(fig, "eda_histograms.png")

# ---- 2. decile plot -------------------------------------------------------
dec = pd.qcut(emis.rank(method="first"), 10, labels=False) + 1
g = pd.DataFrame({"decile": dec, "rv": rv, "emis": emis}).groupby("decile")
stats = g["rv"].agg(mean="mean", median="median",
                    q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75))
stats["emis_median"] = g["emis"].median()
fig, ax = plt.subplots(figsize=(9, 5))
ax.fill_between(stats.index, stats["q25"], stats["q75"], color=C.PALETTE[0],
                alpha=0.18, linewidth=0, label="IQR (25th-75th pct)")
ax.plot(stats.index, stats["median"], color=C.PALETTE[0], linestyle="--",
        linewidth=1.5, label="median")
ax.plot(stats.index, stats["mean"], color=C.PALETTE[0], marker="o", label="mean")
ax.set_xticks(stats.index)
ax.set_xticklabels([f"D{d}\n{m:.1%}" for d, m in stats["emis_median"].items()])
ax.set_xlabel("decile of emis_next_30d_pct_float (median share of float unlocking in 30d)")
ax.set_ylabel("rv_fwd_14d (annualized)")
ax.set_ylim(0, None)
ax.set_title("Forward 14d volatility by unlock-pressure decile (daily panel)")
ax.legend(loc="upper left")
C.savefig(fig, "eda_decile_emission_vs_rv.png")
print(stats.round(4).to_string())

# ---- 3. correlation heatmap ----------------------------------------------
top_emis = ["emis_next_7d_pct_float", "emis_next_30d_pct_float",
            "emis_next_90d_pct_float", "emis_next_30d_pct_total",
            "days_to_next_cliff", "next_cliff_pct_float", "has_unlock_events"]
cols = ["y"] + C.CONTROLS + top_emis
corr = daily[cols].corr(method="spearman")
cmap = LinearSegmentedColormap.from_list("div", ["#d03b3b", "#f0efec", "#2a78d6"])
fig, ax = plt.subplots(figsize=(11, 9))
sns.heatmap(corr, cmap=cmap, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
            annot_kws={"size": 7}, linewidths=1, linecolor=C.SURFACE,
            cbar_kws={"label": "Spearman rho", "shrink": 0.7}, ax=ax)
ax.grid(False)
ax.set_title("Spearman correlation: target y, controls and emission features "
             "(daily panel)")
C.savefig(fig, "eda_correlation_heatmap.png")

# ---- 4. per-token coverage ------------------------------------------------
cov = daily.groupby("token_id")["date"].agg(["count", "min", "max"]).sort_values(
    ["min", "max"], ascending=[True, False])
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.hist(cov["count"], bins=40, color=C.PALETTE[0], edgecolor=C.SURFACE)
ax.axvline(cov["count"].median(), color=C.INK_2, linestyle="--", linewidth=1)
ax.text(cov["count"].median(), ax.get_ylim()[1] * 0.95,
        f" median {cov['count'].median():.0f} rows", color=C.INK_2, fontsize=9,
        ha="right")
ax.set_xlabel("daily rows per token (after cleaning)")
ax.set_ylabel("tokens")
ax.set_title(f"Coverage: rows per token ({len(cov)} tokens)")
C.savefig(fig, "eda_rows_per_token.png")

fig, ax = plt.subplots(figsize=(9, 9))
ypos = np.arange(len(cov))
ax.hlines(ypos, cov["min"], cov["max"], color=C.PALETTE[0], linewidth=1.2)
folds = C.make_folds(daily, verbose=False)
for c in folds.cutoffs:
    ax.axvline(c, color=C.INK_2, linestyle=":", linewidth=1)
ax.text(folds.cutoffs[0], len(cov) + 1, "fold cutoffs ", color=C.INK_2,
        fontsize=8, ha="right")
ax.set_yticks([])
ax.set_ylabel(f"{len(cov)} tokens, sorted by first date")
ax.set_ylim(-2, len(cov) + 4)
ax.grid(axis="y", visible=False)
ax.set_title("Coverage: date range of each token in the cleaned daily panel")
C.savefig(fig, "eda_token_date_ranges.png")

# ---- 5. summary table -----------------------------------------------------
raw = pd.read_csv(C.DATA_PATH, usecols=["days_to_next_cliff", "unlockPrecision"])
pooled = spearmanr(daily["emis_next_30d_pct_float"], daily["y"]).statistic
per_tok = daily.groupby("token_id").apply(
    lambda d: spearmanr(d["emis_next_30d_pct_float"], d["y"]).statistic
    if d["emis_next_30d_pct_float"].nunique() > 1 else np.nan,
    include_groups=False)
rows = [
    ("rows_daily", len(daily)), ("rows_weekly", len(weekly)),
    ("tokens", daily["token_id"].nunique()),
    ("date_min", daily["date"].min().date()), ("date_max", daily["date"].max().date()),
    ("rows_per_token_median", cov["count"].median()),
    ("rows_per_token_min", cov["count"].min()),
    ("spearman_emis30_y_pooled", round(pooled, 4)),
    ("spearman_emis30_y_per_token_median", round(per_tok.median(), 4)),
    ("spearman_emis30_y_per_token_n", int(per_tok.notna().sum())),
    ("spearman_emis30_y_per_token_share_positive",
     round((per_tok.dropna() > 0).mean(), 4)),
    ("raw_null_rate_days_to_next_cliff (filled 365)",
     round(raw["days_to_next_cliff"].isna().mean(), 4)),
    ("raw_null_rate_unlockPrecision (-> unknown)",
     round(raw["unlockPrecision"].isna().mean(), 4)),
]
rows += [(f"null_rate_after_cleaning:{c}", round(daily[c].isna().mean(), 4))
         for c in C.FULL]
summary = pd.DataFrame(rows, columns=["metric", "value"])
C.RESULTS_DIR.mkdir(exist_ok=True)
summary.to_csv(C.RESULTS_DIR / "eda_summary.csv", index=False)
print(summary.head(13).to_string(index=False))
print(f"max null rate after cleaning: {daily[C.FULL].isna().mean().max():.4f}")
print(f"[01_eda] done in {time.perf_counter() - t0:.1f}s")
