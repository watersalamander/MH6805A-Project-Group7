"""Build the draft final report (Word) from results/ and figures/."""
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from stats import (FOLDS, INTERNAL, LOGIT, MAIN, NAMES, REG, RFG, RFIMP, TARGETS,
                   WEEKLY, best_params)

ROOT = "D:/ML-project"
FIG = ROOT + "/figures/"
OUT = ROOT + "/report/Group7_Final_Report_DRAFT.docx"
INK = RGBColor(0x1F, 0x24, 0x33)
MUTED = RGBColor(0x5A, 0x60, 0x70)
PH = RGBColor(0xC0, 0x39, 0x2B)   # placeholder text the group must replace

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.0))
sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.8)

st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.08
for lvl, size in ((1, 13), (2, 11)):
    h = doc.styles[f"Heading {lvl}"]
    h.font.name, h.font.size, h.font.bold = "Calibri", Pt(size), True
    h.font.color.rgb = INK
    h.element.rPr.rFonts.set(qn("w:asciiTheme"), "")  # drop theme font so Calibri sticks
    h.paragraph_format.space_before = Pt(8 if lvl == 1 else 5)
    h.paragraph_format.space_after = Pt(3)
    h.paragraph_format.keep_with_next = True

# page numbers in footer
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
    r = fp.add_run()
    if kind:
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), kind); r._r.append(e)
    else:
        e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = text; r._r.append(e)
    r.font.size = Pt(9)


def para(text="", bold_lead=None, size=None, align=None, italic=False, color=None, after=None):
    p = doc.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead); r.bold = True
        if size: r.font.size = Pt(size)
    add_runs(p, text, size=size, italic=italic, color=color)
    if align is not None: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def add_runs(p, text, size=None, italic=False, color=None):
    """Very small markup: **bold**, `code`, [[placeholder]]."""
    import re
    for tok in re.split(r"(\*\*.+?\*\*|`.+?`|\[\[.+?\]\])", text):
        if not tok:
            continue
        if tok.startswith("**"):
            r = p.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("`"):
            r = p.add_run(tok[1:-1]); r.font.name = "Consolas"; r.font.size = Pt((size or 10.5) - 1)
            continue
        elif tok.startswith("[["):
            r = p.add_run("[" + tok[2:-2] + "]"); r.font.color.rgb = PH; r.bold = True
        else:
            r = p.add_run(tok)
        if size: r.font.size = Pt(size)
        if italic: r.italic = True
        if color: r.font.color.rgb = color


def bullets(items, size=None):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, it, size=size)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), hexcolor)
    tcPr.append(s)


def table(header, rows, widths, size=8.5, bold_rows=(), caption=None, left_cols=(0,)):
    if caption:
        cap = para(caption, size=9, italic=False, color=MUTED, after=2)
        cap.runs[0].bold = True
        cap.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate([header] + rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.width = Cm(widths[j])
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT if j in left_cols else WD_ALIGN_PARAGRAPH.CENTER
            add_runs(p, str(val), size=size)
            if i == 0:
                for r in p.runs: r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255)
                shade(c, "1F2433")
            elif i in bold_rows:
                for r in p.runs: r.bold = True
            elif i % 2 == 0:
                shade(c, "F1F3F6")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def figure(path, width_cm, caption):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(FIG + path, width=Cm(width_cm))
    c = para(caption, size=9, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)


f3 = lambda x: f"{x:.3f}"
f4 = lambda x: f"{x:.4f}"
sg = lambda x: f"{(0.0 if abs(x) < 5e-4 else x):+.3f}"

# ---------------------------------------------------------------- title block
t = para("MH6805 Machine Learning in Finance  |  Group 7  |  Final Report (DRAFT)", size=9.5,
         align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=2)
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Do Scheduled Token Unlocks Help Forecast Crypto Volatility?"); r.bold = True; r.font.size = Pt(16); r.font.color.rgb = INK
t.paragraph_format.space_after = Pt(2)
para("Walk-forward evidence from 176 tokens and five machine-learning models", size=11, italic=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=4)
para("[[Member 1 name, NTU email]]   [[Member 2 name, NTU email]]   [[Member 3 name, NTU email]]",
     size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, after=1)
para("Contribution of each member: see Table A3 in the appendix.", size=9, italic=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=6)

