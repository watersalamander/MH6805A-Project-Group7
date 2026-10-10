# Token unlocks and forward volatility (MH6805, Group 7)

Does a token's scheduled unlock (emission) calendar help forecast its forward
14-day realized volatility beyond volatility persistence and market regime?
Every model is run on control features only and on controls + emission +
static features; the difference is the finding.

**Status (Oct 2026):** data, cleaning, folds, EDA, baselines, KNN and Random
Forest are finished and executed in the notebook. Headline so far: emission +
static features add at most a few thousandths of `r2_oos`, well inside the
fold-to-fold spread. **The next step is more models**, added by teammates
following the guide below.

---

## For teammates: read this first

### Rule 1. The notebook is the deliverable
`MH6805_token_unlock_volatility.ipynb` is the **only file we submit**. Every
new model goes into this notebook as its own section. Do **not** create a
separate notebook or a new script as your final work; anything that is not in
the notebook will not be marked.

You may prototype wherever you like, but the finished model must live in the
notebook, executed, with its outputs saved.

### Rule 2. Do not clean the data again
The data pipeline is frozen. Use it exactly as it is:

- Load the panel only through `load_data(freq="daily")` / `load_data(freq="weekly")`.
  In the notebook this is already done: use the `data` dict
  (`data["daily"]` and `data["weekly"]` are `(df, folds)` pairs).
- Build splits only through `make_folds` (already in `data`).
- Use the existing feature sets: `CONTROLS`, `FULL`, `CONTROLS+EMIS5`,
  `FULL_NO_AGG30`. If you really need another subset of the **already cleaned**
  columns, use `register_feature_set(name, columns)`; never create new columns.
- Do **not** edit section 0 (shared harness), section 1 (load and clean) or
  section 2 (folds), and do not touch `common.py`.
- **Never modify anything under `data/`.** Do not re-download, re-filter,
  re-impute or re-scale the CSV.

If you think the cleaning is wrong, raise it with the group instead of fixing
it in your own section. Every model must see identical rows and identical
folds, otherwise the comparison table is meaningless.

### Rule 3. Same protocol for every model
These are already enforced by `run_model`; do not work around them.

- Run each model on **`CONTROLS` and `FULL`**, on **both `daily` and
  `weekly`** panels (four runs). The comparison chart needs all four.
- No shuffling, no `KFold`, no `train_test_split`. Splits are by date only.
- Put every scaler / imputer / encoder **inside the sklearn `Pipeline`** your
  factory returns, so it is fit on the training slice of each fold only.
- `random_state=RANDOM_STATE` (42) on anything random.
- Tune only through the `param_grid` you pass to `run_model`. It picks the
  config by validation RMSE and scores test **once**. Never look at test
  numbers to choose hyperparameters.
- A null or negative result is a valid result. Do not tune until FULL "wins".

---

## How to add a model to the notebook

### Step 1. Set up and check the notebook runs
```bash
git checkout main && git pull
git checkout -b <your-name>-<model>        # e.g. alex-ridge
pip install -r requirements.txt            # Python 3.13
python -m ipykernel install --user --name python3
```
Open the notebook from the **repo root** and run all cells. Because finished
KNN and RF runs are reused from `results/`, a full run takes only a few
minutes. Do **not** set `NB_FRESH=1` (that recomputes RF, several hours).

### Step 2. Insert your section
Insert your cells **after section 6 (Random Forest) and before section 7
(Comparison across models)**, then renumber: your model becomes section 7,
Comparison becomes 8, Conclusions becomes 9 (and so on if several models are
added). Each model section has:

1. A markdown cell: what the model is, why it suits this question, the grid.
2. A code cell with the factory, grid and the four runs (template below).
3. Optionally, one or two diagnostic figures saved with `savefig`.

### Step 3. Use this template
Copy it, change the name, the pipeline and the grid. Imports go at the top of
your own cell; nothing else in the notebook needs to change.

