"""Step 5 - compare every model. Run from the repo root:
    python scripts/04_compare.py
Reads every per-fold results CSV in results/ (anything with the results
schema, so teammates' models appear automatically), writes
results/comparison_table.csv and figures/compare_r2_oos.png.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import common as C

METRICS = ["rmse", "mae", "r2_oos", "spearman", "rmse_level"]
REQUIRED = set(C.RESULT_COLUMNS) - {"subsample"}
BASELINES = ["persistence", "train_mean"]


def read_results() -> pd.DataFrame:
    frames = []
    for path in sorted(C.RESULTS_DIR.glob("*.csv")):
        head = pd.read_csv(path, nrows=0)
        if not REQUIRED.issubset(head.columns):
            continue  # eda summary, importances, validation curves, ...
        d = pd.read_csv(path)
        if "subsample" not in d.columns:
            d["subsample"] = "all"
        d["subsample"] = d["subsample"].fillna("all")
        frames.append(d)
        print(f"[04_compare] {path.name}: {len(d)} fold rows, "
              f"models {sorted(d['model'].unique())}")
    return pd.concat(frames, ignore_index=True)


def main():
    C.set_style()
    res = read_results()
    keys = ["model", "feature_set", "freq", "target", "subsample"]
    table = res.groupby(keys, sort=False)[METRICS].agg(["mean", "std"])
    table.columns = [f"{m}_{s}" for m, s in table.columns]
    table.insert(0, "n_folds", res.groupby(keys, sort=False)["fold"].nunique())
    table = table.reset_index().sort_values(
        ["target", "subsample", "freq", "model", "feature_set"],
        key=lambda s: s.map({"daily": 0, "weekly": 1}) if s.name == "freq" else s)
    table.to_csv(C.RESULTS_DIR / "comparison_table.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30,
                           "display.max_rows", 200):
        print(table.round(4).to_string(index=False))

    plot(table)


def plot(table):
    main_t = table[(table.target == C.TARGETS["y"]) & (table.subsample == "all")]
    models = [m for m in main_t["model"].unique() if m not in BASELINES]
    sets = [("CONTROLS", "controls only", C.PALETTE[0]),
            ("FULL", "controls + emission + static (FULL)", C.PALETTE[1])]
    fig, axes = plt.subplots(1, 2, figsize=(max(9, 2.2 * len(models) + 5), 5),
                             sharey=True)
    for ax, freq in zip(axes, ("daily", "weekly")):
        t = main_t[main_t.freq == freq].set_index(["model", "feature_set"])
        x = np.arange(len(models))
        for i, (fs, label, color) in enumerate(sets):
            mean = [t["r2_oos_mean"].get((m, fs), np.nan) for m in models]
            std = [t["r2_oos_std"].get((m, fs), np.nan) for m in models]
            ax.bar(x + (i - 0.5) * 0.38, mean, width=0.36, yerr=std, color=color,
                   label=label, error_kw={"ecolor": C.INK_2, "elinewidth": 1})
            for xi, v in zip(x, mean):
                if np.isfinite(v):
                    ax.text(xi + (i - 0.5) * 0.38, 0.005, f"{v:.3f}", ha="center",
                            va="bottom", fontsize=8, color="white",
                            fontweight="bold")
        ax.axhline(0, color=C.INK, linestyle="--", linewidth=1.2,
                   label="persistence baseline (0 by construction)")
        if ("train_mean", "NONE") in t.index:
            tm = t.loc[("train_mean", "NONE"), "r2_oos_mean"]
            ax.axhline(tm, color=C.INK_2, linestyle=":", linewidth=1.5,
                       label="pooled train-mean baseline")
            ax.text(-0.58, tm, f"{tm:.3f}", ha="left", va="bottom", fontsize=8,
                    color=C.INK_2)
        ax.set_xticks(x)
        ax.set_xticklabels(models)
        ax.set_xlim(-0.6, len(models) - 0.4)
        ax.grid(axis="x", visible=False)
        ax.set_title(f"{freq} panel", fontsize=10)
    axes[0].set_ylabel("r2_oos vs persistence (mean of 5 folds, bar = +/- 1 std)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, -0.1))
    fig.suptitle("Out-of-sample R2 by model: controls only vs full feature set "
                 "(target log rv_fwd_14d)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    C.savefig(fig, "compare_r2_oos.png")


if __name__ == "__main__":
    main()
