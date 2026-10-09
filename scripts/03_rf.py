"""Step 4 - Random Forest. Run from the repo root:
    python scripts/03_rf.py                 # everything (slow, see timings)
    python scripts/03_rf.py --skip-runs     # only importances / PDP figures,
                                            # reusing best params in results/rf.csv
    RF_SMOKE=1 python scripts/03_rf.py      # tiny forests, nothing saved to
                                            # results/rf.csv (code check only)

Tuning budget. A 400-tree forest on the daily panel takes 20-90 s per fit, so
the full 36-config grid x 5 folds is ~45 min per run. Following the project
rule ("subsample the grid search rather than drop the protocol") the daily
runs evaluate a fixed, seeded random subset of the grid; weekly runs use the
full grid. The fold protocol itself is unchanged.
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
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.pipeline import Pipeline

import common as C

NAME = "rf"
SMOKE = os.environ.get("RF_SMOKE") == "1"
N_TREES = 30 if SMOKE else 400
PARAM_GRID = {"max_depth": [None, 8, 12, 16],
              "min_samples_leaf": [20, 50, 100],
              "max_features": ["sqrt", 0.33, 0.5]}
# configs evaluated per fold (None = full grid of 36)
BUDGET = {"daily_main": 12, "daily_robust": 6, "weekly": None}
if SMOKE:
    BUDGET = {k: 2 for k in BUDGET}

GROUP_COLOR = {"controls": C.PALETTE[0], "emission": C.PALETTE[1],
               "static": C.PALETTE[2]}


def group_of(feature: str) -> str:
    return ("controls" if feature in C.CONTROLS else
            "emission" if feature in C.EMISSION else "static")


def rf_factory(**params) -> Pipeline:
    # trees need no scaling; the Pipeline wrapper keeps the harness contract
    return Pipeline([("rf", RandomForestRegressor(
        n_estimators=N_TREES, n_jobs=-1, random_state=C.RANDOM_STATE, **params))])


def run(df, folds, fs, freq, budget, **kw):
    return C.run_model(NAME, rf_factory, df, folds, fs, PARAM_GRID, freq,
                       max_configs=BUDGET[budget], save=not SMOKE, **kw)


# --------------------------------------------------------------------------
def main_runs():
    out = []
    for freq in ("weekly", "daily"):
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
        out.append(run(df, folds, "FULL", "daily", "daily_robust", target=target))

    sub = df[df["listedMethod_INTERNAL"] == 1].reset_index(drop=True)
    print(f"[subsample INTERNAL] {len(sub):,d} rows, "
          f"{sub['token_id'].nunique()} tokens")
    sub_folds = C.make_folds(sub)
    C.baselines(sub, sub_folds, freq="daily", subsample="INTERNAL", save=not SMOKE)
    # controls-only on the same subsample, so the FULL number has a reference
    for fs in ("CONTROLS", "FULL"):
        out.append(run(sub, sub_folds, fs, "daily", "daily_robust",
                       subsample="INTERNAL"))
    return pd.concat(out)


# --------------------------------------------------------------------------
def importances(est, X_te, y_te, features, variant):
    pi = permutation_importance(est, X_te, y_te, n_repeats=10,
                                random_state=C.RANDOM_STATE,
                                scoring="neg_root_mean_squared_error")
    return pd.DataFrame({
        "model_variant": variant, "feature": features,
        "group": [group_of(f) for f in features],
        "perm_importance_mean": pi.importances_mean,
        "perm_importance_std": pi.importances_std,
        "impurity_importance": est.named_steps["rf"].feature_importances_,
    }).sort_values("perm_importance_mean", ascending=False)


def interpret(df, folds, params):
    tr, _, te = folds[-1]
    y = df["y"].to_numpy()
    print(f"[interpret] last fold, FULL config {params}")

    fitted, imps = {}, []
    for variant in ("FULL", "FULL_NO_AGG30"):
        feats = C.FEATURE_SETS[variant]
        t0 = time.perf_counter()
        X = df[feats].to_numpy(float)
        est = rf_factory(**params).fit(X[tr], y[tr])
        rmse = float(np.sqrt(np.mean((y[te] - est.predict(X[te])) ** 2)))
        imps.append(importances(est, X[te], y[te], feats, variant))
        fitted[variant] = (est, X)
        print(f"[interpret] {variant}: test rmse {rmse:.4f} "
              f"({time.perf_counter() - t0:.1f}s incl. permutation importance)")
    imp = pd.concat(imps, ignore_index=True)
    imp.to_csv(C.RESULTS_DIR / "rf_permutation_importance.csv", index=False)
    full = imp[imp.model_variant == "FULL"]
    print(full.head(15).round(5).to_string(index=False))

    plot_importance(full)
    plot_recipient_split(imp)
    plot_pdp(*fitted["FULL"], te)


def plot_importance(full):
    top = full.head(15).iloc[::-1]
    colors = [GROUP_COLOR[g] for g in top["group"]]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5), sharey=True)
    axes[0].barh(top["feature"], top["perm_importance_mean"],
                 xerr=top["perm_importance_std"], color=colors, height=0.7,
                 error_kw={"ecolor": C.INK_2, "elinewidth": 1})
    axes[0].axvline(0, color=C.INK_2, linewidth=0.8)
    axes[0].set_title("Permutation importance on the TEST set\n"
                      "(increase in RMSE when shuffled, 10 repeats)", fontsize=10)
    axes[0].set_xlabel("increase in test RMSE (log-vol)")
    axes[1].barh(top["feature"], top["impurity_importance"], color=colors,
                 height=0.7)
    axes[1].set_title("Impurity importance (training set)\n"
                      "same features, same order", fontsize=10)
    axes[1].set_xlabel("share of impurity reduction")
    for ax in axes:
        ax.grid(axis="y", visible=False)
    axes[1].legend(handles=[Patch(color=c, label=g) for g, c in GROUP_COLOR.items()],
                   title="feature group", loc="lower right")
    fig.suptitle("Random Forest (FULL, last fold): top 15 features by "
                 "permutation importance", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    C.savefig(fig, "rf_permutation_importance_top15.png")


def plot_recipient_split(imp):
    piv = (imp[imp.feature.isin(C.EMISSION_BUCKETS + ["emis_next_30d_pct_float"])]
           .pivot(index="feature", columns="model_variant",
                  values=["perm_importance_mean", "perm_importance_std"]))
    order = ["emis_next_30d_pct_float"] + C.EMISSION_BUCKETS
    piv = piv.reindex(order)
    labels = ["aggregate\n(all recipients)"] + C.BUCKETS
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, (variant, label) in enumerate(
            [("FULL", "FULL (aggregate included)"),
             ("FULL_NO_AGG30", "recipient split (aggregate removed)")]):
        ax.bar(x + (i - 0.5) * 0.38, piv[("perm_importance_mean", variant)],
               yerr=piv[("perm_importance_std", variant)], width=0.36,
               color=C.PALETTE[i], label=label,
               error_kw={"ecolor": C.INK_2, "elinewidth": 1})
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("permutation importance\n(increase in test RMSE, log-vol)")
    ax.set_xlabel("emis_next_30d_<recipient>_pct_float")
    ax.set_title("Permutation importance of 30-day emission by recipient "
                 "(RF, last fold)", fontsize=11)
    ax.legend()
    C.savefig(fig, "rf_recipient_split_importance.png")
    print(piv["perm_importance_mean"].round(5).to_string())


def plot_pdp(est, X, te):
    feats = C.FULL
    i_e, i_b = feats.index("emis_next_30d_pct_float"), feats.index("btc_rv_past_14d")
    rng = np.random.default_rng(C.RANDOM_STATE)
    Xs = X[np.sort(rng.choice(te, size=min(3000, len(te)), replace=False))]

    pd1 = partial_dependence(est, Xs, [i_e], percentiles=(0, 0.99),
                             grid_resolution=40, kind="average")
    gx = np.expm1(pd1["grid_values"][0])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(gx * 100, pd1["average"][0], color=C.PALETTE[0])
    deciles = np.expm1(np.quantile(X[te, i_e], np.linspace(0.1, 0.9, 9))) * 100
    ax.plot(deciles, np.full(9, ax.get_ylim()[0]), "|", color=C.INK_2,
            markersize=12, clip_on=False)
    ax.set_xlabel("share of float unlocking in the next 30 days, % "
                  "(ticks at the bottom = test-set deciles)")
    ax.set_ylabel("partial dependence: predicted log(rv_fwd_14d)")
    span = pd1["average"][0].max() - pd1["average"][0].min()
    ax.set_title("RF partial dependence on 30-day unlock pressure (FULL, last "
                 f"fold)\ntotal range of the curve: {span:.3f} log-vol",
                 fontsize=11)
    C.savefig(fig, "rf_pdp_emis30.png")

    pd2 = partial_dependence(est, Xs, [(i_e, i_b)], percentiles=(0, 0.99),
                             grid_resolution=20, kind="average")
    ge, gb = pd2["grid_values"]
    cmap = LinearSegmentedColormap.from_list(
        "seq", ["#cde2fb", "#6da7ec", "#2a78d6", "#0d366b"])
    fig, ax = plt.subplots(figsize=(9, 6))
    cs = ax.contourf(np.expm1(ge) * 100, gb, pd2["average"][0].T, levels=12,
                     cmap=cmap)
    ax.contour(np.expm1(ge) * 100, gb, pd2["average"][0].T, levels=12,
               colors=C.SURFACE, linewidths=0.5)
    fig.colorbar(cs, ax=ax, label="predicted log(rv_fwd_14d)")
    ax.grid(False)
    ax.set_xlabel("share of float unlocking in the next 30 days, %")
    ax.set_ylabel("btc_rv_past_14d (market vol regime)")
    ax.set_title("RF 2-D partial dependence: unlock pressure x BTC vol regime",
                 fontsize=11)
    C.savefig(fig, "rf_pdp_emis30_x_btc.png")


# --------------------------------------------------------------------------
def main():
    t0 = time.perf_counter()
    C.set_style()
    skip = "--skip-runs" in sys.argv
    if not skip:
        res = main_runs()
    df = C.load_data(freq="daily", verbose=False)
    folds = C.make_folds(df, verbose=False)
    if not skip:
        res = pd.concat([res, robustness_runs(df, folds)])
        print("\nRF mean over folds:")
        print(res.groupby(["freq", "target", "subsample", "feature_set"], sort=False)
                 [["rmse", "mae", "r2_oos", "spearman"]].mean().round(4).to_string())
    else:
        res = pd.read_csv(C.RESULTS_DIR / f"{NAME}.csv")

    best = res[(res.feature_set == "FULL") & (res.freq == "daily")
               & (res.target == C.TARGETS["y"]) & (res.subsample == "all")
               & (res.fold == len(folds))]
    interpret(df, folds, json.loads(best.iloc[0]["best_params"]))
    print(f"[03_rf] done in {(time.perf_counter() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
