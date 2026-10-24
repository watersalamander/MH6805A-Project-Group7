# Group 7 presentation script (8 minutes, 13 slides)

About 970 words in total. At 130 words a minute that is about 7 min 30 s, so each
member speaks 300-390 words in 2.3 to 3 minutes, leaving about 30 s for slide changes and hand-overs. Every number below comes from
`results/` and matches the slides and the report. The lines for each slide are also
in that slide's speaker notes (PowerPoint: Slide Show > Presenter View), so nobody
needs a printout.

Practise with a timer. If you run long, slow down on the numbers and trim the examples; do not skip the hand-overs.

| Block | Slides | Speaker | Target time |
|---|---|---|---|
| Question, data, protocol and benchmarks | 1-5 | Member 1 | 3:05 |
| Models and headline results | 6-9 | Member 2 | 2:20 |
| Errors, relevance and conclusion | 10-13 | Member 3 | 2:25 |

---

## Slide 1 (Member 1, ~20 s)
Title: Do scheduled token unlocks help forecast crypto volatility?

Good morning, we are Group 7: [Member 1], [Member 2] and [Member 3]. Crypto tokens
publish their unlock calendars months in advance. Our question: does that calendar
help predict how volatile a token will be over the next two weeks?

## Slide 2 (Member 1, ~45 s)
Title: Do unlocks add anything beyond persistence?

Most of a token's supply is locked at launch and released on a published schedule,
and traders treat a big unlock as a volatility event, because new supply may be sold.
The catch is that volatility is very persistent: last fortnight already predicts the
next one well. So we ask whether unlocks add anything *beyond* that.

One comparison answers it. Every model is trained twice on the same rows and folds:
once on nine controls, such as trailing volatility and the BTC regime, and once with
23 unlock and allocation features added. The difference in out-of-sample R-squared is
our finding.

## Slide 3 (Member 1, ~40 s)
Title: In the raw data, volatility does rise with unlocks

Our data covers 176 tokens, daily, from September 2024 to August 2026: about 101,000
token-days, with prices from Binance and unlock schedules from Tokenomist.

The raw data does show a link. Sort token-days by how much of the float unlocks in the
next month, and forward volatility rises from about 0.97 in the lowest decile to 1.14
in the highest. The correlation is positive for 74% of tokens. But heavy-unlock tokens
are also young and already volatile. Is this just persistence in disguise?

## Slide 4 (Member 1, ~50 s)
Title: Walk-forward validation: never shuffle, never peek

To test that fairly, we never shuffle. Five walk-forward folds are cut by date: each
model trains on the past, skips a 30-day gap because the target looks 14 days ahead,
and is tested on the next 90 days.

Each candidate, meaning pre-processing, model and settings together, is chosen on a
validation slice at the end of the training window. It is then refit and scored once
on test, and no model was changed after seeing test results.

## Slide 5 (Member 1, ~35 s)
Title: Two simple benchmarks every model must beat

Every model is judged against two benchmarks that need no machine learning, scored
on exactly the same test rows. Persistence forecasts the next two weeks with the last
two; it is the zero point of our R-squared. The training mean ignores recent
volatility and forecasts the average, yet it beats persistence in four of five folds,
R-squared 0.17, because volatility mean-reverts. So a model has to beat 0.17, not
just zero, to be useful.

With the protocol and the benchmarks fixed, [Member 2] will show what five models do
under it.

## Slide 6 (Member 2, ~30 s)
Title: Five models, one shared harness

Thank you. We ran five models on that same harness:
- K-nearest neighbours, for similarity;
- Random Forest and LightGBM, for non-linear effects;
- Ridge and Elastic Net, as linear benchmarks (Elastic Net can drop features entirely).

Notice what validation chose: huge neighbourhoods, large leaves, strong penalties, the
slowest boosting. That already hints that the target is noisy relative to the signal.

## Slide 7 (Member 2, ~30 s)
Title: All models beat the benchmarks on controls alone

Here is the headline. Blue is controls only, orange adds the unlock features. Every
model beats persistence and the training-mean baseline of 0.17, with out-of-sample
R-squared between 0.22 and 0.27. Ridge on controls alone is as good as anything we
built.

But compare each blue bar with its orange partner. Adding 23 unlock features raises
R-squared by only 0.001 to 0.006.

