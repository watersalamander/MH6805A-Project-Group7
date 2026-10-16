"""Shared harness for the MH6805 token-unlock volatility project.

Everything a model script needs lives here: data cleaning, feature sets,
walk-forward folds, metrics, baselines and the generic tune/refit/predict loop.

Rules baked into this module (see CLAUDE.md):
  * rows are never shuffled; every split is by calendar date
  * targets are forward-looking and never enter the feature matrix
  * anything that is *fit* (scalers, encoders, models) is fit on the training
    slice of the current fold only -- put it inside the Pipeline returned by
    your estimator_factory
"""
from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RANDOM_STATE = 42

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "dataset_v1.csv"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"

# --------------------------------------------------------------------------
# Column bookkeeping
# --------------------------------------------------------------------------
BUCKETS = ["founderTeam", "privateInvestors", "community",
           "publicInvestors", "reserve", "others"]

RAW_TARGETS = ["rv_fwd_7d", "rv_fwd_14d", "rv_fwd_30d",
               "rv_fwd_14d_parkinson", "fwd_ret_14d"]

# cleaned target column -> tag written to the `target` column of results CSVs
TARGETS = {
    "y": "log_rv_fwd_14d",
    "y_7d": "log_rv_fwd_7d",
    "y_30d": "log_rv_fwd_30d",
    "y_14d_parkinson": "log_rv_fwd_14d_parkinson",
}
_TARGET_SOURCE = {
    "y": "rv_fwd_14d",
    "y_7d": "rv_fwd_7d",
    "y_30d": "rv_fwd_30d",
    "y_14d_parkinson": "rv_fwd_14d_parkinson",
}

# persistence benchmark used in r2_oos, for every target
PERSIST_COL = "rv_past_14d"

LISTED_METHODS = ["INTERNAL", "AI", "EXTERNAL"]
PRECISION_ORDER = ["second", "hour", "block", "day", "week", "month", "unknown"]

RAW_EMIS_COUNT_COLS = (["emis_next_7d", "emis_next_30d", "emis_next_90d"]
                       + [f"emis_next_30d_{b}" for b in BUCKETS]
                       + ["emis_next_30d_unattributed"])
DROP_COLS = (["symbol", "tge_proxy_date", "total_supply_basis", "total_supply",
              "float_pit", "listedMethod", "unlockPrecision"]
             + RAW_EMIS_COUNT_COLS + RAW_TARGETS)

# --------------------------------------------------------------------------
# Feature sets (names are the column names AFTER load_data cleaning)
# --------------------------------------------------------------------------
CONTROLS = ["rv_past_7d", "rv_past_14d", "rv_past_30d", "ret_past_7d",
            "ret_past_30d", "btc_rv_past_14d", "eth_rv_past_14d",
            "log_mcap_pit", "days_since_tge"]

EMISSION_BUCKETS = [f"emis_next_30d_{b}_pct_float" for b in BUCKETS]
EMISSION = (["emis_next_7d_pct_float", "emis_next_30d_pct_float",
             "emis_next_90d_pct_float", "emis_next_30d_pct_total",
             "days_to_next_cliff", "next_cliff_pct_float", "has_unlock_events"]
            + EMISSION_BUCKETS)

STATIC = ([f"alloc_share_{b}" for b in BUCKETS]
          + [f"listedMethod_{m}" for m in LISTED_METHODS]
          + ["unlockPrecision_ord"])

FULL = CONTROLS + EMISSION + STATIC

EMIS5 = ["emis_next_30d_pct_float", "emis_next_7d_pct_float",
         "next_cliff_pct_float", "days_to_next_cliff", "has_unlock_events"]

FEATURE_SETS: dict[str, list[str]] = {
    "CONTROLS": CONTROLS,
    "EMISSION": EMISSION,
    "STATIC": STATIC,
    "FULL": FULL,
    "CONTROLS+EMIS5": CONTROLS + EMIS5,
    # recipient-split variant: the six bucket columns carry the 30d signal
    "FULL_NO_AGG30": [c for c in FULL if c != "emis_next_30d_pct_float"],
}


def register_feature_set(name: str, columns: list[str]) -> None:
    """Add a named feature set so run_model can look it up."""
    missing = [c for c in columns if c not in _cleaned_columns()]
    if missing:
        raise KeyError(f"feature set {name!r}: unknown columns {missing}")
    FEATURE_SETS[name] = list(columns)


