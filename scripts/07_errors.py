"""Step 8 - Error analysis and practical relevance. Run from the repo root:
    python scripts/07_errors.py
Reads the saved test-set predictions of the main daily runs (no refitting of
the four regressors), so it takes about a minute. Writes
results/error_by_group.csv, results/error_level_summary.csv,
results/error_big_misses.csv and figures/errors_calibration.png,
figures/errors_by_group.png, figures/tree_depth3_full.png.

Questions it answers, all on the same test rows for every forecast:
  - Which mistakes remain? RMSE and bias by ex-ante subgroup (trailing vol,
    unlock pressure, cliff in the next 14 days, token age, BTC regime) and by
    realized outcome, plus the share of forecasts off by more than 2x.
  - Do unlock features help where they should? FULL minus CONTROLS RMSE
    inside the high-unlock and cliff-imminent groups.
  - What does a tree use? One illustrative depth-3 regression tree on FULL
    features, fit on the last fold's training rows only (not a competing model).
Grouping by realized volatility uses the outcome, so it describes errors; it
is never a feature.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor, plot_tree

import common as C

RUNS = {  # label -> (model, feature set)
    "Ridge CONTROLS": ("ridge", "CONTROLS"), "Ridge FULL": ("ridge", "FULL"),
    "RF CONTROLS": ("rf", "CONTROLS"), "RF FULL": ("rf", "FULL"),
    "KNN CONTROLS": ("knn", "CONTROLS"), "KNN FULL": ("knn", "FULL"),
    "EN CONTROLS": ("enet", "CONTROLS"), "EN FULL": ("enet", "FULL"),
}
SHOW = ["Persistence", "Train mean", "Ridge CONTROLS", "RF CONTROLS", "RF FULL"]
BIG_MISS = np.log(2.0)   # forecast off by more than a factor of 2


def test_frame(df, folds) -> pd.DataFrame:
    """Every test row once, with ex-ante descriptors and all forecasts."""
    rows = []
    for k, (tr, _, te) in enumerate(folds, start=1):
        part = df.iloc[te][["token_id", "date", "y", "rv_past_14d", "btc_rv_past_14d",
                            "days_since_tge", "days_to_next_cliff",
                            "emis_next_30d_pct_float"]].copy()
        part["fold"] = k
        part["Persistence"] = np.log(part["rv_past_14d"])
        part["Train mean"] = df["y"].iloc[tr].mean()
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    for label, (m, fs) in RUNS.items():
        p = pd.read_parquet(C.RESULTS_DIR / f"preds_{m}_{fs}_daily.parquet")
        p = p.rename(columns={"y_pred": label})[["token_id", "date", "fold", label]]
        out = out.merge(p, on=["token_id", "date", "fold"], how="left", validate="1:1")
    missing = out[list(RUNS)].isna().sum()
    assert missing.sum() == 0, f"predictions missing for some test rows:\n{missing}"

    emis = np.expm1(out["emis_next_30d_pct_float"])          # share of float, level
    out["unlock_group"] = pd.cut(emis, [-np.inf, 0.005, 0.02, 0.05, np.inf],
                                 labels=["<0.5%", "0.5-2%", "2-5%", ">5%"])
    out["cliff_14d"] = np.where(out["days_to_next_cliff"] <= 14, "cliff in 14d", "no cliff in 14d")
    out["age_group"] = pd.cut(out["days_since_tge"], [-np.inf, 365, 730, np.inf],
                              labels=["<1y", "1-2y", ">2y"])
    out["trail_vol_q"] = pd.qcut(out["rv_past_14d"], 5, labels=[f"Q{i}" for i in range(1, 6)])
    out["btc_regime"] = pd.qcut(out["btc_rv_past_14d"], 3, labels=["calm", "mid", "stressed"])
    out["realized_q"] = pd.qcut(out["y"], 5, labels=[f"Q{i}" for i in range(1, 6)])
    return out


def group_table(t: pd.DataFrame) -> pd.DataFrame:
    labels = ["Persistence", "Train mean"] + list(RUNS)
    recs = []
    for dim in ["unlock_group", "cliff_14d", "age_group", "trail_vol_q", "btc_regime", "realized_q"]:
        for g, sub in t.groupby(dim, observed=True):
            r = {"dimension": dim, "group": str(g), "n": len(sub), "share": len(sub) / len(t)}
            for lab in labels:
                err = sub["y"] - sub[lab]
                r[f"rmse|{lab}"] = float(np.sqrt(np.mean(err ** 2)))
                r[f"bias|{lab}"] = float(np.mean(err))   # >0: forecast too low
            for m in ["Ridge", "RF", "KNN", "EN"]:
                r[f"delta_rmse|{m}"] = r[f"rmse|{m} FULL"] - r[f"rmse|{m} CONTROLS"]
            recs.append(r)
    return pd.DataFrame(recs)


def level_summary(t: pd.DataFrame) -> pd.DataFrame:
    """Errors in annualized-vol units, the scale a risk desk works in."""
    rv = np.exp(t["y"])
    recs = []
    for lab in ["Persistence", "Train mean"] + list(RUNS):
        f = np.exp(t[lab])
        err = t["y"] - t[lab]
        recs.append({"forecast": lab,
                     "median_abs_vol_error": float(np.median(np.abs(f - rv))),
                     "median_abs_pct_error": float(np.median(np.abs(f / rv - 1))),
                     "share_within_25pct": float(np.mean(np.abs(f / rv - 1) <= 0.25)),
                     "share_off_by_2x": float(np.mean(np.abs(err) > BIG_MISS)),
                     "share_big_miss_underforecast": float(np.mean(err[np.abs(err) > BIG_MISS] > 0)),
                     "rmse_log": float(np.sqrt(np.mean(err ** 2)))})
    return pd.DataFrame(recs)


def big_misses(t: pd.DataFrame, label: str = "Ridge CONTROLS") -> pd.DataFrame:
    """Who the remaining 2x misses are, against all other test rows."""
    miss = np.abs(t["y"] - t[label]) > BIG_MISS
    emis = np.expm1(t["emis_next_30d_pct_float"])
    recs = []
    for name, m in (("2x miss", miss), ("other rows", ~miss)):
        s = t[m]
        recs.append({"rows": name, "n": int(m.sum()),
                     "median_days_since_tge": float(s["days_since_tge"].median()),
                     "median_rv_past_14d": float(s["rv_past_14d"].median()),
                     "median_rv_fwd_14d": float(np.exp(s["y"]).median()),
                     "median_unlock_30d_pct_float": float(emis[m].median()),
                     "share_cliff_in_14d": float((s["days_to_next_cliff"] <= 14).mean()),
                     "share_young_lt_1y": float((s["days_since_tge"] < 365).mean())})
    return pd.DataFrame(recs)


def plot_calibration(t: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    ax = axes[0]
    for lab, col in (("Persistence", C.INK_2), ("Ridge CONTROLS", C.PALETTE[0]), ("RF FULL", C.PALETTE[1])):
        b = pd.qcut(t[lab], 10, duplicates="drop")
        g = t.groupby(b, observed=True).agg(pred=(lab, "mean"), real=("y", "mean"))
        ax.plot(np.exp(g["pred"]), np.exp(g["real"]), "o-", color=col, label=lab)
    lo, hi = 0.3, 2.0
    ax.plot([lo, hi], [lo, hi], ls="--", color=C.GRID_DARK if hasattr(C, "GRID_DARK") else "0.6", lw=1)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("forecast rv_fwd_14d (decile mean)"); ax.set_ylabel("realized rv_fwd_14d")
    ax.set_title("Calibration: forecast deciles vs realized")
    ax.legend(loc="upper left")
    ax = axes[1]
    q = t.groupby("realized_q", observed=True)
    x = np.arange(5)
    for i, (lab, col) in enumerate((("Persistence", C.INK_2), ("Ridge CONTROLS", C.PALETTE[0]), ("RF FULL", C.PALETTE[1]))):
        bias = q.apply(lambda s: float(np.mean(s["y"] - s[lab])))
        ax.bar(x + (i - 1) * 0.27, bias.to_numpy(), width=0.27, color=col, label=lab)
    ax.axhline(0, color=C.INK_2, lw=0.8)
    ax.set_xticks(x, [f"Q{i}\n{np.exp(t.loc[t.realized_q == f'Q{i}', 'y']).median():.2f}" for i in range(1, 6)])
    ax.set_xlabel("quintile of realized rv_fwd_14d (median)")
    ax.set_ylabel("mean error, log (realized - forecast)")
    ax.set_title("Remaining mistakes: too high when calm, too low when volatile")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    C.savefig(fig, "errors_calibration.png")


def plot_groups(g: pd.DataFrame) -> None:
    dims = [("unlock_group", "30-day unlock pressure (share of float)"),
            ("cliff_14d", "cliff unlock within 14 days"),
            ("age_group", "token age"), ("btc_regime", "BTC volatility regime")]
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.4), sharey=True)
    cols = {"Persistence": C.INK_2, "Train mean": "#B7BDC7", "Ridge CONTROLS": C.PALETTE[0],
            "RF CONTROLS": "#7FB0E6", "RF FULL": C.PALETTE[1]}
    for ax, (dim, title) in zip(axes, dims):
        sub = g[g.dimension == dim]
        x = np.arange(len(sub))
        w = 0.8 / len(SHOW)
        for i, lab in enumerate(SHOW):
            ax.bar(x + (i - (len(SHOW) - 1) / 2) * w, sub[f"rmse|{lab}"], width=w,
                   color=cols[lab], label=lab)
        ax.set_xticks(x, [f"{gr}\n(n={n:,})" for gr, n in zip(sub.group, sub.n)], fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("test RMSE (log vol)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(SHOW), fontsize=9)
    fig.suptitle("Test RMSE by ex-ante subgroup (daily panel, all 5 folds pooled)",
                 x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    C.savefig(fig, "errors_by_group.png")


def plot_tree_last_fold(df, folds) -> list[str]:
    tr = folds[-1][0]
    feats = C.FEATURE_SETS["FULL"]
    tree = DecisionTreeRegressor(max_depth=3, min_samples_leaf=500,
                                 random_state=C.RANDOM_STATE)
    tree.fit(df[feats].iloc[tr], df["y"].iloc[tr])
    fig, ax = plt.subplots(figsize=(16, 6.5))
    plot_tree(tree, feature_names=feats, filled=False, impurity=False, rounded=True,
              precision=2, fontsize=8, ax=ax)
    ax.set_title("Illustrative depth-3 regression tree on FULL features "
                 "(last fold, training rows only; leaf value = mean log rv_fwd_14d)")
    C.savefig(fig, "tree_depth3_full.png")
    used = [feats[i] for i in tree.tree_.feature if i >= 0]
    return used


def main() -> None:
    C.set_style()
    df = C.load_data(freq="daily", verbose=False)
    folds = C.make_folds(df, verbose=False)
    t = test_frame(df, folds)
    print(f"[errors] {len(t):,} test rows, {t.token_id.nunique()} tokens")

    g = group_table(t)
    g.to_csv(C.RESULTS_DIR / "error_by_group.csv", index=False)
    lv = level_summary(t)
    lv.to_csv(C.RESULTS_DIR / "error_level_summary.csv", index=False)
    bm = big_misses(t)
    bm.to_csv(C.RESULTS_DIR / "error_big_misses.csv", index=False)

    pd.set_option("display.width", 200)
    cols = ["dimension", "group", "n"] + [f"rmse|{s}" for s in SHOW] + ["delta_rmse|Ridge", "delta_rmse|RF"]
    print(g[cols].round(4).to_string(index=False))
    print(lv.round(3).to_string(index=False))
    print(bm.round(3).to_string(index=False))

    plot_calibration(t)
    plot_groups(g)
    used = plot_tree_last_fold(df, folds)
    print("[tree] split features:", ", ".join(dict.fromkeys(used)))


if __name__ == "__main__":
    main()
