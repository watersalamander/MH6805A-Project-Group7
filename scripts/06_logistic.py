"""Step 7 - Logistic regression on high-volatility events. Run from the repo root:
    python scripts/06_logistic.py
Writes results/logistic.csv (own schema, see below), results/logistic_coefs.csv,
results/preds_logistic_<label>_<fs>_<freq>.parquet and figures/logistic_auc.png.

A classification view of the same question. Two events, both defined from the
forward target (so they are labels, never inputs):
  top20_xs   rv_fwd_14d in the top 20% of all tokens on date D (cross-section:
             which tokens will be the most volatile?)
  spike_1.5x rv_fwd_14d > 1.5 x rv_past_30d (time series: will this token's vol
             jump against its own recent level?)
Labels are built on the daily panel, so the cross-sectional quantile uses every
token on that date; the weekly panel picks them up by (token_id, date).

Same rows, features, folds and tuning protocol as the regression models: C is
tuned on the validation slice (fit on train minus val minus a 30-day purge) by
log loss, the best C is refit on all of train and scored once on test.
Pipeline: common.log_transformer -> StandardScaler -> LogisticRegression (L2).

results/logistic.csv is NOT in the regression results schema (no RMSE), so
04_compare.py skips it. Columns: model, feature_set, freq, label, fold,
cutoff_date, n_train, n_test, best_params, auc, pr_auc, brier, log_loss,
brier_skill (vs the training base rate), base_rate, subsample.
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import common as C

NAME = "logistic"
C_GRID = [1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 10]
LABELS = ["top20_xs", "spike_1.5x"]
EPS = 1e-6
LOGIT_COLUMNS = ["model", "feature_set", "freq", "label", "fold", "cutoff_date",
                 "n_train", "n_test", "best_params", "auc", "pr_auc", "brier",
                 "log_loss", "brier_skill", "base_rate", "subsample"]
LOGIT_KEY = ["model", "feature_set", "freq", "label", "subsample"]


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Event labels from the forward target (daily panel)."""
    q80 = df.groupby("date")["y"].transform(lambda s: s.quantile(0.8))
    return df.assign(**{
        "top20_xs": (df["y"] > q80).astype(int),
        "spike_1.5x": (df["y"] > np.log(1.5 * df["rv_past_30d"])).astype(int)})


def logit_factory(features, C_):
    return Pipeline([("log", C.log_transformer(features)),
                     ("scale", StandardScaler()),
                     ("logit", LogisticRegression(C=C_, max_iter=2000,
                                                  random_state=C.RANDOM_STATE))])


def scores(y, p, base_rate=None, prob=True) -> dict:
    out = {"auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
           "brier": np.nan, "log_loss": np.nan, "brier_skill": np.nan,
           "base_rate": float(np.mean(y))}
    if prob:
        p = np.clip(p, EPS, 1 - EPS)
        out["brier"] = brier_score_loss(y, p)
        out["log_loss"] = log_loss(y, p, labels=[0, 1])
        if base_rate is not None:
            ref = brier_score_loss(y, np.full(len(y), base_rate))
            out["brier_skill"] = 1 - out["brier"] / ref
    return out


def run_logit(df, folds, fs, freq, label, subsample="all"):
    feats = C.FEATURE_SETS[fs]
    X, y = df[feats].to_numpy(float), df[label].to_numpy()
    rows, preds, coefs = [], [], []
    for k, (tr, va, te) in enumerate(folds, start=1):
        fit = C.fit_slice(df, tr, va)
        best = (np.inf, None)
        for c in C_GRID:
            p = logit_factory(feats, c).fit(X[fit], y[fit]).predict_proba(X[va])[:, 1]
            ll = log_loss(y[va], np.clip(p, EPS, 1 - EPS), labels=[0, 1])
            if ll < best[0]:
                best = (ll, c)
        est = logit_factory(feats, best[1]).fit(X[tr], y[tr])
        p = est.predict_proba(X[te])[:, 1]
        m = scores(y[te], p, y[tr].mean())
        rows.append({"model": NAME, "feature_set": fs, "freq": freq,
                     "label": label, "fold": k,
                     "cutoff_date": folds.cutoffs[k - 1].date().isoformat(),
                     "n_train": len(tr), "n_test": len(te),
                     "best_params": f'{{"C": {best[1]}}}', **m,
                     "subsample": subsample})
        preds.append(pd.DataFrame({"token_id": df["token_id"].to_numpy()[te],
                                   "date": df["date"].to_numpy()[te],
                                   "y_true": y[te], "p": p, "fold": k}))
        for f, c in zip(feats, est.named_steps["logit"].coef_[0]):
            coefs.append({"label": label, "feature_set": fs, "freq": freq,
                          "fold": k, "feature": f, "coef_std": c,
                          "odds_ratio_per_sd": np.exp(c)})
        print(f"[{NAME}|{label}|{fs}_{freq}] fold {k}: val logloss {best[0]:.4f} "
              f"test auc {m['auc']:.4f} brier_skill {m['brier_skill']:+.4f} "
              f"C={best[1]:g}")
    pd.concat(preds, ignore_index=True).to_parquet(
        C.RESULTS_DIR / f"preds_{NAME}_{label}_{C.run_tag(fs, freq, subsample=subsample)}.parquet",
        index=False)
    return pd.DataFrame(rows), pd.DataFrame(coefs)


