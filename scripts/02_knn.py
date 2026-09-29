"""Step 3 - KNN regression. Run from the repo root:
    python scripts/02_knn.py
Writes results/knn.csv (+ preds/val files), results/knn_neighbours.csv and
figures/knn_*.png.
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
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer

import common as C

NAME = "knn"
FEATURE_SET_NAMES = ["CONTROLS", "CONTROLS+EMIS5", "FULL"]
PARAM_GRID = {"n_neighbors": [5, 10, 25, 50, 100, 250],
              "weights": ["uniform", "distance"]}
N_SHOWN = 15  # neighbours drawn in the illustration (the table has all k)


def knn_factory(**params) -> Pipeline:
    return Pipeline([
        ("qt", QuantileTransformer(output_distribution="normal",
                                   n_quantiles=1000,
                                   random_state=C.RANDOM_STATE)),
        ("knn", KNeighborsRegressor(algorithm="brute", n_jobs=-1, **params)),
    ])


def main():
    t0 = time.perf_counter()
    C.set_style()
    data = {}
    all_results = []
    for freq in ("daily", "weekly"):
        df = C.load_data(freq=freq)
        folds = C.make_folds(df)
        C.baselines(df, folds, freq=freq)
        data[freq] = (df, folds)
        for fs in FEATURE_SET_NAMES:
            all_results.append(
                C.run_model(NAME, knn_factory, df, folds, fs, PARAM_GRID, freq))

    res = pd.concat(all_results)
    summary = (res.groupby(["freq", "feature_set"], sort=False)
                  [["rmse", "mae", "r2_oos", "spearman"]].mean())
    print("\nKNN mean over folds:")
    print(summary.round(4).to_string())
    for freq in ("daily", "weekly"):
        a = summary.loc[(freq, "CONTROLS"), "rmse"]
        c = summary.loc[(freq, "FULL"), "rmse"]
        verdict = "DEGRADES" if c > a else "improves"
        print(f"[{freq}] RMSE CONTROLS {a:.4f} -> FULL {c:.4f}: adding "
              f"emission+static features {verdict} KNN (a result, not a bug)")

    plot_val_curve()
    neighbour_illustration(*data["daily"], res)
    print(f"[02_knn] done in {time.perf_counter() - t0:.1f}s")


def plot_val_curve():
    """Validation RMSE vs k (daily), one line per feature set. Each point is
    the mean over folds, using the better of the two weightings at that k."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, fs in enumerate(FEATURE_SET_NAMES):
        val = pd.read_csv(C.RESULTS_DIR / f"val_{NAME}_{C.run_tag(fs, 'daily')}.csv")
        curve = (val.groupby(["n_neighbors", "weights"])["val_rmse"].mean()
                    .unstack("weights").min(axis=1))
        ax.plot(curve.index, curve.values, marker="o", color=C.PALETTE[i],
                label=f"{fs} ({len(C.FEATURE_SETS[fs])} features)")
        ax.annotate(f"{curve.iloc[-1]:.3f}", (curve.index[-1], curve.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=8, color=C.INK_2)
    ax.set_xscale("log")
    ax.set_xticks(PARAM_GRID["n_neighbors"])
    ax.set_xticklabels(PARAM_GRID["n_neighbors"])
    ax.minorticks_off()
    ax.set_xlabel("k (n_neighbors, log scale)")
    ax.set_ylabel("validation RMSE, log-vol (mean of 5 folds)")
    ax.set_title("KNN: validation RMSE vs k by feature set (daily panel)")
    ax.legend(title="feature set")
    C.savefig(fig, "knn_val_rmse_vs_k.png")


def neighbour_illustration(df, folds, res, fs="CONTROLS+EMIS5"):
    """Who are the neighbours of the most unlock-heavy test row?"""
    features = C.FEATURE_SETS[fs]
    tr, _, te = folds[-1]
    row = res[(res.feature_set == fs) & (res.freq == "daily")
              & (res.fold == len(folds))].iloc[0]
    params = json.loads(row["best_params"])
    pipe = knn_factory(**params).fit(df.iloc[tr][features].to_numpy(float),
                                     df.iloc[tr]["y"].to_numpy())

    q_pos = te[np.argmax(df["emis_next_30d_pct_float"].to_numpy()[te])]
    q = df.iloc[[q_pos]]
    xq = pipe.named_steps["qt"].transform(q[features].to_numpy(float))
    dist, idx = pipe.named_steps["knn"].kneighbors(xq)
    nb = df.iloc[tr[idx[0]]]

    def table(d, role, distance):
        return pd.DataFrame({
            "role": role, "token_id": d["token_id"].values,
            "date": d["date"].dt.date.values, "distance": distance,
            "emis_next_30d_pct_float": np.expm1(d["emis_next_30d_pct_float"].values),
            "rv_past_14d": d["rv_past_14d"].values,
            "rv_fwd_14d": np.exp(d["y"].values)})

    out = pd.concat([table(q, "query", 0.0), table(nb, "neighbour", dist[0])],
                    ignore_index=True)
    pred = float(np.exp(pipe.predict(q[features].to_numpy(float))[0]))
    out["knn_pred_rv_fwd_14d"] = pred
    out.to_csv(C.RESULTS_DIR / "knn_neighbours.csv", index=False)
    print(f"\nNeighbour illustration ({fs}, fold {len(folds)}, {params}); "
          f"KNN prediction {pred:.3f} vs realized {out.loc[0, 'rv_fwd_14d']:.3f}")
    print(out.head(N_SHOWN + 1).round(4).to_string(index=False))

    shown = out.head(N_SHOWN + 1)
    labels = ["QUERY\n" + shown.loc[0, "token_id"]] + [
        f"{t}\n{d:%y-%m-%d}" for t, d in zip(shown["token_id"][1:], shown["date"][1:])]
    colors = [C.PALETTE[1]] + [C.PALETTE[0]] * (len(shown) - 1)
    panels = [("emis_next_30d_pct_float", "share of float unlocking in next 30d"),
              ("rv_past_14d", "rv_past_14d (known at D)"),
              ("rv_fwd_14d", "realized rv_fwd_14d (target, level)")]
    fig, axes = plt.subplots(3, 1, figsize=(12, 9.5), sharex=True)
    for ax, (col, title) in zip(axes, panels):
        ax.bar(range(len(shown)), shown[col], color=colors, width=0.7)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="x", visible=False)
        for x, v in enumerate(shown[col]):
            if x == 0 or col != "emis_next_30d_pct_float":
                continue
        ax.text(0, shown[col].iloc[0], f"{shown[col].iloc[0]:.2f}", ha="center",
                va="bottom", fontsize=8, color=C.INK_2)
    axes[2].axhline(pred, color=C.INK_2, linestyle="--", linewidth=1.2)
    axes[2].text(len(shown) - 0.5, pred, f"KNN prediction {pred:.2f} "
                 f"(k={params['n_neighbors']}, {params['weights']})",
                 ha="right", va="bottom", fontsize=8, color=C.INK_2)
    axes[2].set_xticks(range(len(shown)))
    axes[2].set_xticklabels(labels, fontsize=7)
    qd = shown.loc[0, "date"]
    fig.suptitle(
        f"KNN neighbours of the most unlock-heavy test row: "
        f"{shown.loc[0, 'token_id']} on {qd} (orange) vs its {len(shown) - 1} "
        f"nearest training rows (blue, nearest first)\nfeature set {fs}, "
        f"last fold", x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    C.savefig(fig, "knn_neighbour_illustration.png")


if __name__ == "__main__":
    main()