def _cleaned_columns(path: Path = DATA_PATH) -> set[str]:
    """Column names load_data will produce, derived from the CSV header only."""
    raw = list(pd.read_csv(path, nrows=0).columns)
    cols = [c for c in raw if c not in DROP_COLS]
    cols += list(TARGETS)
    cols += EMISSION_BUCKETS
    cols += [f"listedMethod_{m}" for m in LISTED_METHODS]
    cols += ["unlockPrecision_ord"]
    return set(cols)


def _verify_feature_sets() -> None:
    have = _cleaned_columns()
    for name, cols in FEATURE_SETS.items():
        missing = [c for c in cols if c not in have]
        if missing:
            raise KeyError(f"feature set {name}: columns missing from "
                           f"{DATA_PATH.name} after cleaning: {missing}")
        dupes = {c for c in cols if cols.count(c) > 1}
        if dupes:
            raise ValueError(f"feature set {name}: duplicated columns {dupes}")
        leaked = [c for c in cols if c in RAW_TARGETS or c in TARGETS]
        if leaked:
            raise ValueError(f"feature set {name} contains targets: {leaked}")


_verify_feature_sets()


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def load_data(path=DATA_PATH, freq: str = "daily", verbose: bool = True) -> pd.DataFrame:
    """Load and clean the panel. Returns token_id, date, targets and features,
    sorted by (token_id, date) with a fresh 0..n-1 index. Never shuffled."""
    if freq not in ("daily", "weekly"):
        raise ValueError("freq must be 'daily' or 'weekly'")

    def log(step, before, after):
        if verbose:
            print(f"[load_data] {step:<44s} rows {before:>7,d} -> {after:>7,d}")

    df = pd.read_csv(path)
    n0 = len(df)

    # 1. parse date, sort
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["token_id", "date"], kind="stable").reset_index(drop=True)
    log("1 parse date, sort (token_id, date)", n0, len(df))

    # 2. drop rows without target / 30d history
    n = len(df)
    df = df[df["rv_fwd_14d"].notna() & df["rv_past_30d"].notna()].copy()
    log("2 drop null rv_fwd_14d / rv_past_30d", n, len(df))

    # 3. log targets
    for new, src in _TARGET_SOURCE.items():
        df[new] = np.log(df[src])

    # 4. log1p the long-tailed pct_float columns (nulls stay null until step 5)
    pct_float_cols = [c for c in df.columns
                      if c.startswith("emis_next_") and c.endswith("_pct_float")]
    for c in pct_float_cols + ["next_cliff_pct_float"]:
        df[c] = np.log1p(df[c])

    # 5. structural nulls (tokens without cliffs / no cliff left in window)
    df["days_to_next_cliff"] = df["days_to_next_cliff"].fillna(365)
    df["next_cliff_pct_float"] = df["next_cliff_pct_float"].fillna(0.0)

    # 6. recipient buckets as share of float, log1p
    for b in BUCKETS:
        df[f"emis_next_30d_{b}_pct_float"] = np.log1p(
            df[f"emis_next_30d_{b}"] / df["float_pit"])

    # 7. encodings with fixed category lists (nothing is learned from data)
    unknown_lm = set(df["listedMethod"].dropna().unique()) - set(LISTED_METHODS)
    if unknown_lm:
        raise ValueError(f"unexpected listedMethod values: {unknown_lm}")
    for m in LISTED_METHODS:
        df[f"listedMethod_{m}"] = (df["listedMethod"] == m).astype(int)
    prec = df["unlockPrecision"].fillna("unknown")
    unknown_p = set(prec.unique()) - set(PRECISION_ORDER)
    if unknown_p:
        raise ValueError(f"unexpected unlockPrecision values: {unknown_p}")
    df["unlockPrecision_ord"] = prec.map(
        {p: i for i, p in enumerate(PRECISION_ORDER)}).astype(int)
    for c in ["has_unlock_events", "emission_schedule_ended"]:
        df[c] = df[c].astype(int)

    # 8. drop identifiers, raw token counts and every raw target
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])

    # 9. weekly: first available day of each ISO week per token
    if freq == "weekly":
        n = len(df)
        iso = df["date"].dt.isocalendar()
        df = (df.assign(_y=iso["year"].values, _w=iso["week"].values)
                .groupby(["token_id", "_y", "_w"], sort=False, as_index=False)
                .head(1)
                .drop(columns=["_y", "_w"]))
        log("9 weekly: first day of ISO week per token", n, len(df))

    df = df.sort_values(["token_id", "date"], kind="stable").reset_index(drop=True)

    nulls = df[FULL + list(TARGETS)].isna().sum()
    if nulls.any():
        raise ValueError(f"nulls remain after cleaning:\n{nulls[nulls > 0]}")

    lead = ["token_id", "date"] + list(TARGETS)
    df = df[lead + [c for c in df.columns if c not in lead]]
    if verbose:
        print(f"[load_data] freq={freq}: {len(df):,d} rows, "
              f"{df['token_id'].nunique()} tokens, "
              f"{df['date'].min().date()} .. {df['date'].max().date()}")
    return df