def naive_rows(df, folds, freq, label, subsample="all"):
    """Rank by rv_past_14d: AUC / PR-AUC only (it is a score, not a probability).
    Only meaningful for top20_xs; spike_1.5x is relative to the token's own vol."""
    rows = []
    for k, (tr, _, te) in enumerate(folds, start=1):
        m = scores(df[label].to_numpy()[te], df["rv_past_14d"].to_numpy()[te],
                   prob=False)
        rows.append({"model": "naive_rv14", "feature_set": "NONE", "freq": freq,
                     "label": label, "fold": k,
                     "cutoff_date": folds.cutoffs[k - 1].date().isoformat(),
                     "n_train": len(tr), "n_test": len(te), "best_params": "{}",
                     **m, "subsample": subsample})
    return pd.DataFrame(rows)


def upsert(path: Path, new: pd.DataFrame) -> None:
    if path.exists():
        old = pd.read_csv(path)
        keys = set(map(tuple, new[LOGIT_KEY].astype(str).drop_duplicates().to_numpy()))
        keep = [tuple(r) not in keys for r in old[LOGIT_KEY].astype(str).to_numpy()]
        new = pd.concat([old[keep], new], ignore_index=True)
    new[LOGIT_COLUMNS].to_csv(path, index=False)


def plot_auc(res):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    sets = [("CONTROLS", "controls only", C.PALETTE[0]),
            ("FULL", "controls + emission + static (FULL)", C.PALETTE[1])]
    for ax, freq in zip(axes, ("daily", "weekly")):
        r = res[(res.freq == freq) & (res.subsample == "all")]
        x = np.arange(len(LABELS))
        for i, (fs, lab, color) in enumerate(sets):
            g = r[r.feature_set == fs].groupby("label")["auc"]
            mean, std = g.mean().reindex(LABELS), g.std().reindex(LABELS)
            ax.bar(x + (i - 0.5) * 0.38, mean, width=0.36, yerr=std, color=color,
                   label=lab, error_kw={"ecolor": C.INK_2, "elinewidth": 1})
            for xi, v in zip(x, mean):
                ax.text(xi + (i - 0.5) * 0.38, 0.505, f"{v:.3f}", ha="center",
                        va="bottom", fontsize=8, color="white", fontweight="bold")
        naive = r[r.model == "naive_rv14"].groupby("label")["auc"].mean()
        for xi, l in enumerate(LABELS):
            if l not in naive:
                continue
            ax.hlines(naive[l], xi - 0.4, xi + 0.4, color=C.INK, linestyle="--",
                      linewidth=1.2, label="rank by rv_past_14d" if xi == 0 else None)
        ax.axhline(0.5, color=C.INK_2, linestyle=":", linewidth=1)
        ax.set_ylim(0.5, None)
        ax.set_xticks(x)
        ax.set_xticklabels(LABELS)
        ax.grid(axis="x", visible=False)
        ax.set_title(f"{freq} panel", fontsize=10)
    axes[0].set_ylabel("test ROC-AUC (mean of 5 folds, bar = +/- 1 std)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, -0.08))
    fig.suptitle("Logistic regression: high-volatility events, controls only vs "
                 "FULL", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    C.savefig(fig, "logistic_auc.png")


def main():
    t0 = time.perf_counter()
    C.set_style()
    daily = add_labels(C.load_data(freq="daily"))
    weekly = C.load_data(freq="weekly").merge(
        daily[["token_id", "date"] + LABELS], on=["token_id", "date"],
        how="left", validate="one_to_one")
    assert weekly[LABELS].notna().all().all()
    print("base rates (daily): " + ", ".join(f"{l}={daily[l].mean():.3f}" for l in LABELS))

    res, coefs = [], []
    for freq, df in (("daily", daily), ("weekly", weekly)):
        folds = C.make_folds(df)
        for label in LABELS:
            if label == "top20_xs":
                res.append(naive_rows(df, folds, freq, label))
            for fs in ("CONTROLS", "FULL"):
                r, c = run_logit(df, folds, fs, freq, label)
                res.append(r)
                coefs.append(c)
    sub = daily[daily["listedMethod_INTERNAL"] == 1].reset_index(drop=True)
    sub_folds = C.make_folds(sub)
    for label in LABELS:
        if label == "top20_xs":
            res.append(naive_rows(sub, sub_folds, "daily", label, "INTERNAL"))
        for fs in ("CONTROLS", "FULL"):
            res.append(run_logit(sub, sub_folds, fs, "daily", label, "INTERNAL")[0])

    res = pd.concat(res, ignore_index=True)
    upsert(C.RESULTS_DIR / f"{NAME}.csv", res)
    coefs = pd.concat(coefs, ignore_index=True)
    coefs.to_csv(C.RESULTS_DIR / "logistic_coefs.csv", index=False)

    summary = (res.groupby(["label", "freq", "subsample", "model", "feature_set"],
                           sort=False)[["auc", "pr_auc", "brier", "log_loss",
                                        "brier_skill"]].mean())
    print("\nLogistic mean over folds:")
    print(summary.round(4).to_string())
    for label in LABELS:
        for freq in ("daily", "weekly"):
            key = (label, freq, "all", NAME)
            a = summary.loc[key + ("CONTROLS",), "log_loss"]
            c = summary.loc[key + ("FULL",), "log_loss"]
            verdict = "DEGRADES" if c > a else "improves"
            print(f"[{label}|{freq}] log loss CONTROLS {a:.4f} -> FULL {c:.4f}: "
                  f"adding emission+static features {verdict} the model")
    plot_auc(res)
    print(f"[06_logistic] done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