```python
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

RIDGE_NAME = "ridge"                         # unique: becomes results/ridge.csv
RIDGE_GRID = {"alpha": [0.1, 1, 10, 100, 1000]}


def ridge_factory(**params) -> Pipeline:     # must return an UNFITTED Pipeline
    return Pipeline([
        ("scale", StandardScaler()),         # fit on training rows only
        ("ridge", Ridge(**params)),
    ])


ridge_results = []
for freq, (df, folds) in data.items():                   # daily and weekly
    for fs in ("CONTROLS", "FULL"):
        grid = {"alpha": [1, 100]} if SMOKE else RIDGE_GRID
        done = finished_run(RIDGE_NAME, folds, fs, freq)  # reuse if already run
        ridge_results.append(done if done is not None else
                             run_model(RIDGE_NAME, ridge_factory, df, folds, fs,
                                       grid, freq, save=not SMOKE))
ridge_res = pd.concat(ridge_results, ignore_index=True)

print("Ridge mean over folds:")
display(ridge_res.groupby(["freq", "feature_set"], sort=False)
                 [["rmse", "mae", "r2_oos", "spearman"]].mean().round(4))
```

What you get for free:

- `run_model` tunes on the validation slice (with a 30-day purge), refits on
  all of train, scores test once per fold, and writes `results/<name>.csv`,
  test predictions (`preds_*.parquet`) and validation curves (`val_*.csv`).
- `finished_run` makes later notebook runs reuse your saved results, so the
  notebook stays fast for everyone.
- The **Comparison section picks up your `results/<name>.csv` automatically**:
  your model appears in `comparison_table.csv`, the headline tables and the
  `compare_r2_oos.png` chart with no code change.

For a slow model, pass `max_configs=N` to `run_model` to evaluate a fixed,
seeded random subset of the grid (this is what RF does on the daily panel).
Say so in your markdown cell.

### Step 4. Test cheaply, then run for real
1. Smoke check: start the kernel with `NB_SMOKE=1` (tiny grids, nothing saved)
   and run all cells to catch code errors.
2. Real run: restart the kernel **without** `NB_SMOKE`, run all cells top to
   bottom. Check there are no error outputs and every figure renders.

### Step 5. Update the conclusions, then open a pull request
- Add your model's row to the table in the Conclusions section and adjust the
  text if your result changes the overall reading. Compare against both
  `persistence` (r2_oos = 0) and `train_mean` (r2_oos about 0.17).
- Commit the executed notebook **and** your new files under `results/` and
  `figures/`, then push your branch and open a pull request into `main`.
- Keep console output ASCII only (the Windows cp874 console crashes otherwise).

### Avoiding notebook merge conflicts
A `.ipynb` file is JSON, so two people editing it at once conflict easily.

- Only add cells inside your own section; do not edit, re-run-and-reformat or
  move other people's cells.
- Before opening your PR, `git pull origin main`, re-run the notebook, and
  commit the re-executed version.
- Merge one model PR at a time. The next person pulls `main` before merging.
- If a conflict happens anyway, keep `main`'s version of the notebook, re-add
  your section's cells, and re-run.

### Model ideas (not assignments; agree in the group who does what)
| Model | Why it is interesting here | Notes |
|---|---|---|
| Ridge / Lasso / ElasticNet | Linear benchmark; on CONTROLS it is close to a HAR volatility model | Needs `StandardScaler` in the pipeline |
| Gradient boosting (`HistGradientBoostingRegressor`) | Usually stronger than RF on tabular data | Already in scikit-learn; fast |
| LightGBM / XGBoost | Same idea, more tuning options | Add the package to `requirements.txt` in your PR |
| MLP (`MLPRegressor`) | Non-linear, smooth | Scale inputs; set `random_state` and `early_stopping` |
| SVR (linear kernel or `LinearSVR`) | Robust loss | Kernel SVR is too slow on ~100k daily rows |

---

## Repository reference

### Layout
| Path | What it is |
|---|---|
| `MH6805_token_unlock_volatility.ipynb` | **The deliverable.** Whole pipeline, executed |
| `data/dataset_v1.csv` | Token x day panel, 176 tokens, 2024-09-14 to 2026-08-15. Read-only |
| `data/COLUMN_GUIDE.md` | Column definitions |
| `common.py`, `scripts/01_eda.py` .. `04_compare.py` | Script versions of the harness and analysis, inlined in the notebook. Reference only; not needed to run the notebook |
| `scripts/tok_pull.py`, `build_dataset.py`, `audit_alignment.py`, `final_check.py`, `make_report.py` | Built the dataset. Not part of the analysis; do not re-run |
| `results/` | Per-fold results, predictions, tables (see below) |
| `figures/` | PNG copies of every chart (150 dpi) |
| `CLAUDE.md` | Full statement of the project rules |