## Slide 8 (Member 2, ~35 s)
Title: The small gain is noise: it flips sign across folds

Is even that gain real? Fold by fold, in calendar order, the Random Forest gains about
0.03 in the two oldest folds, then loses in the three most recent, which have the most
training data. KNN swings more, and LightGBM gains in just one fold.

Meanwhile R-squared itself moves by about 0.15 from fold to fold, 25 times the largest
average gain. A gain that flips sign like this is noise, not signal.

## Slide 9 (Member 2, ~45 s)
Title: Inside the models, unlock features barely register

We also looked inside each model with the tool that suits it. In the Random Forest,
the five most important features are all controls; the best unlock feature ranks
sixth, at about a fifth of trailing 30-day volatility.
In LightGBM, controls take 92% of the split gain. Ridge's largest unlock coefficient is
positive, as the story predicts, but five times smaller than trailing volatility. A
shallow tree never splits on an unlock feature. And for the most unlock-heavy token,
KNN finds no comparable history at all.

So on average the answer is no. [Member 3] will show where the remaining errors are,
and whether this matters in practice.

## Slide 10 (Member 3, ~45 s)
Title: Unlock features do not help even where unlocks are big

Thank you. If unlocks carried signal, it would show where unlocks are largest. Bars
above zero mean the unlock features made forecasts *worse*. Where more than 5% of the
float unlocks within a month, they make Ridge and the Random Forest worse, and
LightGBM gains nothing. The same two models are also worse just before a cliff unlock.

What the models really fix is large mistakes. Forecasts off by more than a factor of
two fall from 18% under persistence to 12%. Most misses that remain are over-forecasts
for tokens that suddenly calm down.

## Slide 11 (Member 3, ~25 s)
Title: The null result survives every robustness check

The result holds with weekly data, three other volatility measures, and only the
hand-curated tokens. The largest gain anywhere is 0.017, a tenth of the fold-to-fold
spread.

## Slide 12 (Member 3, ~40 s)
Title: Is any improvement useful for the decision?

Is any of this useful in practice? Errors are still large: the typical miss is about
0.27 volatility points, a third of the level, and on a typical day the model is no
closer than persistence. Its value is avoiding the big misses that matter for margins
and position limits.

Unlock features add nothing there, yet cost a data subscription and a pipeline. Our
advice to a risk desk: don't pay for them as a volatility input, and keep a person in
the loop for the cases on the right.

## Slide 13 (Member 3, ~35 s)
Title: Unlocks are not a reliable incremental volatility signal

To conclude:
- The raw link is real, but trailing volatility already explains it.
- Five models agree.
- The best forecaster is a simple Ridge model on the controls.
- This fits an efficient market: schedules are public months ahead, so the effect is
  likely priced in early.

Our limits are one market regime and today's schedule versions, which can only flatter
unlocks. Thank you. We are happy to take questions.

---

## Q&A: short answers to likely questions

| Question | Who | Short answer |
|---|---|---|
| Why not k-fold cross-validation? | Member 1 | Rows are time-ordered and a 14-day target overlaps between days. Shuffling would leak the future, so we use walk-forward folds with a 30-day embargo. |
| How do you know the features are known on day D? | Member 1 | Everything is computed from data up to the close of day D. The only forward-looking inputs are the published schedule columns. |
| Why does the training mean beat persistence? | Member 1 | Volatility mean-reverts: persistence over-reacts to the last two weeks. That is why we compare against both baselines. |
| Why did Ridge do best, and LightGBM worst? | Member 2 | The signal is a smooth mix of trailing volatility at several horizons. Shrinkage suits it; boosting finds little extra structure to exploit, so validation chose its most regularized settings. |
| Is +0.006 R-squared really nothing? | Member 2 | It is 25 times smaller than the fold-to-fold spread, flips sign over time, and wins in only one or two of five folds for the tree models. |
| Could unlocks matter in a crash? | Member 3 | Possibly. Our sample has no 2022-style stress period; we name that as a limit. |
| Does using today's schedules bias the result? | Member 3 | Yes, but toward finding an effect. Back-filled revisions make the unlock features look better, so the null result is, if anything, conservative. |
| Is a null result useful? | Member 3 | Yes. It saves a risk desk a paid data feed and stops forecasts being bumped for a widely believed but non-incremental story. |