m = MAIN
para("We ask whether a token's published unlock (emission) schedule adds forecasting power for its forward 14-day "
     "realized volatility beyond what trailing volatility and the market regime already explain. On a panel of "
     f"176 tokens over 2024-09 to 2026-08 (101,393 token-days) we run K-nearest neighbours, Random Forest, Ridge, Elastic "
     "Net and logistic regression twice, once on nine control features and once on controls plus 23 emission and static "
     "features, under a strict five-fold walk-forward protocol with embargo. Every regressor beats both the persistence "
     f"forecast and the pooled-mean baseline (out-of-sample R\u00b2 of {m['knn']['CONTROLS']['r2_oos']:.2f} to "
     f"{m['ridge']['CONTROLS']['r2_oos']:.2f} against persistence), but that gain comes from the controls. Adding the "
     f"unlock features changes out-of-sample R\u00b2 by +0.001 to +0.006 on average, against a fold-to-fold standard "
     "deviation of about 0.15, and the sign of the change flips between folds. The classification view agrees: the "
     "unlock features lower ROC-AUC slightly. Although forward volatility does rise with unlock pressure in the raw data, "
     "that relationship is absorbed by trailing volatility once it is controlled for. We conclude that, in this panel, "
     "scheduled unlocks are not a reliable incremental volatility signal.", bold_lead="Abstract. ", size=10)

# ---------------------------------------------------------------- 1 intro
doc.add_heading("1  Introduction", 1)
para("Most crypto tokens are not fully in circulation at launch. Team, investor and ecosystem allocations are locked "
     "and released on a published vesting schedule, and data vendors such as Tokenomist track these \u201cunlocks\u201d "
     "token by token. Market commentary routinely treats a large upcoming unlock as a volatility event: new supply reaches "
     "holders who may sell, so prices are expected to move more around the unlock date. Because the schedule is public "
     "in advance, it is one of the few forward-looking inputs a forecaster can legitimately use.")
para("Volatility forecasting matters for position sizing, option pricing, margin setting and risk limits, and it is a "
     "well-studied problem: realized volatility is highly persistent, so yesterday's volatility is a strong forecast of "
     "tomorrow's (Andersen et al., 2003; Corsi, 2009). Any new feature therefore has to beat a demanding benchmark. This "
     "project tests whether unlock information clears that bar, using the machine-learning methods covered in MH6805 "
     "and a protocol designed so that the result can be trusted as an out-of-sample statement.")

# ---------------------------------------------------------------- 2 problem
doc.add_heading("2  Problem Statement and Objectives", 1)
para("**Research question.** Do scheduled token-unlock features add forecasting power for a token's forward 14-day "
     "realized volatility **beyond** volatility persistence and the market regime?")
para("The question is about incremental value, not about whether a good volatility model can be built. We therefore "
     "fix the design so that the answer is read off one comparison: every model is trained twice, on **control features "
     "only** and on **controls + emission + static features**, with identical rows, folds and tuning. The difference "
     "between the two runs is the finding; a null or negative difference is a valid result. Our objectives are:")
bullets([
    "**O1.** Build a leakage-free token-day panel in which every input is known at the close of day D.",
    "**O2.** Forecast log forward 14-day realized volatility with at least four regression models (KNN, Random Forest, "
    "Ridge, Elastic Net) and benchmark them against persistence and the training mean.",
    "**O3.** Measure the incremental contribution of unlock features per model and per fold, and check its stability "
    "across panel frequency, alternative targets and a hand-curated token subsample.",
    "**O4.** Re-ask the question as classification (logistic regression on high-volatility events) and interpret what "
    "the models learn from unlock features.",
])

# ---------------------------------------------------------------- 3 data
doc.add_heading("3  Dataset", 1)
doc.add_heading("3.1  Sources and construction", 2)
para("The panel combines two real data sources. **Prices** are Binance USDT-pair daily klines (open, high, low, close), "
     "from which we compute returns and realized volatility. **Unlock schedules and allocations** come from the "
     "Tokenomist API (daily emission, unlock events and allocation endpoints). The universe is the 176 tokens that have "
     "both a Tokenomist schedule and a Binance USDT pair; the sample runs from 2024-09-14 to 2026-08-15 (one row per "
     "token per calendar day, 101,393 rows after cleaning; median 701 days per token). A weekly panel (first day of "
     "each ISO week, 14,623 rows) is used as a robustness check because daily rows of a 14-day target overlap heavily.")
doc.add_heading("3.2  Target and features", 2)
para("The target is y = log(RV\u2081\u2084), where RV\u2081\u2084 is the annualized realized volatility of daily "
     "close-to-close log returns over days D+1 to D+14, \u221a(365/14 \u00b7 \u03a3 r\u00b2). Logging makes the "
     "heavy-tailed target close to symmetric, and all errors are reported in log-volatility space. Features fall into "
     "three groups (full list in Table A1):")
