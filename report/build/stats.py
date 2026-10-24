"""Collect every number the report and slides quote, straight from results/."""
import json
import pandas as pd

ROOT = "D:/ML-project"
REG = ["knn", "rf", "lightgbm", "ridge", "enet"]
NAMES = {"knn": "KNN", "rf": "Random Forest", "lightgbm": "LightGBM", "ridge": "Ridge", "enet": "Elastic Net",
         "persistence": "Persistence", "train_mean": "Train mean"}


def load():
    d = pd.concat([pd.read_csv(f"{ROOT}/results/{m}.csv") for m in REG + ["baselines"]])
    return d


def summary(d, freq="daily", target="log_rv_fwd_14d", sub="all"):
    x = d[(d.freq == freq) & (d.target == target) & (d.subsample == sub)]
    out = {}
    for m in REG:
        xm = x[x.model == m]
        if xm.empty:
            continue
        p = xm.pivot_table(index="fold", columns="feature_set", values=["r2_oos", "rmse", "spearman"])
        row = {}
        for fs in ["CONTROLS", "FULL", "CONTROLS+EMIS5"]:
            if ("r2_oos", fs) in p.columns:
                row[fs] = {k: p[(k, fs)].mean() for k in ["r2_oos", "rmse", "spearman"]}
                row[fs]["r2_std"] = p[("r2_oos", fs)].std()
        if "CONTROLS" in row and "FULL" in row:
            dl = p[("r2_oos", "FULL")] - p[("r2_oos", "CONTROLS")]
            row["delta"] = dl.mean()
            row["delta_folds"] = dl.tolist()
            row["wins"] = int((dl > 0).sum())
        out[m] = row
    for b in ["persistence", "train_mean"]:
        xb = x[x.model == b]
        out[b] = {"r2_oos": xb.r2_oos.mean(), "rmse": xb.rmse.mean(), "r2_std": xb.r2_oos.std()}
    return out


def folds(d):
    x = d[(d.model == "persistence") & (d.freq == "daily") & (d.target == "log_rv_fwd_14d") & (d.subsample == "all")]
    return x[["fold", "cutoff_date", "n_train", "n_test"]].sort_values("fold").values.tolist()


def best_params(d, m, fs):
    x = d[(d.model == m) & (d.feature_set == fs) & (d.freq == "daily") & (d.target == "log_rv_fwd_14d") & (d.subsample == "all")]
    return [json.loads(s) for s in x.sort_values("fold").best_params]


def rf_groups():
    p = pd.read_csv(f"{ROOT}/results/rf_permutation_importance.csv")
    p = p[p.model_variant == "FULL"]
    return p.groupby("group").perm_importance_mean.sum().to_dict(), p.sort_values("perm_importance_mean", ascending=False)


D = load()
MAIN = summary(D)
WEEKLY = summary(D, freq="weekly")
INTERNAL = summary(D, sub="INTERNAL")
TARGETS = {t: summary(D, target=t) for t in ["log_rv_fwd_7d", "log_rv_fwd_30d", "log_rv_fwd_14d_parkinson"]}
FOLDS = folds(D)
RFG, RFIMP = rf_groups()
LGBG = pd.read_csv(f"{ROOT}/results/lgbm_importance.csv").groupby("group").gain_share.sum().to_dict()


def errors():
    g = pd.read_csv(f"{ROOT}/results/error_by_group.csv")
    lv = pd.read_csv(f"{ROOT}/results/error_level_summary.csv").set_index("forecast")
    bm = pd.read_csv(f"{ROOT}/results/error_big_misses.csv").set_index("rows")
    return g, lv, bm


ERR_G, ERR_LV, ERR_BM = errors()

if __name__ == "__main__":
    for k, v in MAIN.items():
        print(k, v)
    print(WEEKLY["ridge"], WEEKLY["knn"])
    print({t: {m: round(TARGETS[t][m].get("delta", float("nan")), 4) for m in REG if m in TARGETS[t]} for t in TARGETS})
    print({m: round(INTERNAL[m].get("delta", float("nan")), 4) for m in REG if m in INTERNAL})
    print(RFG)
