"""Step 8 - Gradient boosting (LightGBM). Run from the repo root:
    python scripts/07_lgbm.py               # runs + importance figure
    python scripts/07_lgbm.py --fresh       # recompute runs already in lightgbm.csv
    LGBM_SMOKE=1 python scripts/07_lgbm.py  # tiny grid, nothing saved (code check)
Writes results/lightgbm.csv (+ preds/val files), results/lgbm_importance.csv
and figures/lgbm_importance.png.

Ported from a teammate's notebook onto the shared harness. His grid
(learning_rate up to 0.1, up to 31 leaves, min_child_samples down to 50)
overfit the small weekly folds: weekly r2_oos was 0.08 (CONTROLS) and 0.10
(FULL), below the pooled train-mean baseline (0.17), with fold 1 at -0.47.
The grid below is shifted toward stronger regularization (slower learning,
fewer leaves, larger leaves). It is the same grid for CONTROLS and FULL, so
the comparison between them is unaffected.

Tuning budget follows 03_rf.py: the daily runs evaluate a fixed, seeded
random subset of the 32-config grid; weekly runs use the full grid.
Trees need no scaling; the Pipeline wrapper keeps the harness contract.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from matplotlib.patches import Patch
from sklearn.pipeline import Pipeline

import common as C

NAME = "lightgbm"
SMOKE = os.environ.get("LGBM_SMOKE") == "1"
FRESH = "--fresh" in sys.argv
LGBM_GRID = {"n_estimators": [200, 500],
             "learning_rate": [0.02, 0.05],
             "num_leaves": [7, 15],
             "min_child_samples": [100, 400],
             "reg_lambda": [1, 10]}
# configs evaluated per fold (None = full grid of 32)
BUDGET = {"daily_main": 12, "daily_robust": 6, "weekly": None}
if SMOKE:
    LGBM_GRID = {"n_estimators": [100], "learning_rate": [0.05],
                 "num_leaves": [7, 15], "min_child_samples": [200],
                 "reg_lambda": [1]}
    BUDGET = {k: None for k in BUDGET}

GROUP_COLOR = {"controls": C.PALETTE[0], "emission": C.PALETTE[1],
               "static": C.PALETTE[2]}


def group_of(feature: str) -> str:
    return ("controls" if feature in C.CONTROLS else
            "emission" if feature in C.EMISSION else "static")


def lgbm_factory(**params) -> Pipeline:
    return Pipeline([("lgbm", LGBMRegressor(
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        deterministic=True, force_row_wise=True,  # reproducible with n_jobs=-1
        random_state=C.RANDOM_STATE, n_jobs=-1, verbose=-1, **params))])


def finished_run(folds, fs, freq, target="y", subsample="all"):
    """Rows already in results/lightgbm.csv for this run, or None."""
    path = C.RESULTS_DIR / f"{NAME}.csv"
    if SMOKE or FRESH or not path.exists():
        return None
    old = pd.read_csv(path)
    key = {"model": NAME, "feature_set": fs, "freq": freq,
           "target": C.TARGETS[target], "subsample": subsample}
    mask = np.logical_and.reduce([old[k].astype(str) == v for k, v in key.items()])
    rows = old[mask]
    if len(rows) == len(folds) and sorted(rows["fold"]) == list(range(1, len(folds) + 1)):
        return rows.reset_index(drop=True)
    return None


def run(df, folds, fs, freq, budget, **kw):
    done = finished_run(folds, fs, freq, **kw)
    if done is not None:
        print(f"[{NAME}|{C.run_tag(fs, freq, **kw)}] found in results/{NAME}.csv, "
              f"skipping (mean rmse {done['rmse'].mean():.4f}); use --fresh to rerun")
        return done
    return C.run_model(NAME, lgbm_factory, df, folds, fs, LGBM_GRID, freq,
                       max_configs=BUDGET[budget], save=not SMOKE, **kw)


def main_runs():
    out = []
    for freq in ("daily", "weekly"):
        df = C.load_data(freq=freq)
        folds = C.make_folds(df)
        C.baselines(df, folds, freq=freq, save=not SMOKE)
        for fs in ("CONTROLS", "FULL"):
            out.append(run(df, folds, fs, freq,
                           "weekly" if freq == "weekly" else "daily_main"))
    return pd.concat(out)


def robustness_runs(df, folds):
    out = []
    for target in ("y_14d_parkinson", "y_7d", "y_30d"):
        C.baselines(df, folds, freq="daily", target=target, save=not SMOKE)
        for fs in ("CONTROLS", "FULL"):
            out.append(run(df, folds, fs, "daily", "daily_robust", target=target))

    sub = df[df["listedMethod_INTERNAL"] == 1].reset_index(drop=True)
    print(f"[subsample INTERNAL] {len(sub):,d} rows, "
          f"{sub['token_id'].nunique()} tokens")
    sub_folds = C.make_folds(sub)
    C.baselines(sub, sub_folds, freq="daily", subsample="INTERNAL", save=not SMOKE)
    for fs in ("CONTROLS", "FULL"):
        out.append(run(sub, sub_folds, fs, "daily", "daily_robust",
                       subsample="INTERNAL"))
    return pd.concat(out)


# --------------------------------------------------------------------------
def importance(df, folds, res):
    """Gain importance of the last-fold FULL (daily) model, refit with its
    tuned params. Gain is measured on the training set (how much each feature
    reduced the loss while the trees were grown), not on test."""
    feats = C.FULL
    tr = folds[-1][0]
    r = res[(res.feature_set == "FULL") & (res.freq == "daily")
            & (res.target == C.TARGETS["y"]) & (res.subsample == "all")
            & (res.fold == len(folds))]
    params = json.loads(r.iloc[0]["best_params"])
    est = lgbm_factory(**params).fit(df[feats].to_numpy(float)[tr],
                                     df["y"].to_numpy()[tr])
    gain = est.named_steps["lgbm"].booster_.feature_importance("gain")
    imp = pd.DataFrame({"feature": feats, "group": [group_of(f) for f in feats],
                        "gain": gain, "gain_share": gain / gain.sum()})
    imp = imp.sort_values("gain_share", ascending=False)
    if not SMOKE:
        imp.to_csv(C.RESULTS_DIR / "lgbm_importance.csv", index=False)
    print(f"[importance] last fold, FULL config {params}")
    print(imp.head(15).round(4).to_string(index=False))
    return imp, params


def plot_importance(imp, params):
    top = imp.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.barh(top["feature"], top["gain_share"],
            color=[GROUP_COLOR[g] for g in top["group"]], height=0.7)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("share of total split gain (training set)")
    shares = imp.groupby("group")["gain_share"].sum()
    ax.legend(handles=[Patch(color=c, label=f"{g} ({shares.get(g, 0):.0%} of gain)")
                       for g, c in GROUP_COLOR.items()],
              title="feature group", loc="lower right")
    ax.set_title("LightGBM (FULL, last fold): top 15 features by gain\n"
                 f"{json.dumps(params, sort_keys=True)}", fontsize=10)
    C.savefig(fig, "lgbm_importance.png")


# --------------------------------------------------------------------------
def main():
    t0 = time.perf_counter()
    C.set_style()
    res = main_runs()
    df = C.load_data(freq="daily", verbose=False)
    folds = C.make_folds(df, verbose=False)
    res = pd.concat([res, robustness_runs(df, folds)])
    summary = (res.groupby(["freq", "target", "subsample", "feature_set"], sort=False)
                  [["rmse", "mae", "r2_oos", "spearman"]].mean())
    print("\nLightGBM mean over folds:")
    print(summary.round(4).to_string())
    for freq in ("daily", "weekly"):
        key = (freq, C.TARGETS["y"], "all")
        a = summary.loc[key + ("CONTROLS",), "rmse"]
        c = summary.loc[key + ("FULL",), "rmse"]
        verdict = "DEGRADES" if c > a else "improves"
        print(f"[{freq}] RMSE CONTROLS {a:.4f} -> FULL {c:.4f}: adding "
              f"emission+static features {verdict} LightGBM (a result, not a bug)")
    plot_importance(*importance(df, folds, res))
    print(f"[07_lgbm] done in {(time.perf_counter() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
