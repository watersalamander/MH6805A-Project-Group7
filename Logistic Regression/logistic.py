"""
MH6805 Group 7 - Logistic Regression: probability of a high-volatility event.
Owner: Maulina Umi Rofiqoh

Run:  python logistic.py path/to/dataset_v1.csv [out_dir]

Two event definitions (both use only prices after D, like the regression targets):
  A  'top20_xs'  : rv_fwd_14d in the top 20% of all tokens on date D
                   (cross-sectional: which tokens will be the most volatile?)
  B  'spike_1.5x': rv_fwd_14d > 1.5 x rv_past_30d
                   (time-series: will this token's vol jump vs its own recent level?)
                   rv_past_30d falls back to rv_past_14d for new listings. Base rate ~13%.

Same rows, features, walk-forward folds and 30-day embargo as ridge_elasticnet.py (prep.py).
Models: naive score (rv_past_14d for A; none for B), logistic controls-only,
logistic full (controls + emission). L2 penalty, C tuned on the last 90 days of each
training window. No resampling: A has exactly 20% positives; B is mildly imbalanced and
evaluated with threshold-free metrics, so class balancing is unnecessary.
Metrics: ROC-AUC, PR-AUC (average precision), Brier, log loss, Brier skill vs the
training base rate. Incremental test: DM on daily mean log-loss differential.
Explanatory: full-sample logit (GLM binomial), standardized X, two-way clustered SE,
odds ratios per 1 SD.
"""
import sys, os, warnings
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, log_loss
import statsmodels.api as sm

from prep import load_panel, build_features, walk_forward_folds, FEATURE_SETS

warnings.filterwarnings("ignore")
DATA = sys.argv[1] if len(sys.argv) > 1 else "dataset_v1.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results_logistic"
os.makedirs(OUT, exist_ok=True)
C_GRID = [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 10]
EPS = 1e-6

df = load_panel(DATA)
Xall = build_features(df)
dates = df["date"]
folds = walk_forward_folds(dates)

rv30 = df["rv_past_30d"].fillna(df["rv_past_14d"])
q80 = df.groupby("date")["rv_fwd_14d"].transform(lambda s: s.quantile(0.8))
LABELS = {
    "top20_xs": (df["rv_fwd_14d"] > q80).astype(int).values,
    "spike_1.5x": (df["rv_fwd_14d"] > 1.5 * rv30).astype(int).values,
}
NAIVE = {"top20_xs": df["rv_past_14d"].values, "spike_1.5x": None}


def fit(C, Xtr, ytr, Xte):
    sc = StandardScaler().fit(Xtr)
    m = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(Xtr), ytr)
    return m.predict_proba(sc.transform(Xte))[:, 1], m


def tune(X, y, d):
    cut = d.max() - pd.Timedelta(days=90)
    tr = (d <= cut - pd.Timedelta(days=31)).values
    va = (d > cut).values
    best, bl = None, np.inf
    for C in C_GRID:
        p, _ = fit(C, X[tr], y[tr], X[va])
        ll = log_loss(y[va], np.clip(p, EPS, 1 - EPS))
        if ll < bl:
            best, bl = C, ll
    return best


def scores(y, p, base_rate=None, prob=True):
    out = dict(auc=roc_auc_score(y, p), pr_auc=average_precision_score(y, p),
               base_rate=y.mean())
    if prob:
        p = np.clip(p, EPS, 1 - EPS)
        out["brier"] = brier_score_loss(y, p)
        out["log_loss"] = log_loss(y, p)
        if base_rate is not None:
            b_ref = brier_score_loss(y, np.full(len(y), base_rate))
            out["brier_skill"] = 1 - out["brier"] / b_ref
    return out


def dm_test(d, lag=14):
    d = np.asarray(d); T = len(d); dc = d - d.mean()
    g = [np.sum(dc[k:] * dc[:T - k]) / T for k in range(lag + 1)]
    v = g[0] + 2 * sum((1 - k / (lag + 1)) * g[k] for k in range(1, lag + 1))
    s = d.mean() / np.sqrt(v / T)
    return s, 2 * (1 - norm.cdf(abs(s)))


