# Project context (NTU MH6805 group project)

## The question
Do scheduled token-unlock (emission) features add forecasting power for a
crypto token's forward 14-day realized volatility **beyond** volatility
persistence and market regime? Every model is run twice: on control features
only and on controls + emission + static. The difference is the finding.
A null or negative result is a valid result; never tune until it disappears.

## Data
- `data/dataset_v1.csv`: token x calendar-day panel (176 tokens in the file,
  2024-09-14 .. 2026-08-15). Column definitions: `data/COLUMN_GUIDE.md`.
- **Never modify anything under `data/`.** `data/raw/` is git-ignored.

## The ex-ante rule
A feature must be known at the close of date D.
- Targets (`rv_fwd_*`, `fwd_ret_14d`) are forward-looking: never inputs.
- The only forward-looking inputs allowed are the emission schedule columns
  (`emis_next_*`, cliff columns), because the schedule is published in advance.
- Caveat: schedules are the version curated on the pull date (2026-09-14), so
  they are lookahead-safe mechanically but not against later revisions.
  Static columns (alloc shares, listedMethod, unlockPrecision) are snapshots too.

## Never shuffle rows
- No `KFold`, no `train_test_split(shuffle=True)`, no random split of any kind.
- All splits are by calendar date via `common.make_folds`.
- Scalers / imputers / encoders are fit on the training slice of the current
  fold only: put them inside the sklearn `Pipeline` your factory returns.
- `random_state=42` everywhere (`common.RANDOM_STATE`).

## Feature sets (`common.py`, names after cleaning)
- `CONTROLS` (9): rv_past_7d/14d/30d, ret_past_7d/30d, btc/eth_rv_past_14d,
  log_mcap_pit, days_since_tge
- `EMISSION` (13): emis_next_{7,30,90}d_pct_float (log1p), emis_next_30d_pct_total,
  days_to_next_cliff (null -> 365), next_cliff_pct_float (log1p, null -> 0),
  has_unlock_events, six emis_next_30d_<bucket>_pct_float (log1p)
- `STATIC` (10): six alloc_share_<bucket>, listedMethod one-hots,
  unlockPrecision_ord
- `FULL` = CONTROLS + EMISSION + STATIC (32)
- Extras in `common.FEATURE_SETS`: `CONTROLS+EMIS5`, `FULL_NO_AGG30`.
  Add new ones with `common.register_feature_set`.

## Targets
`y` = log(rv_fwd_14d) (primary). Robustness: `y_7d`, `y_30d`,
`y_14d_parkinson`. All metrics are in log-vol space.

## Fold protocol (`make_folds`)
5 walk-forward folds, tokens pooled. Cutoffs every 90 days over the last 450
days. train = date <= c - 30d (embargo); test = c < date <= c + 90d; the last
90 days of train are the validation slice. Tuning fits on train minus val
minus a 30-day purge before val, scores RMSE on val, then the best config is
refit on all of train and scored once on test. Tuning never touches test.

## Metrics (`evaluate`)
rmse, mae, spearman, rmse_level (after exp), and
r2_oos = 1 - SSE_model / SSE_persistence where persistence = log(rv_past_14d).
r2_oos = 0 means "ties persistence". Note the pooled train mean already beats
persistence (r2_oos ~ +0.17), so compare models against `train_mean` too.

## Results schema (`results/<model>.csv`, one row per fold per run)
model, feature_set, freq, target, fold, cutoff_date, n_train, n_test,
best_params (json), rmse, mae, r2_oos, spearman, rmse_level, subsample
(`subsample` = "all" unless a filtered panel was used.)
Re-running a script replaces its earlier rows; it does not duplicate them.

## Layout
`common.py` harness | `scripts/01_eda.py` | `scripts/02_knn.py` |
`scripts/03_rf.py` | `scripts/04_compare.py` | `scripts/05_linear.py` (Ridge,
Elastic Net) | `scripts/07_lgbm.py` (LightGBM) | `scripts/08_errors.py` (error analysis by subgroup + practical
relevance from the saved test predictions; run after 02/03/05/07) |
`results/` | `figures/` | `report/` (draft report and slides; `report/build/`
regenerates them from results/ and figures/)
Linear models log the vol controls inside their Pipeline via
`common.log_transformer` (fixed transform, nothing learned).
Older files in `scripts/` (tok_pull, build_dataset, audit_alignment,
final_check, make_report) built the dataset; they are not part of the
analysis pipeline.

## Conventions
- Plain scripts, run from the repo root: `python scripts/02_knn.py`.
- Keep console output ASCII (the Windows cp874 console crashes on others).
- Use `common.set_style()` / `common.savefig()` for figures (PNG, 150 dpi).