# --------------------------------------------------------------------------
# Walk-forward folds
# --------------------------------------------------------------------------
def make_folds(df: pd.DataFrame, n_folds: int = 5, test_days: int = 90,
               embargo_days: int = 30, val_days: int = 90, verbose: bool = True):
    """Walk-forward folds by date, all tokens pooled.

    Returns a list of (train_idx, val_idx, test_idx) positional index arrays.
    val_idx is the last `val_days` of train and is a subset of train_idx.
    Cutoff dates are stored on the returned list as `.cutoffs`.
    """
    dates = df["date"].to_numpy()
    max_date = df["date"].max()
    day = pd.Timedelta(days=1)
    folds = FoldList()
    for i in range(n_folds):
        c = max_date - (n_folds - i) * test_days * day
        train_end = c - embargo_days * day
        val_start = train_end - val_days * day  # val = (val_start, train_end]
        train_mask = dates <= train_end.to_datetime64()
        val_mask = train_mask & (dates > val_start.to_datetime64())
        test_mask = (dates > c.to_datetime64()) & \
                    (dates <= (c + test_days * day).to_datetime64())
        tr, va, te = (np.flatnonzero(m) for m in (train_mask, val_mask, test_mask))
        if min(len(tr) - len(va), len(va), len(te)) <= 0:
            raise ValueError(f"fold {i + 1} has an empty slice; "
                             "reduce n_folds/test_days/val_days")

        # no test row within embargo_days after any train row
        gap = (dates[te].min() - dates[tr].max()) / np.timedelta64(1, "D")
        assert gap > embargo_days, f"fold {i + 1}: embargo violated (gap {gap}d)"
        assert not np.intersect1d(tr, te).size
        assert np.isin(va, tr).all()

        folds.append((tr, va, te))
        folds.cutoffs.append(c)
        if verbose:
            d = lambda ix: f"{pd.Timestamp(dates[ix].min()).date()}..{pd.Timestamp(dates[ix].max()).date()}"
            print(f"[make_folds] fold {i + 1} cutoff {c.date()} | "
                  f"train {len(tr):>6,d} {d(tr)} | "
                  f"val {len(va):>6,d} {d(va)} | "
                  f"test {len(te):>6,d} {d(te)}")
    return folds


class FoldList(list):
    """A list of (train_idx, val_idx, test_idx) that also carries cutoff dates."""

    def __init__(self, *args):
        super().__init__(*args)
        self.cutoffs: list[pd.Timestamp] = []


def fit_slice(df: pd.DataFrame, train_idx, val_idx, purge_days: int = 30):
    """Rows of train used to fit during tuning: train minus val, minus the
    `purge_days` right before val (their forward targets overlap the val
    period, which would flatter low-bias models such as small-k KNN)."""
    dates = df["date"].to_numpy()
    val_start = dates[val_idx].min()
    keep = dates[train_idx] <= val_start - np.timedelta64(purge_days + 1, "D")
    return np.asarray(train_idx)[keep]


# --------------------------------------------------------------------------
# Metrics and baselines
# --------------------------------------------------------------------------
def evaluate(y_true, y_pred, y_persist) -> dict:
    """Metrics in log-vol space. r2_oos is relative to the persistence
    forecast (y_persist = log rv_past_14d): 0 = ties persistence."""
    y_true, y_pred, y_persist = (np.asarray(a, dtype=float)
                                 for a in (y_true, y_pred, y_persist))
    err = y_true - y_pred
    sse = float(np.sum(err ** 2))
    sse_p = float(np.sum((y_true - y_persist) ** 2))
    rho = spearmanr(y_true, y_pred).statistic if np.ptp(y_pred) > 0 else np.nan
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "r2_oos": 1.0 - sse / sse_p,
        "spearman": float(rho),
        "rmse_level": float(np.sqrt(np.mean((np.exp(y_true) - np.exp(y_pred)) ** 2))),
        "n": int(len(y_true)),
    }