table(["Group", "#", "Features", "Role"], [
    ["CONTROLS", "9", "Trailing RV (7, 14, 30d), trailing return (7, 30d), BTC and ETH 14d RV, log market cap, days since launch",
     "Persistence, momentum, market regime, size, age"],
    ["EMISSION", "13", "Share of float unlocking in next 7/30/90d, 30d share of total supply, days to and size of next cliff, "
     "has-cliff flag, 30d unlocks split by six recipient groups", "Forward-looking, published schedule"],
    ["STATIC", "10", "Allocation shares of six recipient groups, Tokenomist listing method (3 one-hots), unlock precision",
     "Token design, data quality"],
], [2.2, 0.8, 9.6, 4.4], left_cols=(0, 2, 3), caption="Table 1. Feature groups. FULL = all 32 features.")
doc.add_heading("3.3  Pre-processing and leakage control", 2)
para("Cleaning is a fixed, deterministic step with nothing learned from the data: rows without a target or without 30 days "
     "of price history are dropped; long-tailed emission ratios are log1p-transformed; the two structurally missing cliff "
     "columns are filled (days to next cliff = 365, size = 0) for the 51% of rows with no remaining cliff; categorical "
     "columns are encoded with fixed category lists. After cleaning no feature has missing values. The **ex-ante rule** is "
     "enforced throughout: a feature must be known at the close of D, the targets are never inputs, and the only "
     "forward-looking inputs are the published schedule columns. One caveat cannot be engineered away: schedules are "
     "the version curated on the pull date (2026-09-14), so later revisions are reflected in the past (Section 6).")
doc.add_heading("3.4  Exploratory analysis", 2)
para("Unlock pressure is concentrated: in half of all token-days less than 1% of the float unlocks in the next 30 days, "
     "while the top decile faces a median of 8.4%. Figure 1 shows that forward volatility does rise with unlock pressure: "
     "mean RV\u2081\u2084 climbs from about 0.97 in the lowest decile to 1.14 in the highest. The pooled Spearman "
     "correlation between 30-day unlock pressure and the target is 0.14, the per-token median is 0.22 and it is positive "
     "for 74% of tokens. The raw relationship is therefore real; the question is whether it survives once trailing "
     "volatility, which is itself correlated with unlock pressure (young, high-emission tokens are volatile), is controlled for.")
figure("eda_decile_emission_vs_rv.png", 11.5, "Figure 1. Forward 14-day realized volatility by decile of 30-day unlock "
       "pressure (share of float unlocking), daily panel.")

# ---------------------------------------------------------------- 4 methods
doc.add_heading("4  Methodology", 1)
doc.add_heading("4.1  Walk-forward validation (no shuffling)", 2)
para("Rows of a panel time series are not exchangeable, and a 14-day forward target makes neighbouring days share most of "
     "their future. We therefore never shuffle and never use k-fold cross-validation. Five walk-forward folds are cut by "
     "calendar date with all tokens pooled, cutoffs every 90 days over the last 450 days (Table 2). For cutoff c, "
     "training uses dates \u2264 c \u2212 30 days (a 30-day embargo, longer than the 14-day target horizon, following "
     "L\u00f3pez de Prado, 2018) and testing uses the 90 days after c. Hyper-parameters are tuned inside each fold: "
     "the last 90 days of training are a validation slice, candidate models are fit on the training data before it "
     "(with a further 30-day purge) and scored by validation RMSE; the best configuration is refit on all training data "
     "and scored **once** on the test window. Tuning never sees test data. All scalers and transformers sit inside a "
     "scikit-learn Pipeline, so they are fit on the training slice of the current fold only; random_state = 42 everywhere.")
table(["Fold", "Cutoff", "Train rows", "Test rows", "Test window"],
      [[f, c, f"{a:,}", f"{b:,}", f"{c} + 90 days"] for f, c, a, b in FOLDS],
      [1.4, 2.8, 2.6, 2.6, 4.2], caption="Table 2. Walk-forward folds (daily panel). The training window expands.")
