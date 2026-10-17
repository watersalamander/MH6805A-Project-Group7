"""
MH6805 Group 7 - Ridge / Elastic-Net forecasts of forward realized volatility.
Owner: Maulina Umi Rofiqoh

Run:  python ridge_elasticnet.py path/to/dataset_v1.csv  [out_dir]

What it does
  1. Target y = log(rv_fwd_14d) (plus robustness targets).
  2. Walk-forward (6 expanding folds, 30-day embargo), features scaled inside each fold.
  3. Hyper-parameters tuned inside each training window on its last 90 days
     (with its own 30-day embargo) - no peeking at the test fold.
  4. Models: naive persistence, Ridge (controls only), Ridge (full), Elastic-Net (full).
  5. Metrics: RMSE / MAE on log vol, OOS R^2 vs persistence, Spearman.
     Incremental test: Diebold-Mariano on daily mean squared-error differential
     (full vs controls), Newey-West HAC.
  6. Explanatory table: full-sample OLS on standardized features with
     two-way (token, date) clustered SEs, plus Ridge/EN coefficients per fold.
"""
import sys, os, json, warnings
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, norm
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.preprocessing import StandardScaler
import statsmodels.api as sm

from prep import load_panel, build_features, walk_forward_folds, FEATURE_SETS

warnings.filterwarnings("ignore")
DATA = sys.argv[1] if len(sys.argv) > 1 else "dataset_v1.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results_ridge_en"
os.makedirs(OUT, exist_ok=True)

RIDGE_ALPHAS = [1, 10, 100, 1e3, 1e4, 3e4, 1e5, 3e5, 1e6]
EN_ALPHAS = [1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3]
EN_L1 = [0.1, 0.5, 0.9]
TARGETS = {"rv_fwd_14d": "rv_past_14d", "rv_fwd_7d": "rv_past_7d",
           "rv_fwd_30d": "rv_past_30d", "rv_fwd_14d_parkinson": "rv_past_14d"}


def metrics(y, p, p_naive):
    sse, sse_n = np.sum((y - p) ** 2), np.sum((y - p_naive) ** 2)
    return dict(rmse=np.sqrt(np.mean((y - p) ** 2)),
                mae=np.mean(np.abs(y - p)),
                r2_oos_vs_persistence=1 - sse / sse_n,
                spearman=spearmanr(y, p)[0])


def fit_predict(model, Xtr, ytr, Xte):
    sc = StandardScaler().fit(Xtr)
    model.fit(sc.transform(Xtr), ytr)
    return model.predict(sc.transform(Xte)), model, sc


def tune(kind, X, y, dates):
    """Pick hyper-params on the last 90 days of the training window."""
    cut = dates.max() - pd.Timedelta(days=90)
    tr = (dates <= cut - pd.Timedelta(days=31)).values
    va = (dates > cut).values
    grid = ([dict(alpha=a) for a in RIDGE_ALPHAS] if kind == "ridge" else
            [dict(alpha=a, l1_ratio=l) for a in EN_ALPHAS for l in EN_L1])
    best, best_mse = None, np.inf
    for g in grid:
        m = Ridge(**g) if kind == "ridge" else ElasticNet(max_iter=5000, **g)
        p, _, _ = fit_predict(m, X[tr], y[tr], X[va])
        mse = np.mean((y[va] - p) ** 2)
        if mse < best_mse:
            best, best_mse = g, mse
    return best


def dm_test(loss_diff_by_date):
    """Diebold-Mariano with Newey-West HAC (lag = 14 for overlapping 14d targets)."""
    d = np.asarray(loss_diff_by_date)
    T, lag = len(d), 14
    dc = d - d.mean()
    gamma = [np.sum(dc[k:] * dc[:T - k]) / T for k in range(lag + 1)]
    var = gamma[0] + 2 * sum((1 - k / (lag + 1)) * gamma[k] for k in range(1, lag + 1))
    stat = d.mean() / np.sqrt(var / T)
    return stat, 2 * (1 - norm.cdf(abs(stat)))


# ====================================================================== run
df = load_panel(DATA)
Xall = build_features(df)
dates = df["date"]
folds = walk_forward_folds(dates)
print(f"rows={len(df):,} tokens={df.token_id.nunique()} features(full)={len(FEATURE_SETS['full'])}")

summary_rows, pred_frames, coef_rows, tuned_rows = [], [], [], []