RESULT_COLUMNS = ["model", "feature_set", "freq", "target", "fold", "cutoff_date",
                  "n_train", "n_test", "best_params", "rmse", "mae", "r2_oos",
                  "spearman", "rmse_level", "subsample"]
RUN_KEY = ["model", "feature_set", "freq", "target", "subsample"]


def _upsert_results(path: Path, new: pd.DataFrame) -> None:
    """Append to a results CSV, replacing rows from an earlier identical run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        if "subsample" not in old.columns:
            old["subsample"] = "all"
        keys = set(map(tuple, new[RUN_KEY].astype(str).drop_duplicates().to_numpy()))
        keep = [tuple(r) not in keys for r in old[RUN_KEY].astype(str).to_numpy()]
        new = pd.concat([old[keep], new], ignore_index=True)
    new[RESULT_COLUMNS].to_csv(path, index=False)


def baselines(df: pd.DataFrame, folds, freq: str = "daily", target: str = "y",
              subsample: str = "all", save: bool = True) -> pd.DataFrame:
    """Persistence (log rv_past_14d) and pooled train-mean forecasts per fold."""
    y = df[target].to_numpy()
    persist = np.log(df[PERSIST_COL].to_numpy())
    rows = []
    for k, (tr, _, te) in enumerate(folds, start=1):
        preds = {"persistence": persist[te],
                 "train_mean": np.full(len(te), y[tr].mean())}
        for name, p in preds.items():
            m = evaluate(y[te], p, persist[te])
            rows.append({"model": name, "feature_set": "NONE", "freq": freq,
                         "target": TARGETS[target], "fold": k,
                         "cutoff_date": folds.cutoffs[k - 1].date().isoformat(),
                         "n_train": len(tr), "n_test": m.pop("n"),
                         "best_params": "{}", **m, "subsample": subsample})
    out = pd.DataFrame(rows)[RESULT_COLUMNS]
    if save:
        _upsert_results(RESULTS_DIR / "baselines.csv", out)
    return out


# --------------------------------------------------------------------------
# Generic model loop
# --------------------------------------------------------------------------
def expand_grid(param_grid: dict, max_configs: int | None = None) -> list[dict]:
    """All combinations of param_grid; optionally a fixed random subset."""
    keys = list(param_grid)
    configs = [dict(zip(keys, v)) for v in itertools.product(*param_grid.values())]
    if max_configs is not None and max_configs < len(configs):
        rng = np.random.default_rng(RANDOM_STATE)
        pick = sorted(rng.choice(len(configs), size=max_configs, replace=False))
        configs = [configs[i] for i in pick]
    return configs


def _jsonable(params: dict) -> str:
    return json.dumps({k: (v.item() if isinstance(v, np.generic) else v)
                       for k, v in params.items()}, sort_keys=True)


def run_tag(feature_set_name, freq, target="y", subsample="all") -> str:
    tag = f"{feature_set_name}_{freq}"
    if target != "y":
        tag += f"_{TARGETS[target]}"
    if subsample != "all":
        tag += f"_{subsample}"
    return tag


def run_model(name, estimator_factory, df, folds, feature_set_name, param_grid,
              freq, *, target: str = "y", subsample: str = "all",
              max_configs: int | None = None, purge_days: int = 30,
              save: bool = True, verbose: bool = True) -> pd.DataFrame:
    """Tune on the validation slice, refit on full train, score on test.

    estimator_factory(**params) must return an unfitted sklearn Pipeline (or
    estimator); any scaler inside it is therefore fit on training rows only.
    param_grid is {param_name: [values]}; max_configs evaluates a fixed random
    subset of the grid (seeded) when the full grid is too slow.
    `df` must be the frame `folds` was built from. `subsample` is only a label
    for the results CSV -- filter df yourself before calling make_folds.

    Writes results/<name>.csv, results/preds_<name>_<tag>.parquet and
    results/val_<name>_<tag>.csv (validation RMSE of every config tried).
    """
    features = FEATURE_SETS[feature_set_name]
    if target not in TARGETS:
        raise KeyError(f"target must be one of {list(TARGETS)}")
    X = df[features].to_numpy(dtype=float)
    y = df[target].to_numpy()
    persist = np.log(df[PERSIST_COL].to_numpy())
    configs = expand_grid(param_grid, max_configs)
    tag = run_tag(feature_set_name, freq, target, subsample)

    rows, preds, val_rows = [], [], []
    t_start = time.perf_counter()
    for k, (tr, va, te) in enumerate(folds, start=1):
        t0 = time.perf_counter()
        fit = fit_slice(df, tr, va, purge_days)
        best = (np.inf, None)
        for params in configs:
            est = estimator_factory(**params).fit(X[fit], y[fit])
            rmse = float(np.sqrt(np.mean((y[va] - est.predict(X[va])) ** 2)))
            val_rows.append({"model": name, "feature_set": feature_set_name,
                             "freq": freq, "target": TARGETS[target],
                             "subsample": subsample, "fold": k, **params,
                             "val_rmse": rmse})
            if rmse < best[0]:
                best = (rmse, params)
        est = estimator_factory(**best[1]).fit(X[tr], y[tr])
        p = est.predict(X[te])
        m = evaluate(y[te], p, persist[te])
        rows.append({"model": name, "feature_set": feature_set_name, "freq": freq,
                     "target": TARGETS[target], "fold": k,
                     "cutoff_date": folds.cutoffs[k - 1].date().isoformat(),
                     "n_train": len(tr), "n_test": m.pop("n"),
                     "best_params": _jsonable(best[1]), **m,
                     "subsample": subsample})
        preds.append(pd.DataFrame({"token_id": df["token_id"].to_numpy()[te],
                                   "date": df["date"].to_numpy()[te],
                                   "y_true": y[te], "y_pred": p, "fold": k}))
        if verbose:
            print(f"[{name}|{tag}] fold {k}: val_rmse {best[0]:.4f} "
                  f"test rmse {m['rmse']:.4f} r2_oos {m['r2_oos']:+.4f} "
                  f"best {_jsonable(best[1])} ({time.perf_counter() - t0:.1f}s)")

    out = pd.DataFrame(rows)[RESULT_COLUMNS]
    if verbose:
        print(f"[{name}|{tag}] mean r2_oos {out['r2_oos'].mean():+.4f} "
              f"mean rmse {out['rmse'].mean():.4f} "
              f"({len(configs)} configs, {time.perf_counter() - t_start:.1f}s total)")
    if save:
        _upsert_results(RESULTS_DIR / f"{name}.csv", out)
        pd.concat(preds, ignore_index=True).to_parquet(
            RESULTS_DIR / f"preds_{name}_{tag}.parquet", index=False)
        pd.DataFrame(val_rows).to_csv(
            RESULTS_DIR / f"val_{name}_{tag}.csv", index=False)
    return out


# --------------------------------------------------------------------------
# Fixed log transform for the linear models (Ridge / Elastic Net / logistic)
# --------------------------------------------------------------------------
# Volatility levels and token age are right-skewed and enter a linear model
# better in logs. Nothing is learned from data, so it is safe in any fold.
LOG_COLS = ["rv_past_7d", "rv_past_14d", "rv_past_30d",
            "btc_rv_past_14d", "eth_rv_past_14d"]
LOG1P_COLS = ["days_since_tge"]


def _log_columns(X, ix_log=(), ix_log1p=()):
    X = np.array(X, dtype=float, copy=True)
    X[:, list(ix_log)] = np.log(X[:, list(ix_log)])
    X[:, list(ix_log1p)] = np.log1p(X[:, list(ix_log1p)])
    return X


def log_transformer(features: list[str]):
    """FunctionTransformer that logs LOG_COLS and log1ps LOG1P_COLS, located
    by position in `features` (the column order of the feature matrix)."""
    from sklearn.preprocessing import FunctionTransformer
    return FunctionTransformer(_log_columns, kw_args={
        "ix_log": [i for i, f in enumerate(features) if f in LOG_COLS],
        "ix_log1p": [i for i, f in enumerate(features) if f in LOG1P_COLS]})


# --------------------------------------------------------------------------
# Plot style shared by all scripts
# --------------------------------------------------------------------------
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
           "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def set_style() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from cycler import cycler
    plt.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 150, "savefig.bbox": "tight",
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.prop_cycle": cycler(color=PALETTE),
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
        "axes.titlecolor": INK, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.labelsize": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": INK_2, "ytick.color": INK_2,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "text.color": INK, "legend.frameon": False, "legend.fontsize": 9,
        "lines.linewidth": 2, "lines.markersize": 6, "font.size": 10,
    })


def savefig(fig, name: str) -> Path:
    import matplotlib.pyplot as plt
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[figure] {path.relative_to(ROOT)}")
    return path


if __name__ == "__main__":
    # smoke test + baselines for both frequencies
    for f in ("daily", "weekly"):
        d = load_data(freq=f)
        print(baselines(d, make_folds(d), freq=f)
              .groupby("model")[["rmse", "mae", "r2_oos", "spearman"]].mean())