doc.add_heading("4.2  Benchmarks and metrics", 2)
para("Two model-free benchmarks are reported. **Persistence** forecasts y with log(RV past 14d), the natural random-walk "
     "volatility forecast. The **training mean** forecasts the pooled mean of y in the training window. The headline metric "
     "is the out-of-sample R\u00b2 against persistence (Campbell and Thompson, 2008), R\u00b2_oos = 1 \u2212 SSE_model / "
     "SSE_persistence: zero means the model ties persistence. We also report RMSE, MAE and Spearman rank correlation in "
     "log space. Because the training mean already beats persistence (R\u00b2_oos \u2248 0.17), models are judged "
     "against both benchmarks, and the unlock question is judged by the **paired, per-fold difference** "
     "\u0394 = R\u00b2_oos(FULL) \u2212 R\u00b2_oos(CONTROLS).")
doc.add_heading("4.3  Models", 2)
kp = best_params(__import__("stats").D, "knn", "FULL")
para("**K-nearest neighbours (KNN).** A non-parametric, distance-based regressor: the forecast is the (optionally "
     "distance-weighted) average target of the k most similar training token-days. A QuantileTransformer maps each "
     "feature to a normal scale so that no feature dominates the distance. Grid: k \u2208 {5, 10, 25, 50, 100, 250} \u00d7 "
     "{uniform, distance} weights. Tuning chose very large neighbourhoods (k = 100 to 250 in every fold), already a "
     "sign that the target is noisy relative to the feature signal. KNN is also run on CONTROLS+EMIS5 (controls plus the "
     "five headline unlock columns) to separate the information in unlock features from the curse of dimensionality.")
para("**Random Forest (RF).** An ensemble of 400 bootstrapped regression trees with random feature subsets (Breiman, 2001), "
     "which captures non-linearities and interactions, for example an unlock effect that matters only in calm markets. "
     "Grid: max_depth \u2208 {None, 8, 12, 16} \u00d7 min_samples_leaf \u2208 {20, 50, 100} \u00d7 max_features \u2208 "
     "{sqrt, 0.33, 0.5}; daily runs evaluate a fixed seeded subset of 12 configurations for run time. Tuning consistently "
     "chose large leaves (50 to 100 rows), i.e. heavy smoothing. We interpret the FULL model with permutation importance "
     "on the last fold's test set and partial dependence plots.")
para("**Ridge regression.** Linear regression with an L2 penalty (Hoerl and Kennard, 1970), a strong benchmark for "
     "correlated predictors such as the three trailing-volatility windows. Volatility controls are logged inside the "
     "pipeline (a fixed transform) and all features standardized. Grid: \u03b1 \u2208 {0.1, \u2026, 10\u2077}. "
     "**Elastic Net** adds an L1 penalty (Zou and Hastie, 2005), which can set coefficients exactly to zero and so "
     "performs feature selection: if unlock features carry signal, Elastic Net should keep them. Grid: "
     "\u03b1 \u2208 {10\u207b\u2074, \u2026, 1} \u00d7 l1_ratio \u2208 {0.1, 0.5, 0.9}.")
para("**Logistic regression.** A classification view of the same question with an L2-penalised logistic model "
     "(C \u2208 {10\u207b\u2075, \u2026, 10}, tuned by validation log loss). Two events are defined from the forward target: "
     "**top20_xs**, the token is in the top 20% of forward volatility across all tokens on date D (base rate 20%); and "
     "**spike_1.5x**, forward volatility exceeds 1.5\u00d7 the token's own trailing 30-day volatility (base rate 14%). "
     "We report threshold-free ROC-AUC and PR-AUC and the Brier skill score versus the training base rate; no "
     "resampling is used, since it would distort probabilities and the metrics do not depend on a threshold.")

# ---------------------------------------------------------------- 5 results
doc.add_heading("5  Results", 1)
doc.add_heading("5.1  Headline comparison", 2)
rows = []
for k in REG:
    r = m[k]
    rows.append([NAMES[k], f3(r["CONTROLS"]["r2_oos"]), f3(r["FULL"]["r2_oos"]), sg(r["delta"]),
                 f"{r['wins']}/5", f4(r["CONTROLS"]["rmse"]), f4(r["FULL"]["rmse"]),
                 f3(r["CONTROLS"]["spearman"]), f3(r["FULL"]["spearman"])])
rows.append(["Train mean", f3(m["train_mean"]["r2_oos"]), "\u2013", "\u2013", "\u2013", f4(m["train_mean"]["rmse"]), "\u2013", "\u2013", "\u2013"])
rows.append(["Persistence", "0.000", "\u2013", "\u2013", "\u2013", f4(m["persistence"]["rmse"]), "\u2013", "\u2013", "\u2013"])
table(["Model", "R\u00b2oos CTRL", "R\u00b2oos FULL", "\u0394", "FULL wins", "RMSE CTRL", "RMSE FULL", "\u03c1 CTRL", "\u03c1 FULL"],
      rows, [2.8, 1.8, 1.8, 1.4, 1.5, 1.9, 1.9, 1.6, 1.6],
      caption="Table 3. Test-set results, daily panel, target log RV\u2081\u2084, mean of 5 folds. \u0394 = FULL \u2212 "
              "CONTROLS in R\u00b2oos; \u201cFULL wins\u201d counts folds with \u0394 > 0; \u03c1 = Spearman.")
