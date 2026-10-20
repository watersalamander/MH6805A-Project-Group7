# Group 7: presentation and review split

The report and deck are split into three continuous blocks that follow the story:
**question and data** -> **models and results** -> **errors, relevance and conclusion**.
Whoever presents a block also rechecks that block in the slides, the report and the
code that produced its numbers, so they can answer Q&A on it. Each person also reads one
other block as a second pair of eyes.

Replace `Member 1/2/3` with names, then put the same names in the slide speaker notes,
on slide 1, on slide 17 and in report Table A3.

## At a glance

| | Member 1: Question, data and protocol | Member 2: Models and headline results | Member 3: Errors, relevance and conclusion |
|---|---|---|---|
| **Presents** | Slides 1-6 (title, motivation, design, dataset, EDA, walk-forward protocol) | Slides 7-11 (six models, R2 results, per-fold noise, interpretation, logistic) | Slides 12-16 (which mistakes remain, robustness, practical relevance, conclusion, limitations) and moderates Q&A (slide 17) |
| **Talk time** | about 1/3 (the title slide is short) | about 1/3 | about 1/3 |
| **Report sections to recheck** | Abstract, 1 Introduction, 2 Problem and objectives, 3 Dataset (Table 1, Figure 1), 4.1 to 4.2 protocol and baselines (Table 2) | 4.3 Models, 5.1 Predictive performance (Tables 3-4, Figure 2), 5.3 Interpretation, 5.4 Logistic (Table 6) | 5.2 Which mistakes remain (Table 5), 5.5 Robustness, 5.6 Comparison and practical relevance, 6 Conclusion, References |
| **Appendix to recheck** | Table A1, Figure A10 | Figures A3-A9, A11 | Figures A1-A2, Table A2, Table A3 (collect everyone's contribution) |
| **Code and results to recheck** | `common.py` (cleaning in `load_data`, `make_folds`, `evaluate`, `baselines`), `scripts/01_eda.py`, `data/COLUMN_GUIDE.md`, `results/eda_summary.csv`, `results/baselines.csv` | `scripts/02_knn.py`, `03_rf.py`, `05_linear.py`, `06_logistic.py`, `07_lgbm.py`, `04_compare.py`, `results/<model>.csv`, `results/comparison_table.csv` | `scripts/08_errors.py`, `results/error_*.csv`, robustness rows of `results/comparison_table.csv` (weekly, INTERNAL, 7d/30d/Parkinson targets) |
| **Second read of** | Member 3's block (does the conclusion answer the question as posed?) | Member 1's block (does the protocol described match what the models did?) | Member 2's block (do the conclusions follow from the results?) |
| **Final job** | Fill names and emails on the report title and slide 1 | Check every number in Tables 3, 4 and 6 against the CSVs | Final pass: page limit (body + references <= 7 pages), no red placeholders left, consistent fonts |

## Checklists

### Member 1: Question, data and protocol
Slides 1-6, report Abstract to 4.2.
- [ ] Question wording is the same on slide 2, slide 3, report Section 2 and the abstract.
- [ ] Dataset numbers match `results/eda_summary.csv`: 176 tokens, 101,393 daily rows, 14,623 weekly rows, 2024-09-14 to 2026-08-15, median 701 days per token.
- [ ] Cleaning steps in report 3.3 match `load_data` in `common.py`: rows dropped, log1p columns, cliff nulls filled (365 / 0, 51% of rows), fixed category lists, zero nulls after cleaning.
- [ ] EDA figures and numbers: Spearman 0.14 pooled, 0.22 per-token median, 74% of tokens positive, deciles 0.97 to 1.14 (Figure 1, slide 5).
- [ ] Fold table (report Table 2, slide 6 timeline) matches `make_folds`: cutoffs, train/test sizes, 30-day embargo, 90-day validation slice, 30-day purge.
- [ ] Ex-ante rule and the schedule-revision caveat are stated correctly (report 3.3, slide 4 notes).
- [ ] Baselines: persistence = log rv_past_14d, train-mean R2 about 0.17 (report 4.2).
- **Be ready for:** Why not k-fold cross-validation? Why a 30-day embargo? Why log volatility? How do you know the features are known at day D? Why is the train mean a stronger baseline than persistence?

### Member 2: Models and headline results
Slides 7-11, report 4.3, 5.1, 5.3, 5.4.
- [ ] Each model's grid in report 4.3 and on slide 7 matches its script (KNN `PARAM_GRID`, RF `PARAM_GRID`, `RIDGE_GRID`, `ENET_GRID`, `LGBM_GRID`, logistic `C_GRID`).
- [ ] Tuned settings quoted (KNN k = 100-250, RF leaves 50-100, Ridge alpha 1e4-1e7, Elastic Net all-zero in folds 1 and 3, LightGBM lr 0.02 / 200 trees) match `best_params` in `results/<model>.csv`.
- [ ] Table 3 and the slide 8 chart match `results/comparison_table.csv` (daily, `log_rv_fwd_14d`, subsample `all`).
- [ ] Table 4 per-fold deltas and the slide 9 chart: RF +0.031, +0.030, then negative; LightGBM gains only in fold 2.
- [ ] Interpretation numbers: RF permutation importance by group (0.031 / 0.010 / 0.005), Ridge coefficient +0.008 vs +0.040, LightGBM gain shares 92% / 4% / 4%, KNN neighbour example (104% vs 12.5%, 0.78 vs 0.55).
- [ ] Logistic Table 6 matches `results/logistic.csv` (AUC 0.694 vs 0.653 naive, delta AUC -0.002 and -0.004).
- **Be ready for:** Why these six models? Why does Ridge beat the tree models? Why did LightGBM do worst? Why is a gain of +0.006 R2 "noise"? What is permutation importance? Why no SMOTE in the logistic model?

### Member 3: Errors, relevance and conclusion
Slides 12-16 and Q&A, report 5.2, 5.5, 5.6, 6, References.
- [ ] Table 5 and the slide 12 chart match `results/error_by_group.csv` (Ridge +0.013 and RF +0.004 worse where unlocks exceed 5%, LightGBM +0.000).
- [ ] 2x-miss numbers (18% to 12%, 62% over-forecasts) and volatility-unit errors (0.27 points, 32%, 41% within 25%) match `results/error_level_summary.csv` and `error_big_misses.csv`.
- [ ] Robustness paragraph and the slide 13 table match `comparison_table.csv`: weekly, INTERNAL subsample, 7-day / 30-day / Parkinson targets; largest gain +0.017.
- [ ] Practical-relevance and human-review points (slide 14, report 5.6) are worded as judgement, not as measured facts.
- [ ] Conclusion (slide 15, report 6) says "six models agree" and answers the question from slide 2.
- [ ] References are complete and formatted consistently; every in-text citation has an entry.
- [ ] Final pass: body plus references within 7 pages, appendix after them, no red placeholder text left, Table A3 filled in with everyone's agreed split.
- **Be ready for:** Is a null result useful? Could unlocks matter in a crash? Does schedule revision bias the result? What would you do next? What should a risk desk actually do with this?

## Hand-overs (already in the speaker notes)
- End of slide 6, Member 1 to Member 2: "With the protocol fixed, [Member 2] will show what six models do under it."
- End of slide 11, Member 2 to Member 3: "On average the answer is no; [Member 3] will show where the remaining errors are and whether any of this matters in practice."

## Regenerating after a fix
Fix numbers at the source, not by hand in Word or PowerPoint. Rerun the script, then rebuild both files:

```bash
cd report/build
python build_report.py
python build_slides.py
```

Wording-only edits can go straight into the .docx/.pptx, but tell the others: the next rebuild overwrites them unless the same edit is made in `build_report.py` or `build_slides.py`.
