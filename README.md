# Token unlocks and forward volatility (MH6805)

Does a token's scheduled unlock (emission) calendar help forecast its forward
14-day realized volatility beyond volatility persistence and market regime?
Every model is run on control features only and on controls + emission +
static features; the difference is the finding.

## Setup
```bash
pip install -r requirements.txt
```
Python 3.13. Run everything from the repo root.

## Submission notebook
`MH6805_token_unlock_volatility.ipynb` is the single deliverable: the whole
analysis pipeline (harness, cleaning, folds, EDA, baselines, KNN, Random
Forest, comparison) in one self-contained notebook that starts from
`data/dataset_v1.csv`. It inlines `common.py` and the four scripts below, so
it needs nothing from `scripts/` to run. Data gathering is not part of it.
Run from the repo root with a Python 3.13 kernel; the Random Forest section
takes hours (set `NB_SMOKE=1` in the environment before starting the kernel
for a minutes-long code check that saves nothing).

## Run order
| Command | What it does | Approx. time |
|---|---|---|
| `python common.py` | Smoke test of the harness; writes `results/baselines.csv` | < 1 min |
| `python scripts/01_eda.py` | EDA figures + `results/eda_summary.csv` | < 1 min |
| `python scripts/02_knn.py` | KNN, 3 feature sets x daily/weekly, figures | see script output |
| `python scripts/03_rf.py` | Random Forest, importances, PDPs, robustness | see script output |
| `python scripts/04_compare.py` | Aggregates every results CSV into one table + chart | seconds |

## Result files (`results/`)
| File | Meaning |
|---|---|
| `baselines.csv` | Persistence (log rv_past_14d) and pooled train-mean forecasts, per fold |
| `knn.csv`, `rf.csv` | One row per fold per run (schema below) |
| `preds_<model>_<featureset>_<freq>[...].parquet` | Test-fold predictions: token_id, date, y_true, y_pred, fold |
| `val_<model>_<featureset>_<freq>[...].csv` | Validation RMSE of every hyperparameter config tried, per fold |
| `eda_summary.csv` | Row/token counts, date range, null rates, Spearman(emission, y) |
| `knn_neighbours.csv` | Neighbour illustration table for the KNN figure |
| `rf_permutation_importance.csv` | Permutation (test set) and impurity importances, FULL and recipient-split models |
| `comparison_table.csv` | Mean and std across folds by model / feature set / freq / target / subsample |

Schema of the per-model CSVs:
`model, feature_set, freq, target, fold, cutoff_date, n_train, n_test,
best_params (json), rmse, mae, r2_oos, spearman, rmse_level, subsample`

- All errors are in log-volatility space; `rmse_level` is after `exp()`.
- `r2_oos = 1 - SSE_model / SSE_persistence`. Zero means the model ties the
  persistence forecast `log(rv_past_14d)`; the same benchmark is used for the
  robustness targets.
- `subsample` is `all` unless the run used a filtered panel (e.g. `INTERNAL`).

## Notes on the protocol as implemented
- The CSV holds 176 tokens (not 177); 101,393 daily / 14,623 weekly rows
  remain after cleaning.
- Tuning fits on train minus the validation slice **minus a 30-day purge**
  before validation (`purge_days` in `run_model`), so validation mimics the
  embargoed test setting. Set `purge_days=0` for plain "train minus val".
- Random Forest on the daily panel tunes over a fixed seeded random subset of
  the 36-config grid (12 configs for the main runs, 6 for robustness runs)
  because one 400-tree fit takes 20-90 s. Weekly runs use the full grid.
  Pass `max_configs=` to `run_model` to do the same for a slow model.
- `python scripts/02_knn.py --figures-only` and
  `python scripts/03_rf.py --skip-runs` rebuild figures from saved results.

## Adding a model (teammates)
```python
import sys; sys.path.insert(0, ".")
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
import common as C

def factory(**params):                 # must return an unfitted Pipeline
    return make_pipeline(StandardScaler(), Ridge(**params))

for freq in ("daily", "weekly"):
    df = C.load_data(freq=freq)
    folds = C.make_folds(df)
    for fs in ("CONTROLS", "FULL"):
        C.run_model("ridge", factory, df, folds, fs,
                    {"alpha": [0.1, 1, 10, 100]}, freq)
```
This writes `results/ridge.csv`, and `04_compare.py` picks it up automatically.

## Protocol in brief
Walk-forward, 5 folds, 90-day test windows, 30-day embargo, last 90 days of
train as validation. No random splits anywhere. Details in `CLAUDE.md`.