para("Table 3 and Figure 2 give the main result. **All four regressors beat both benchmarks**: R\u00b2_oos against "
     f"persistence is {m['knn']['CONTROLS']['r2_oos']:.2f} to {m['ridge']['CONTROLS']['r2_oos']:.2f} on controls alone, "
     f"against {m['train_mean']['r2_oos']:.2f} for the training mean, and RMSE falls from {m['persistence']['rmse']:.3f} "
     f"(persistence) to about 0.443. Linear models are as good as the non-linear ones: Ridge on controls "
     f"({m['ridge']['CONTROLS']['r2_oos']:.3f}) ties the Random Forest on the full feature set "
     f"({m['rf']['FULL']['r2_oos']:.3f}). **Adding the 23 unlock and static features barely moves any model**: the "
     f"mean \u0394 is between +0.001 and +0.006, while the standard deviation of R\u00b2_oos across folds is "
     f"{min(m[k]['CONTROLS']['r2_std'] for k in REG):.2f} to {max(m[k]['CONTROLS']['r2_std'] for k in REG):.2f}. "
     "FULL beats CONTROLS in only two or three folds out of five for every model. For KNN the R\u00b2_oos rises slightly "
     "while the mean RMSE gets worse, a reminder that these differences are within noise.")
figure("compare_r2_oos.png", 16.5, "Figure 2. Out-of-sample R\u00b2 against persistence, controls only (blue) vs FULL (orange); "
       "bars = \u00b11 s.d. across folds; dotted line = training-mean baseline.")

doc.add_heading("5.2  Stability across folds", 2)
rows = [[NAMES[k]] + [sg(v) for v in m[k]["delta_folds"]] + [sg(m[k]["delta"])] for k in REG]
table(["Model", "Fold 1", "Fold 2", "Fold 3", "Fold 4", "Fold 5", "Mean"], rows, [3.0, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8],
      caption="Table 4. Per-fold \u0394R\u00b2oos (FULL \u2212 CONTROLS), daily panel. Folds are in calendar order.")
para("Table 4 shows why the small average gains should not be read as a signal. For the Random Forest the gain is "
     "+0.031 and +0.030 in the two oldest folds and negative in the three most recent ones; KNN shows the same pattern with larger "
     "swings (+0.104 in fold 1, \u22120.058 in fold 3). A feature block that helps early and hurts later, with the "
     "most recent folds trained on the most data, is what a chance result looks like. The linear models' differences "
     "are an order of magnitude smaller still (|\u0394| < 0.008), because they keep the unlock coefficients close to zero.")

doc.add_heading("5.3  What the models learn from unlock features", 2)
para("**Random Forest.** Permutation importance on the last fold's test set (Figure A2) ranks trailing 30d, 14d and 7d "
     "volatility, trailing 30-day return and token age as the five most important features. Summed by group, shuffling "
     f"the controls raises test RMSE by {RFG['controls']:.3f}, the 13 emission features by {RFG['emission']:.3f} and the "
     f"10 static features by {RFG['static']:.3f}. The best emission feature (90-day unlock share) is worth 1.5 to 5 times "
     "less than each of the top five controls. Partial dependence on 30-day unlock pressure is nearly flat in every BTC "
     "volatility regime (Figure A3), and dropping the aggregate 30-day column does not make the six recipient-split "
     "columns carry the signal (test RMSE 0.5088 vs 0.5083).")
para("**Ridge and Elastic Net.** Validation selected strong penalties: Ridge chose \u03b1 = 10\u2074 to 10\u2077, and "
     "Elastic Net set **every** coefficient to zero in folds 1 and 3, i.e. it fell back to the training mean, which "
     "on validation data was hard to beat. In the remaining folds the largest standardized coefficients are trailing "
     "30-day volatility (+0.04 log-vol per s.d.), token age (\u22120.03) and ETH volatility (\u22120.03); the largest "
     "unlock coefficient, the 90-day unlock share, is +0.008, positive as the narrative predicts but small (Figure A4).")