for target, past in TARGETS.items():
    ok = df[past].notna().values
    y_all = np.log(df[target].values)
    naive_all = np.log(df[past].fillna(df["rv_past_14d"]).values)
    preds = {m: np.full(len(df), np.nan) for m in
             ["persistence", "ridge_controls", "ridge_full", "en_full"]}
    for k, s, e, tr, te in folds:
        tr, te = tr[ok[tr]], te[ok[te]]
        preds["persistence"][te] = naive_all[te]
        for name, fs, kind in [("ridge_controls", "controls", "ridge"),
                               ("ridge_full", "full", "ridge"),
                               ("en_full", "full", "en")]:
            X = Xall[FEATURE_SETS[fs]].values
            hp = tune(kind, X[tr], y_all[tr], dates.iloc[tr])
            m = Ridge(**hp) if kind == "ridge" else ElasticNet(max_iter=5000, **hp)
            p, m, sc = fit_predict(m, X[tr], y_all[tr], X[te])
            preds[name][te] = p
            tuned_rows.append(dict(target=target, fold=k, model=name, **hp))
            if target == "rv_fwd_14d":
                for f, c in zip(FEATURE_SETS[fs], m.coef_):
                    coef_rows.append(dict(fold=k, model=name, feature=f, coef=c))
        # per-fold metrics
        for name, p in preds.items():
            mm = metrics(y_all[te], p[te], naive_all[te])
            summary_rows.append(dict(target=target, fold=k, test_start=s.date(),
                                     n_test=len(te), n_train=len(tr), model=name, **mm))
    # pooled OOS metrics
    idx = ~np.isnan(preds["ridge_full"])
    for name, p in preds.items():
        mm = metrics(y_all[idx], p[idx], naive_all[idx])
        summary_rows.append(dict(target=target, fold="ALL", test_start=None,
                                 n_test=int(idx.sum()), n_train=None, model=name, **mm))
    pf = df.loc[idx, ["token_id", "date"]].copy()
    pf["target"], pf["y_log"] = target, y_all[idx]
    for name, p in preds.items():
        pf[f"pred_{name}"] = p[idx]
    pred_frames.append(pf)

summary = pd.DataFrame(summary_rows)
preds_df = pd.concat(pred_frames)
summary.to_csv(f"{OUT}/metrics_by_fold.csv", index=False)
preds_df.to_csv(f"{OUT}/oos_predictions.csv", index=False)
pd.DataFrame(tuned_rows).to_csv(f"{OUT}/tuned_hyperparams.csv", index=False)
coefs = pd.DataFrame(coef_rows)
coefs.to_csv(f"{OUT}/coefs_by_fold.csv", index=False)

# ---- incremental-information tests (DM) per target
dm_rows = []
for target, g in preds_df.groupby("target"):
    for a, b in [("ridge_full", "ridge_controls"), ("en_full", "ridge_controls"),
                 ("ridge_controls", "persistence"), ("ridge_full", "persistence")]:
        ld = ((g.y_log - g[f"pred_{a}"]) ** 2 - (g.y_log - g[f"pred_{b}"]) ** 2)
        daily = ld.groupby(g.date).mean().sort_index()
        stat, p = dm_test(daily.values)
        dm_rows.append(dict(target=target, model=a, vs=b,
                            mean_loss_diff=daily.mean(), dm_stat=stat, p_value=p))
dm = pd.DataFrame(dm_rows)
dm.to_csv(f"{OUT}/dm_tests.csv", index=False)

# ---- explanatory: full-sample OLS, standardized X, two-way clustered SE
fs = FEATURE_SETS["full"]
Xs = StandardScaler().fit_transform(Xall[fs].values)
y = np.log(df["rv_fwd_14d"].values)
groups = np.column_stack([pd.factorize(df.token_id)[0], pd.factorize(df.date)[0]])
ols = sm.OLS(y, sm.add_constant(Xs)).fit(cov_type="cluster", cov_kwds={"groups": groups})
expl = pd.DataFrame({"feature": ["const"] + fs, "coef_std": ols.params,
                     "se_2way": ols.bse, "t": ols.tvalues, "p": ols.pvalues})
# ridge/EN fold-average coefficients next to OLS
for name in ["ridge_full", "en_full"]:
    avg = coefs[coefs.model == name].groupby("feature").coef.agg(["mean", "std"])
    expl = expl.merge(avg.rename(columns={"mean": f"{name}_mean", "std": f"{name}_sd"}),
                      left_on="feature", right_index=True, how="left")
expl.to_csv(f"{OUT}/explanatory_coefficients.csv", index=False)

pd.set_option("display.width", 200)
print("\n=== Pooled OOS (all folds) ===")
print(summary[summary.fold == "ALL"].drop(columns=["fold", "test_start", "n_train"])
      .round(4).to_string(index=False))
print("\n=== rv_fwd_14d by fold: OOS R^2 vs persistence ===")
print(summary[(summary.target == "rv_fwd_14d") & (summary.fold != "ALL")]
      .pivot(index=["fold", "test_start", "n_test"], columns="model",
             values="r2_oos_vs_persistence").round(4))
print("\n=== Diebold-Mariano (negative = first model better) ===")
print(dm.round(4).to_string(index=False))
print("\n=== Explanatory (rv_fwd_14d, standardized) ===")
print(expl.round(4).to_string(index=False))
print(f"\nOLS R^2 in-sample = {ols.rsquared:.4f}")
