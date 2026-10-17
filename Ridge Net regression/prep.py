"""
MH6805 Group 7 - shared preprocessing + walk-forward folds.
Every model (Ridge/EN, Logistic, KNN, RF, GBM, DLEN) should import from here
so all members train and test on identical rows, features and splits.

Usage:
    from prep import load_panel, build_features, walk_forward_folds, FEATURE_SETS
"""
import numpy as np
import pandas as pd

BUCKETS = ["founderTeam", "privateInvestors", "community",
           "publicInvestors", "reserve", "others"]

# ---------------------------------------------------------------- load
def load_panel(path="dataset_v1.csv"):
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values(["token_id", "date"]).reset_index(drop=True)
    # persistence baseline needs rv_past_14d -> drop the ~1% of rows without it
    df = df[df["rv_past_14d"].notna()].copy()
    return df


# ---------------------------------------------------------------- features
def build_features(df, pct_cap=1.0):
    """Return a DataFrame of model-ready features (no scaling; scale inside folds)."""
    X = pd.DataFrame(index=df.index)

    # --- backward-looking controls (persistence + regime + size/age)
    X["log_rv_past_7d"] = np.log(df["rv_past_7d"])
    X["log_rv_past_14d"] = np.log(df["rv_past_14d"])
    rv30 = df["rv_past_30d"].fillna(df["rv_past_14d"])        # new listings
    X["log_rv_past_30d"] = np.log(rv30)
    X["rv_past_30d_missing"] = df["rv_past_30d"].isna().astype(float)
    X["ret_past_7d"] = df["ret_past_7d"]
    X["ret_past_30d"] = df["ret_past_30d"].fillna(df["ret_past_7d"])
    X["log_btc_rv_past_14d"] = np.log(df["btc_rv_past_14d"])
    X["log_eth_rv_past_14d"] = np.log(df["eth_rv_past_14d"])
    X["log_mcap_pit"] = df["log_mcap_pit"]
    X["log_days_since_tge"] = np.log1p(df["days_since_tge"])

    # --- emission pressure (variables of interest); cap ratio >1 (3 tokens, 90 rows)
    for h in ["7d", "30d", "90d"]:
        X[f"emis_next_{h}_pct_float"] = np.log1p(
            df[f"emis_next_{h}_pct_float"].clip(upper=pct_cap))
    X["emis_next_30d_pct_total"] = df["emis_next_30d_pct_total"]
    # recipient split, scaled by float so it is comparable across tokens
    for b in BUCKETS:
        X[f"emis30_{b}_pct_float"] = np.log1p(
            (df[f"emis_next_30d_{b}"] / df["float_pit"]).clip(upper=pct_cap))
    # cliff features: structurally missing -> fill + indicator
    X["no_upcoming_cliff"] = df["days_to_next_cliff"].isna().astype(float)
    X["log_days_to_next_cliff"] = np.log1p(df["days_to_next_cliff"].fillna(365))
    X["next_cliff_pct_float"] = np.log1p(
        df["next_cliff_pct_float"].fillna(0).clip(upper=pct_cap))
    X["has_unlock_events"] = df["has_unlock_events"].astype(float)
    X["emission_schedule_ended"] = df["emission_schedule_ended"].astype(float)

    # --- static allocation mix (drop 'others' as reference category)
    for b in BUCKETS[:-1]:
        X[f"alloc_share_{b}"] = df[f"alloc_share_{b}"]
    return X


CONTROLS = ["log_rv_past_7d", "log_rv_past_14d", "log_rv_past_30d",
            "rv_past_30d_missing", "ret_past_7d", "ret_past_30d",
            "log_btc_rv_past_14d", "log_eth_rv_past_14d",
            "log_mcap_pit", "log_days_since_tge"]
EMISSION = (["emis_next_7d_pct_float", "emis_next_30d_pct_float",
             "emis_next_90d_pct_float", "emis_next_30d_pct_total"]
            + [f"emis30_{b}_pct_float" for b in BUCKETS]
            + ["no_upcoming_cliff", "log_days_to_next_cliff",
               "next_cliff_pct_float", "has_unlock_events",
               "emission_schedule_ended"])
STATIC = [f"alloc_share_{b}" for b in BUCKETS[:-1]]

FEATURE_SETS = {
    "controls": CONTROLS + STATIC,                 # no emission info
    "full": CONTROLS + STATIC + EMISSION,          # + emission features
}


# ---------------------------------------------------------------- folds
TEST_STARTS = ["2025-04-01", "2025-07-01", "2025-10-01",
               "2026-01-01", "2026-04-01", "2026-07-01"]


def walk_forward_folds(dates, test_starts=TEST_STARTS, embargo_days=30):
    """Expanding-window folds. Train: date <= test_start - embargo - 1.
    Test: test_start <= date < next test_start (last fold runs to end).
    30-day embargo > longest target horizon, so no train target overlaps test."""
    dates = pd.to_datetime(dates)
    starts = [pd.Timestamp(s) for s in test_starts]
    ends = starts[1:] + [dates.max() + pd.Timedelta(days=1)]
    folds = []
    for k, (s, e) in enumerate(zip(starts, ends)):
        tr = np.where(dates <= s - pd.Timedelta(days=embargo_days + 1))[0]
        te = np.where((dates >= s) & (dates < e))[0]
        folds.append((k, s, e, tr, te))
    return folds