para("**KNN.** KNN is the only model whose best variant is not CONTROLS or FULL: CONTROLS+EMIS5 reaches "
     f"{m['knn']['CONTROLS+EMIS5']['r2_oos']:.3f} (daily) against {m['knn']['FULL']['r2_oos']:.3f} for FULL. With 23 extra "
     "dimensions the neighbourhoods are diluted by uninformative distances, so for a distance-based learner a small, "
     "relevant feature set matters more than a large one.")

doc.add_heading("5.4  Classification view (logistic regression)", 2)
L = LOGIT
rows = []
for lab, name in (("top20_xs", "Top 20% cross-section"), ("spike_1.5x", "Spike > 1.5\u00d7 own 30d vol")):
    c, f = L.loc[(lab, "daily", "CONTROLS")], L.loc[(lab, "daily", "FULL")]
    naive = f3(L.loc[(lab, "daily", "NONE")]["auc"]) if (lab, "daily", "NONE") in L.index else "\u2013"
    rows.append([name, naive, f3(c.auc), f3(f.auc), sg(f.auc - c.auc), f3(c.pr_auc), f3(f.pr_auc), f3(c.brier_skill), f3(f.brier_skill)])
table(["Event", "AUC naive", "AUC CTRL", "AUC FULL", "\u0394AUC", "PR-AUC CTRL", "PR-AUC FULL", "BSS CTRL", "BSS FULL"],
      rows, [3.6, 1.6, 1.6, 1.6, 1.4, 1.8, 1.8, 1.5, 1.5],
      caption="Table 5. Logistic regression, daily panel, mean of 5 folds. Naive = rank by trailing 14d volatility; "
              "BSS = Brier skill score vs the training base rate.")
para("Logistic regression on controls identifies high-volatility events clearly better than ranking by trailing "
     "volatility (AUC 0.694 vs 0.653 for the cross-sectional event). Adding unlock features lowers ROC-AUC, PR-AUC and "
     "Brier skill for both events on both panels (Figure A5). Unlock schedules therefore do not help pick out the tokens "
     "that will be most volatile, nor anticipate a jump in a token's own volatility.")

doc.add_heading("5.5  Robustness", 2)
W = WEEKLY
para("The reading does not depend on the specification. On the **weekly panel**, which removes most overlap between rows, "
     f"\u0394 is {sg(W['rf']['delta'])} (RF), {sg(W['knn']['delta'])} (KNN), {sg(W['ridge']['delta'])} (Ridge) and "
     f"{sg(W['enet']['delta'])} (Elastic Net); the Ridge gain comes almost entirely from fold 1 (+0.082) and is negative "
     "in two other folds. For **alternative targets** (7-day, 30-day and Parkinson high-low 14-day volatility) the linear "
     f"models' \u0394 stays between +0.001 and +0.011 (Ridge on the Parkinson target is the one case where FULL wins all five "
     "folds, still by only +0.011), while the RF FULL model reaches R\u00b2_oos of "
     f"{TARGETS['log_rv_fwd_14d_parkinson']['rf']['FULL']['r2_oos']:.2f}, {TARGETS['log_rv_fwd_7d']['rf']['FULL']['r2_oos']:.2f} "
     f"and {TARGETS['log_rv_fwd_30d']['rf']['FULL']['r2_oos']:.2f}, showing that the pipeline and controls generalise. "
     "On the **hand-curated subsample** (tokens whose schedules Tokenomist maintains internally, where data should be "
     f"cleanest) the RF gap is the largest we observe, {sg(INTERNAL['rf']['delta'])}, but still about a tenth of the fold "
     f"spread, and it is {sg(INTERNAL['ridge']['delta'])} for Ridge and {sg(INTERNAL['enet']['delta'])} for Elastic Net. "
     "Full robustness numbers are in Table A2.")

doc.add_heading("5.6  Model comparison and selection", 2)
para("For the forecasting task itself, **Ridge on the control features** is our recommended model: it has the best or "
     "joint-best R\u00b2_oos and RMSE, the highest rank correlation, it trains in seconds, and its coefficients are "
     "interpretable. The Random Forest is a close second and the better choice if interactions or alternative targets "
     "matter (it is best on the 30-day and Parkinson targets). Elastic Net confirms the feature-selection reading by "
     "discarding unlock features, and KNN is the weakest regressor, sensitive to the dimension of the feature space. "
     "For the research question, the choice of model does not matter: **no model, linear or non-linear, extracts reliable "
     "incremental information from unlock schedules**.")