### Notebook sections
| Section | Content | Teammates edit? |
|---|---|---|
| 0. Shared harness | Cleaning, feature sets, folds, metrics, `run_model` | No |
| 1. Load and clean | `daily`, `weekly` panels | No |
| 2. Walk-forward folds | 5 folds, builds `data` | No |
| 3. EDA | Figures and summary table | No |
| 4. Baselines | Persistence and pooled train mean | No |
| 5. KNN | Done | No |
| 6. Random Forest | Done, plus robustness and interpretation | No |
| *new sections* | **Your models go here** | **Yes** |
| Comparison across models | Reads every `results/<model>.csv` | Only renumber the heading |
| Conclusions | Final reading and table | Yes, add your row |

### Feature sets
- `CONTROLS` (9): `rv_past_7d/14d/30d`, `ret_past_7d/30d`, `btc_rv_past_14d`,
  `eth_rv_past_14d`, `log_mcap_pit`, `days_since_tge`
- `EMISSION` (13): `emis_next_{7,30,90}d_pct_float` (log1p),
  `emis_next_30d_pct_total`, `days_to_next_cliff` (null -> 365),
  `next_cliff_pct_float` (log1p, null -> 0), `has_unlock_events`, six
  `emis_next_30d_<recipient>_pct_float` (log1p)
- `STATIC` (10): six `alloc_share_<recipient>`, `listedMethod` one-hots,
  `unlockPrecision_ord`
- `FULL` = CONTROLS + EMISSION + STATIC (32). Extras: `CONTROLS+EMIS5`,
  `FULL_NO_AGG30`.

### Targets
`y = log(rv_fwd_14d)` is the primary target. Robustness targets: `y_7d`,
`y_30d`, `y_14d_parkinson` (pass `target=` to `run_model`). All metrics are in
log-vol space.

### Protocol in brief
5 walk-forward folds, tokens pooled, cutoffs every 90 days over the last 450
days. Train = dates up to cutoff minus 30 days (embargo); test = the 90 days
after the cutoff; the last 90 days of train are the validation slice. Tuning
fits on train minus validation minus a 30-day purge, picks the best config by
validation RMSE, refits on all of train and scores test once. Details in
`CLAUDE.md`.

### Result files (`results/`)
| File | Meaning |
|---|---|
| `baselines.csv` | Persistence and pooled train-mean forecasts, per fold |
| `knn.csv`, `rf.csv`, `<your model>.csv` | One row per fold per run (schema below) |
| `preds_<model>_<featureset>_<freq>[...].parquet` | Test-fold predictions: token_id, date, y_true, y_pred, fold |
| `val_<model>_<featureset>_<freq>[...].csv` | Validation RMSE of every config tried, per fold |
| `eda_summary.csv` | Row/token counts, date range, null rates, Spearman(emission, y) |
| `knn_neighbours.csv` | Neighbour illustration table for the KNN figure |
| `rf_permutation_importance.csv` | Permutation (test) and impurity importances |
| `comparison_table.csv` | Mean and std across folds by model / feature set / freq / target / subsample |

Schema of the per-model CSVs:
`model, feature_set, freq, target, fold, cutoff_date, n_train, n_test,
best_params (json), rmse, mae, r2_oos, spearman, rmse_level, subsample`

- `r2_oos = 1 - SSE_model / SSE_persistence`. Zero means the model ties the
  persistence forecast `log(rv_past_14d)`. The pooled train mean already
  scores about +0.17, so compare models against `train_mean` too.
- `rmse_level` is RMSE after `exp()`, in volatility units.
- `subsample` is `all` unless the run used a filtered panel (e.g. `INTERNAL`).
- Re-running a model replaces its earlier rows in the CSV; it does not
  duplicate them.

### Current results (target log rv_fwd_14d, mean of 5 folds)
| Model, panel | r2_oos CONTROLS | r2_oos FULL | RMSE CONTROLS | RMSE FULL |
|---|---|---|---|---|
| RF, daily | 0.262 | 0.268 | 0.4451 | 0.4431 |
| RF, weekly | 0.234 | 0.241 | 0.4510 | 0.4500 |
| KNN, daily | 0.234 | 0.235 | 0.4526 | 0.4538 |
| KNN, weekly | 0.232 | 0.225 | 0.4534 | 0.4576 |

Fold-to-fold standard deviation of `r2_oos` is about 0.15 to 0.21.

### Known limitations
- One market regime: the panel covers a calm-to-moderate volatility period
  only, with no 2020/2022-style stress.
- Schedules are the version curated on the pull date (2026-09-14): safe from
  lookahead mechanically, not against later revisions. Static columns are
  snapshots too.
