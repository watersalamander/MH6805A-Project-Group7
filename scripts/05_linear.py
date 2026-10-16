"""Step 6 - Ridge and Elastic Net regression. Run from the repo root:
    python scripts/05_linear.py
Writes results/ridge.csv and results/enet.csv (+ preds/val files),
results/linear_coefs.csv and figures/linear_coefs_full.png.

Ported from a teammate's Ridge/EN script onto the shared harness: same rows,
features, folds, tuning protocol and results schema as KNN and RF. Inside each
Pipeline the volatility controls are logged (common.log_transformer, a fixed
transform) and every feature is standardized on the training slice only.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import common as C

RIDGE_GRID = {"alpha": [0.1, 1, 10, 100, 1e3, 1e4, 1e5, 1e6, 1e7]}
ENET_GRID = {"alpha": [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0],
             "l1_ratio": [0.1, 0.5, 0.9]}
MODELS = {"ridge": RIDGE_GRID, "enet": ENET_GRID}

GROUP_COLOR = {"controls": C.PALETTE[0], "emission": C.PALETTE[1],
               "static": C.PALETTE[2]}


def group_of(feature: str) -> str:
    return ("controls" if feature in C.CONTROLS else
            "emission" if feature in C.EMISSION else "static")


def linear_factory(model: str, features: list[str]):
    """estimator_factory for run_model: log -> standardize -> Ridge / EN."""
    def factory(**params) -> Pipeline:
        reg = (Ridge(**params) if model == "ridge" else
               ElasticNet(max_iter=5000, precompute=True,  # Gram matrix: n >> p, ~100x faster
                          random_state=C.RANDOM_STATE, **params))
        return Pipeline([("log", C.log_transformer(features)),
                         ("scale", StandardScaler()),
                         (model, reg)])
    return factory


def run(model, df, folds, fs, freq, **kw):
    return C.run_model(model, linear_factory(model, C.FEATURE_SETS[fs]), df,
                       folds, fs, MODELS[model], freq, **kw)


def main_runs():
    out = []
    for freq in ("daily", "weekly"):
        df = C.load_data(freq=freq)
        folds = C.make_folds(df)
        C.baselines(df, folds, freq=freq)
        for model in MODELS:
            for fs in ("CONTROLS", "FULL"):
                out.append(run(model, df, folds, fs, freq))
    return pd.concat(out)


def robustness_runs(df, folds):
    out = []
    for target in ("y_14d_parkinson", "y_7d", "y_30d"):
        C.baselines(df, folds, freq="daily", target=target)
        for model in MODELS:
            for fs in ("CONTROLS", "FULL"):
                out.append(run(model, df, folds, fs, "daily", target=target))

    sub = df[df["listedMethod_INTERNAL"] == 1].reset_index(drop=True)
    print(f"[subsample INTERNAL] {len(sub):,d} rows, "
          f"{sub['token_id'].nunique()} tokens")
    sub_folds = C.make_folds(sub)
    C.baselines(sub, sub_folds, freq="daily", subsample="INTERNAL")
    for model in MODELS:
        for fs in ("CONTROLS", "FULL"):
            out.append(run(model, sub, sub_folds, fs, "daily",
                           subsample="INTERNAL"))
    return pd.concat(out)


# --------------------------------------------------------------------------
def coefficients(df, folds, res):
    """Refit FULL (daily) with each fold's tuned params; standardized coefs."""
    feats = C.FULL
    X, y = df[feats].to_numpy(float), df["y"].to_numpy()
    rows = []
    for model in MODELS:
        r = res[(res.model == model) & (res.feature_set == "FULL")
                & (res.freq == "daily") & (res.target == C.TARGETS["y"])
                & (res.subsample == "all")].set_index("fold")
        for k, (tr, _, _) in enumerate(folds, start=1):
            params = json.loads(r.loc[k, "best_params"])
            est = linear_factory(model, feats)(**params).fit(X[tr], y[tr])
            for f, c in zip(feats, est.named_steps[model].coef_):
                rows.append({"model": model, "fold": k, "feature": f,
                             "group": group_of(f), "coef_std": c,
                             "best_params": json.dumps(params, sort_keys=True)})
    coefs = pd.DataFrame(rows)
    coefs.to_csv(C.RESULTS_DIR / "linear_coefs.csv", index=False)
    return coefs


def plot_coefs(coefs):
    agg = (coefs.groupby(["model", "feature"])["coef_std"]
                .agg(["mean", "min", "max"]).reset_index())
    order = (agg[agg.model == "ridge"].assign(a=lambda d: d["mean"].abs())
             .sort_values("a")["feature"].tolist())
    fig, axes = plt.subplots(1, 2, figsize=(13, 9), sharey=True)
    for ax, model in zip(axes, MODELS):
        a = agg[agg.model == model].set_index("feature").reindex(order)
        colors = [GROUP_COLOR[group_of(f)] for f in order]
        ax.barh(order, a["mean"], color=colors, height=0.7,
                xerr=[a["mean"] - a["min"], a["max"] - a["mean"]],
                error_kw={"ecolor": C.INK_2, "elinewidth": 1})
        ax.axvline(0, color=C.INK_2, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        n_zero = int((coefs[coefs.model == model].groupby("feature")["coef_std"]
                      .apply(lambda s: (s == 0).all())).sum())
        sub = f", {n_zero} features zeroed in every fold" if model == "enet" else ""
        ax.set_title(f"{model}: mean over 5 folds, bar = min..max{sub}",
                     fontsize=10)
        ax.set_xlabel("coefficient on standardized feature (log-vol per 1 SD)")
    axes[1].legend(handles=[Patch(color=c, label=g) for g, c in GROUP_COLOR.items()],
                   title="feature group", loc="lower right")
    fig.suptitle("Ridge and Elastic Net coefficients, FULL feature set "
                 "(daily, target log rv_fwd_14d)", x=0.01, ha="left",
                 fontweight="bold")
    fig.tight_layout()
    C.savefig(fig, "linear_coefs_full.png")


# --------------------------------------------------------------------------
def main():
    t0 = time.perf_counter()
    C.set_style()
    res = main_runs()
    df = C.load_data(freq="daily", verbose=False)
    folds = C.make_folds(df, verbose=False)
    res = pd.concat([res, robustness_runs(df, folds)])
    print("\nRidge / Elastic Net mean over folds:")
    summary = (res.groupby(["model", "freq", "target", "subsample", "feature_set"],
                           sort=False)[["rmse", "mae", "r2_oos", "spearman"]].mean())
    print(summary.round(4).to_string())
    for model in MODELS:
        for freq in ("daily", "weekly"):
            key = (model, freq, C.TARGETS["y"], "all")
            a = summary.loc[key + ("CONTROLS",), "rmse"]
            c = summary.loc[key + ("FULL",), "rmse"]
            verdict = "DEGRADES" if c > a else "improves"
            print(f"[{model}|{freq}] RMSE CONTROLS {a:.4f} -> FULL {c:.4f}: "
                  f"adding emission+static features {verdict} the model")

    coefs = coefficients(df, folds, res)
    plot_coefs(coefs)
    top = (coefs[coefs.model == "ridge"].groupby("feature")["coef_std"].mean()
           .sort_values(key=np.abs, ascending=False))
    print("\nRidge FULL, mean standardized coefficient (top 12):")
    print(top.head(12).round(4).to_string())
    print(f"[05_linear] done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