rows, preds_out, coef_rows, tuned = [], [], [], []
for lab, y in LABELS.items():
    P = {m: np.full(len(df), np.nan) for m in ["naive", "logit_controls", "logit_full"]}
    base = np.full(len(df), np.nan)
    for k, s, e, tr, te in folds:
        base[te] = y[tr].mean()
        if NAIVE[lab] is not None:
            P["naive"][te] = NAIVE[lab][te]
        for name, fs in [("logit_controls", "controls"), ("logit_full", "full")]:
            X = Xall[FEATURE_SETS[fs]].values
            C = tune(X[tr], y[tr], dates.iloc[tr])
            p, m = fit(C, X[tr], y[tr], X[te])
            P[name][te] = p
            tuned.append(dict(label=lab, fold=k, model=name, C=C))
            for f, c in zip(FEATURE_SETS[fs], m.coef_[0]):
                coef_rows.append(dict(label=lab, fold=k, model=name, feature=f,
                                      coef=c, odds_ratio_per_sd=np.exp(c)))
        for name, p in P.items():
            if np.isnan(p[te]).all():
                continue
            rows.append(dict(label=lab, fold=k, test_start=s.date(), n_test=len(te),
                             model=name, **scores(y[te], p[te], y[tr].mean(),
                                                  prob=(name != "naive"))))
    idx = ~np.isnan(P["logit_full"])
    for name, p in P.items():
        if np.isnan(p[idx]).all():
            continue
        r = scores(y[idx], p[idx], None, prob=(name != "naive"))
        if name != "naive":
            r["brier_skill"] = 1 - r["brier"] / np.mean((y[idx] - base[idx]) ** 2)
        rows.append(dict(label=lab, fold="ALL", test_start=None,
                         n_test=int(idx.sum()), model=name, **r))
    pf = df.loc[idx, ["token_id", "date"]].copy()
    pf["label"], pf["y"] = lab, y[idx]
    for name, p in P.items():
        pf[f"p_{name}"] = p[idx]
    preds_out.append(pf)

res = pd.DataFrame(rows)
res.to_csv(f"{OUT}/metrics_by_fold.csv", index=False)
preds = pd.concat(preds_out)
preds.to_csv(f"{OUT}/oos_predictions.csv", index=False)
pd.DataFrame(tuned).to_csv(f"{OUT}/tuned_C.csv", index=False)
coefs = pd.DataFrame(coef_rows)
coefs.to_csv(f"{OUT}/coefs_by_fold.csv", index=False)

# --- incremental: daily mean log-loss, full vs controls
dm_rows = []
for lab, g in preds.groupby("label"):
    def ll(p): return -(g.y * np.log(np.clip(p, EPS, 1)) + (1 - g.y) * np.log(np.clip(1 - p, EPS, 1)))
    d = (ll(g.p_logit_full) - ll(g.p_logit_controls)).groupby(g.date).mean().sort_index()
    st, pv = dm_test(d.values)
    dm_rows.append(dict(label=lab, model="logit_full", vs="logit_controls",
                        mean_logloss_diff=d.mean(), dm_stat=st, p_value=pv))
dm = pd.DataFrame(dm_rows)
dm.to_csv(f"{OUT}/dm_tests.csv", index=False)

# --- explanatory odds ratios: full-sample GLM binomial, two-way clustered SE
fs = FEATURE_SETS["full"]
Xs = sm.add_constant(StandardScaler().fit_transform(Xall[fs].values))
groups = np.column_stack([pd.factorize(df.token_id)[0], pd.factorize(df.date)[0]])
expl_all = []
for lab, y in LABELS.items():
    glm = sm.GLM(y, Xs, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": groups})
    ci = glm.conf_int()
    e = pd.DataFrame({"label": lab, "feature": ["const"] + fs, "coef_std": glm.params,
                      "se_2way": glm.bse, "z": glm.tvalues, "p": glm.pvalues,
                      "odds_ratio_per_sd": np.exp(glm.params),
                      "or_ci_low": np.exp(ci[:, 0]), "or_ci_high": np.exp(ci[:, 1])})
    expl_all.append(e)
expl = pd.concat(expl_all)
expl.to_csv(f"{OUT}/odds_ratios.csv", index=False)

pd.set_option("display.width", 220)
print(f"rows={len(df):,}  base rates: " +
      ", ".join(f"{k}={v.mean():.3f}" for k, v in LABELS.items()))
print("\n=== Pooled OOS ===")
print(res[res.fold == "ALL"].drop(columns=["fold", "test_start"]).round(4).to_string(index=False))
print("\n=== AUC by fold ===")
print(res[res.fold != "ALL"].pivot(index=["label", "fold"], columns="model", values="auc").round(4))
print("\n=== DM (log loss; negative = full better) ===")
print(dm.round(4).to_string(index=False))
print("\n=== Odds ratios per 1 SD (two-way clustered) ===")
print(expl.round(4).to_string(index=False))