# ---------------------------------------------------------------- 6 conclusion
doc.add_heading("6  Discussion and Conclusion", 1)
para("**Answer.** Once trailing volatility and the market regime are controlled for, scheduled token unlocks do not add "
     "reliable forecasting power for 14-day forward realized volatility in this panel. Five model families agree, the "
     "average gain is tiny relative to fold-to-fold variation, its sign is unstable over time, and the classification "
     "view shows a small loss. We did not tune the protocol or feature set to change this result.")
para("**Interpretation.** The raw correlation between unlock pressure and forward volatility (Figure 1) is real but not "
     "incremental: tokens with heavy unlocks are typically young, small and already volatile, and that information is "
     "already in their trailing volatility. Because schedules are public long in advance, any predictable effect on "
     "trading activity is plausibly priced and traded around before the event, consistent with semi-strong market "
     "efficiency (Fama, 1970). For practitioners, a large upcoming unlock is not a reason to raise a volatility forecast "
     "that already reflects the token's recent behaviour.")
para("**Limitations.** (i) The sample covers a single, calm-to-moderate regime (2024-09 to 2026-08) without a 2022-style "
     "stress episode; unlocks may matter more when liquidity is thin. (ii) Schedules are the version curated on the pull "
     "date, so revised schedules are back-filled; this can only flatter the unlock features, which strengthens the null. "
     "(iii) Static allocation data are a snapshot. (iv) Only 176 tokens with Binance USDT pairs are covered, which "
     "favours larger, more liquid tokens. (v) Daily RF runs used a subset of the hyper-parameter grid for run time.")
para("**Future work.** Event-study designs around large cliff unlocks (rather than a pooled daily forecast); intraday "
     "data to look at the hours around an unlock; interactions with liquidity, order-book depth and derivatives funding; "
     "point-in-time snapshots of schedules to remove revision bias; and gradient-boosted trees or HAR-style models with "
     "unlock terms as further model families.")

# ---------------------------------------------------------------- references
doc.add_heading("References", 1)
refs = [
    "Andersen, T. G., Bollerslev, T., Diebold, F. X., and Labys, P. (2003). Modeling and forecasting realized volatility. Econometrica, 71(2), 579\u2013625.",
    "Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5\u201332.",
    "Campbell, J. Y., and Thompson, S. B. (2008). Predicting excess stock returns out of sample: Can anything beat the historical average? Review of Financial Studies, 21(4), 1509\u20131531.",
    "Corsi, F. (2009). A simple approximate long-memory model of realized volatility. Journal of Financial Econometrics, 7(2), 174\u2013196.",
    "Fama, E. F. (1970). Efficient capital markets: A review of theory and empirical work. Journal of Finance, 25(2), 383\u2013417.",
    "Hoerl, A. E., and Kennard, R. W. (1970). Ridge regression: Biased estimation for nonorthogonal problems. Technometrics, 12(1), 55\u201367.",
    "L\u00f3pez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.",
    "Parkinson, M. (1980). The extreme value method for estimating the variance of the rate of return. Journal of Business, 53(1), 61\u201365.",
    "Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825\u20132830.",
    "Zou, H., and Hastie, T. (2005). Regularization and variable selection via the elastic net. Journal of the Royal Statistical Society: Series B, 67(2), 301\u2013320.",
    "Data: Tokenomist API (emission, unlock events and allocation endpoints), pulled 2026-09-14; Binance spot market data API (daily klines).",
]
for rf in refs:
    p = para(rf, size=9, after=1); p.paragraph_format.left_indent = Cm(0.6); p.paragraph_format.first_line_indent = Cm(-0.6)

# ---------------------------------------------------------------- appendix
p = doc.add_paragraph(); p.add_run().add_break(WD_BREAK.PAGE)
doc.add_heading("Appendix (not counted toward the 7-page limit)", 1)
A1 = [
    ["rv_past_7d / 14d / 30d", "CONTROLS", "Annualized realized vol of the last 7 / 14 / 30 daily log returns"],
    ["ret_past_7d / 30d", "CONTROLS", "Trailing 7 / 30-day log return"],
    ["btc_rv_past_14d, eth_rv_past_14d", "CONTROLS", "14-day realized vol of BTC and ETH (market regime)"],
    ["log_mcap_pit", "CONTROLS", "Log point-in-time market cap (close price \u00d7 point-in-time float)"],
    ["days_since_tge", "CONTROLS", "Days since launch proxy (first candle or first emission)"],
    ["emis_next_7d/30d/90d_pct_float", "EMISSION", "Tokens unlocking in next 7/30/90 days \u00f7 current float (log1p)"],
    ["emis_next_30d_pct_total", "EMISSION", "Next-30-day unlocks \u00f7 total supply"],
    ["days_to_next_cliff", "EMISSION", "Days to next cliff unlock (365 if none)"],
    ["next_cliff_pct_float", "EMISSION", "Size of next cliff \u00f7 float (log1p, 0 if none)"],
    ["has_unlock_events", "EMISSION", "Token has at least one cliff event"],
    ["emis_next_30d_<group>_pct_float (6)", "EMISSION", "Next-30-day unlocks to founders/team, private investors, community, public investors, reserve, others"],
    ["alloc_share_<group> (6)", "STATIC", "Share of total allocation to each of the six recipient groups"],
    ["listedMethod (3 one-hots)", "STATIC", "How Tokenomist curates the schedule: INTERNAL, AI, EXTERNAL"],
    ["unlockPrecision_ord", "STATIC", "Time granularity of cliff events (second ... month), ordinal; unknown if none"],
    ["log rv_fwd_14d (y)", "TARGET", "Primary target; robustness: log rv_fwd_7d, rv_fwd_30d, Parkinson 14d"],
]
table(["Column", "Group", "Definition"], A1, [5.6, 2.2, 9.2], size=8, left_cols=(0, 2), caption="Table A1. Feature and target definitions (after cleaning).")

rows = []
for lab, d, sub in (("Daily, all tokens (main)", MAIN, None), ("Weekly panel", WEEKLY, None), ("INTERNAL subsample", INTERNAL, None)):
    for k in REG:
        if k in d and "delta" in d[k]:
            rows.append([lab, NAMES[k], f3(d[k]["CONTROLS"]["r2_oos"]), f3(d[k]["FULL"]["r2_oos"]), sg(d[k]["delta"]), f"{d[k]['wins']}/5"])
tn = {"log_rv_fwd_7d": "Target 7d RV", "log_rv_fwd_30d": "Target 30d RV", "log_rv_fwd_14d_parkinson": "Target Parkinson 14d"}
for t, lab in tn.items():
    for k in REG:
        d = TARGETS[t].get(k)
        if not d:
            continue
        if "delta" in d:
            rows.append([lab, NAMES[k], f3(d["CONTROLS"]["r2_oos"]), f3(d["FULL"]["r2_oos"]), sg(d["delta"]), f"{d['wins']}/5"])
        elif "FULL" in d:
            rows.append([lab, NAMES[k], "not run", f3(d["FULL"]["r2_oos"]), "\u2013", "\u2013"])
table(["Specification", "Model", "R\u00b2oos CTRL", "R\u00b2oos FULL", "\u0394", "FULL wins"], rows,
      [4.4, 3.0, 2.2, 2.2, 1.8, 1.8], size=8, caption="Table A2. Robustness: mean R\u00b2oos over 5 folds.")

table(["Member", "Models", "Data & EDA", "Methods", "Results", "Report", "Slides"], [
    ["[[Member 1]]", "[[e.g. KNN, RF]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
    ["[[Member 2]]", "[[e.g. Ridge, Elastic Net]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
    ["[[Member 3]]", "[[e.g. Logistic]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
], [2.8, 3.6, 1.8, 1.8, 1.8, 1.8, 1.8], size=8.5, caption="Table A3. Contribution of each member (to be completed by the group).")

figure("knn_val_rmse_vs_k.png", 12, "Figure A1. KNN validation RMSE against k (mean over folds), by feature set.")
figure("rf_permutation_importance_top15.png", 13, "Figure A2. Random Forest (FULL, last fold): permutation importance on the test set, top 15 features.")
figure("rf_pdp_emis30_x_btc.png", 11, "Figure A3. Random Forest partial dependence on 30-day unlock pressure across BTC volatility regimes.")
figure("linear_coefs_full.png", 15, "Figure A4. Ridge and Elastic Net standardized coefficients (FULL, daily); bars = mean over folds, whiskers = min/max.")
figure("logistic_auc.png", 15, "Figure A5. Logistic regression test ROC-AUC, controls vs FULL; dashed = rank by trailing 14d volatility.")
figure("eda_correlation_heatmap.png", 13, "Figure A6. Spearman correlations between target, controls and emission features.")
para("Code and data: the full pipeline is in MH6805_token_unlock_volatility.ipynb (repository "
     "github.com/watersalamander/MH6805A-Project-Group7), with per-fold results in results/ and figures in figures/.", size=9)

import os
os.makedirs(ROOT + "/report", exist_ok=True)
doc.save(OUT)
print("saved", OUT)
