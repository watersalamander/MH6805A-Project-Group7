"""Build the draft final report (Word) from results/ and figures/.

Run from this folder: python build_report.py
Type scale (two text sizes only): BODY for every prose paragraph, list item and
reference; SMALL for table text, captions and the header line. Inline markup:
**bold**, [[placeholder]] (red), _{sub} and ^{sup}.
"""
import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import stats
from stats import (ERR_BM, ERR_G, ERR_LV, FOLDS, INTERNAL, LOGIT, MAIN, NAMES, REG,
                   RFG, TARGETS, WEEKLY)

ROOT = "D:/ML-project"
FIG = ROOT + "/figures/"
OUT = ROOT + "/report/Group7_Final_Report_DRAFT.docx"
FONT = "Calibri"
BODY, SMALL, H1, H2, TITLE = 11, 9, 13, 11, 16
INK = RGBColor(0x1F, 0x24, 0x33)
MUTED = RGBColor(0x5A, 0x60, 0x70)
PH = RGBColor(0xC0, 0x39, 0x2B)   # placeholder text the group must replace

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
sec.left_margin = sec.right_margin = Cm(2.0)
sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.8)


def set_font(style, size, bold=None, color=None):
    style.font.name, style.font.size = FONT, Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts"); rpr.append(rfonts)
    for att in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(att), FONT)
    for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(att)) is not None:
            del rfonts.attrib[qn(att)]


st = doc.styles["Normal"]
set_font(st, BODY)
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.05
for name in ("List Bullet", "Table Grid"):
    set_font(doc.styles[name], BODY if name == "List Bullet" else SMALL)
for lvl, size in ((1, H1), (2, H2)):
    h = doc.styles[f"Heading {lvl}"]
    set_font(h, size, bold=True, color=INK)
    h.font.italic = False
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
    r.font.size = Pt(SMALL); r.font.name = FONT

TOKEN = re.compile(r"(\*\*.+?\*\*|\[\[.+?\]\]|_\{.+?\}|\^\{.+?\})")


def add_runs(p, text, size=BODY, italic=False, color=None, bold=False):
    for tok in TOKEN.split(text):
        if not tok:
            continue
        b = bold
        if tok.startswith("**"):
            tok, b = tok[2:-2], True
        if tok.startswith("[["):
            r = p.add_run("[" + tok[2:-2] + "]"); r.font.color.rgb = PH; r.bold = True
        elif tok.startswith("_{"):
            r = p.add_run(tok[2:-1]); r.font.subscript = True; r.bold = b
        elif tok.startswith("^{"):
            r = p.add_run(tok[2:-1]); r.font.superscript = True; r.bold = b
        else:
            r = p.add_run(tok); r.bold = b
            if color is not None:
                r.font.color.rgb = color
        r.font.size = Pt(size); r.font.name = FONT
        r.italic = italic


def para(text="", lead=None, size=BODY, align=WD_ALIGN_PARAGRAPH.JUSTIFY, italic=False,
         color=None, after=None):
    p = doc.add_paragraph()
    if lead:
        add_runs(p, lead, size=size, bold=True)
    add_runs(p, text, size=size, italic=italic, color=color)
    p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        add_runs(p, it)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), hexcolor)
    tcPr.append(s)


def caption(text):
    p = para(text, size=SMALL, color=MUTED, align=WD_ALIGN_PARAGRAPH.LEFT, after=2)
    p.runs[0].bold = True
    return p


def table(header, rows, widths, cap, left_cols=(0,)):
    caption(cap).paragraph_format.keep_with_next = True
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
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.keep_with_next = i < len(rows)   # keep the table on one page
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j in left_cols else WD_ALIGN_PARAGRAPH.CENTER
            add_runs(p, str(val), size=SMALL, bold=(i == 0))
            if i == 0:
                for r in p.runs:
                    r.font.color.rgb = RGBColor(255, 255, 255)
                shade(c, "1F2433")
            elif i % 2 == 0:
                shade(c, "F1F3F6")
    gap = doc.add_paragraph(); gap.paragraph_format.space_after = Pt(0)
    for r in gap.runs:
        r.font.size = Pt(SMALL)
    return t


def figure(path, width_cm, cap):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(FIG + path, width=Cm(width_cm))
    para(cap, size=SMALL, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)


f3 = lambda x: f"{x:.3f}"
f4 = lambda x: f"{x:.4f}"
sg = lambda x: f"{(0.0 if abs(x) < 5e-4 else x):+.3f}"
pct = lambda x: f"{100 * x:.0f}%"
R2 = "R^{2}_{oos}"
m = MAIN


def eg(dim, group, col):
    r = ERR_G[(ERR_G.dimension == dim) & (ERR_G.group == group)]
    return float(r[col].iloc[0])


# ---------------------------------------------------------------- title block
para("MH6805 Machine Learning in Finance  |  Group 7  |  Final Report (DRAFT)", size=SMALL,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=2)
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
add_runs(t, "Do Scheduled Token Unlocks Help Forecast Crypto Volatility?", size=TITLE, bold=True, color=INK)
t.paragraph_format.space_after = Pt(2)
para("Walk-forward evidence from 176 tokens and five machine-learning models", italic=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=4)
para("[[Member 1 name, NTU email]]   [[Member 2 name, NTU email]]   [[Member 3 name, NTU email]]",
     align=WD_ALIGN_PARAGRAPH.CENTER, after=1)
para("Contribution of each member: see Table A3 in the appendix.", size=SMALL, italic=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, color=MUTED, after=6)

para("We ask whether a token's published unlock (emission) schedule adds forecasting power for its forward 14-day "
     "realized volatility beyond what trailing volatility and the market regime already explain. On a panel of "
     "176 tokens over 2024-09 to 2026-08 (101,393 token-days) we run K-nearest neighbours, Random Forest, Ridge, "
     "Elastic Net and logistic regression twice, once on nine control features and once on controls plus 23 emission "
     "and static features, under a five-fold walk-forward protocol with embargo. Every regressor beats both the "
     f"persistence forecast and the pooled-mean baseline ({R2} of {m['knn']['CONTROLS']['r2_oos']:.2f} to "
     f"{m['ridge']['CONTROLS']['r2_oos']:.2f} against persistence), but that gain comes from the controls. Adding the "
     f"unlock features changes {R2} by +0.001 to +0.006 on average, against a fold-to-fold standard deviation of "
     "about 0.15, and the sign of the change flips between folds. Error analysis shows that the unlock features do not "
     "help even where unlocks are largest, and the classification view shows a small loss in ROC-AUC. We conclude "
     "that, in this panel, scheduled unlocks are not a reliable incremental volatility signal.", lead="Abstract. ")

# ---------------------------------------------------------------- 1 intro
doc.add_heading("1  Introduction", 1)
para("Most crypto tokens are not fully in circulation at launch. Team, investor and ecosystem allocations are locked "
     "and released on a published vesting schedule, and data vendors such as Tokenomist track these \u201cunlocks\u201d "
     "token by token. Market commentary routinely treats a large upcoming unlock as a volatility event: new supply reaches "
     "holders who may sell, so prices are expected to move more around the unlock date. Because the schedule is public "
     "in advance, it is one of the few forward-looking inputs a forecaster can legitimately use.")
para("Volatility forecasts drive position sizing, option pricing, margin setting and risk limits. Realized volatility is "
     "highly persistent, so recent volatility is already a strong forecast (Andersen et al., 2003; Corsi, 2009), and "
     "any new feature has to beat a demanding benchmark. This project tests whether unlock information clears that bar, "
     "using methods covered in MH6805 and a protocol designed so that the result is a genuine out-of-sample statement.")

# ---------------------------------------------------------------- 2 problem
doc.add_heading("2  Problem Statement and Objectives", 1)
para("Do scheduled token-unlock features add forecasting power for a token's forward 14-day realized volatility "
     "**beyond** volatility persistence and the market regime?", lead="Research question. ")
para("The question is about incremental value, not about whether a good volatility model can be built. Every model is "
     "therefore trained twice, on **control features only** and on **controls + emission + static features**, with "
     "identical rows, folds and tuning; the difference between the two runs is the finding, and a null or negative "
     "difference is a valid result. Our objectives are:")
bullets([
    "**O1.** Define the output Y and inputs X and build a leakage-free token-day panel in which every input is known at the close of day D.",
    "**O2.** Forecast Y with four regression models (KNN, Random Forest, Ridge, Elastic Net) and compare them with two "
    "simple baselines on the same test cases.",
    "**O3.** Measure the incremental contribution of unlock features per model and per fold, check its stability, and "
    "find which mistakes remain.",
    "**O4.** Re-ask the question as classification (logistic regression), interpret what each model uses, and judge "
    "whether any improvement is useful in practice.",
])

# ---------------------------------------------------------------- 3 data
doc.add_heading("3  Dataset", 1)
doc.add_heading("3.1  Sources and construction", 2)
para("The panel combines two real data sources. **Prices** are Binance USDT-pair daily klines (open, high, low, close), "
     "from which we compute returns and realized volatility. **Unlock schedules and allocations** come from the "
     "Tokenomist API (daily emission, unlock events and allocation endpoints). The universe is the 176 tokens that have "
     "both a Tokenomist schedule and a Binance USDT pair, from 2024-09-14 to 2026-08-15 (one row per token per calendar "
     "day; 101,393 rows after cleaning; median 701 days per token). A weekly panel (first day of each ISO week, 14,623 "
     "rows) is a robustness check, because daily rows of a 14-day target overlap heavily.")
doc.add_heading("3.2  Output Y and inputs X", 2)
para("The output is Y = log(RV_{14}), where RV_{14} is the annualized realized volatility of daily close-to-close log "
     "returns over days D+1 to D+14, \u221a(365/14 \u00b7 \u03a3 r^{2}). Logging makes the heavy-tailed target close to "
     "symmetric; all errors are in log-volatility space unless stated. The inputs fall into three groups (full list in "
     "Table A1):")
table(["Group", "#", "Features", "Role"], [
    ["CONTROLS", "9", "Trailing RV (7, 14, 30d), trailing return (7, 30d), BTC and ETH 14d RV, log market cap, days since launch",
     "Persistence, momentum, regime, size, age"],
    ["EMISSION", "13", "Share of float unlocking in next 7/30/90d, 30d share of total supply, days to and size of next cliff, "
     "has-cliff flag, 30d unlocks split by six recipient groups", "Forward-looking, published schedule"],
    ["STATIC", "10", "Allocation shares of six recipient groups, Tokenomist listing method (3 one-hots), unlock precision",
     "Token design, data quality"],
], [2.2, 0.8, 9.6, 4.4], "Table 1. Feature groups. FULL = all 32 features.", left_cols=(0, 2, 3))
doc.add_heading("3.3  Pre-processing and leakage control", 2)
para("Cleaning is a fixed, deterministic step with nothing learned from the data: rows without a target or without 30 days "
     "of price history are dropped; long-tailed emission ratios are log1p-transformed; the two structurally missing cliff "
     "columns are filled (days to next cliff = 365, size = 0) for the 51% of rows with no remaining cliff; categorical "
     "columns are encoded with fixed category lists. After cleaning no feature has missing values. The **ex-ante rule** "
     "holds throughout: a feature must be known at the close of D, targets are never inputs, and the only forward-looking "
     "inputs are the published schedule columns. One caveat remains: schedules are the version curated on the pull date "
     "(2026-09-14), so later revisions are reflected in the past (Section 6).")
doc.add_heading("3.4  Exploratory analysis", 2)
para("Unlock pressure is concentrated: in about half of all token-days less than 1% of the float unlocks in the next 30 "
     "days, while the top decile faces a median of 8.4%. Figure 1 shows that forward volatility does rise with unlock "
     "pressure: mean RV_{14} climbs from about 0.97 in the lowest decile to 1.14 in the highest. The pooled Spearman "
     "correlation is 0.14, the per-token median 0.22, and it is positive for 74% of tokens. The raw relationship is real; "
     "the question is whether it survives once trailing volatility, itself correlated with unlock pressure (young, "
     "high-emission tokens are volatile), is controlled for.")
figure("eda_decile_emission_vs_rv.png", 10, "Figure 1. Forward 14-day realized volatility by decile of 30-day unlock "
       "pressure (share of float unlocking), daily panel.")

# ---------------------------------------------------------------- 4 methods
doc.add_heading("4  Methodology", 1)
doc.add_heading("4.1  Training, validation and test (selection on training data only)", 2)
para("We follow the course roadmap: the test data are reserved before any model is selected, every candidate (a "
     "pre-processing pipeline plus a model plus its settings, e.g. k in KNN) is compared on data drawn from the training "
     "window only, and the selected procedure is refit on the full training window and evaluated **once** on the test "
     "data. Because rows of a panel time series are not exchangeable and a 14-day target makes neighbouring days share "
     "their future, shuffled k-fold cross-validation would leak; we use its time-ordered analogue. Five walk-forward folds "
     "are cut by calendar date with all tokens pooled, cutoffs every 90 days over the last 450 days (Table 2). For "
     "cutoff c, training uses dates \u2264 c \u2212 30 days (a 30-day embargo, longer than the target horizon; L\u00f3pez "
     "de Prado, 2018) and testing the 90 days after c. Inside each fold the last 90 days of training form the validation "
     "slice: candidates are fit on the earlier training rows (with a further 30-day purge), scored by validation RMSE, "
     "and the best is refit on all training rows. Scalers and transformers sit inside a scikit-learn Pipeline, so they are "
     "fit on the training slice of the current fold only; random_state = 42 throughout. Test results were never used to "
     "change a model, a grid or the feature sets.")
table(["Fold", "Cutoff", "Train rows", "Test rows", "Test window"],
      [[f, c, f"{a:,}", f"{b:,}", f"{c} + 90 days"] for f, c, a, b in FOLDS],
      [1.4, 2.8, 2.6, 2.6, 4.2], "Table 2. Walk-forward folds (daily panel). The training window expands.")
doc.add_heading("4.2  Baselines and metrics", 2)
para("Two simple baselines are scored on exactly the same test rows as every model. **Persistence** forecasts Y with "
     "log(RV over the past 14 days), the random-walk volatility forecast; the **training mean** forecasts the pooled mean "
     f"of Y in the training window. The headline metric is {R2} = 1 \u2212 SSE_{{model}} / SSE_{{persistence}} "
     "(Campbell and Thompson, 2008): zero ties persistence. We also report RMSE, MAE and Spearman rank correlation. "
     f"Because the training mean already beats persistence ({R2} \u2248 0.17), models are judged against both, and the "
     f"unlock question is judged by the **paired, per-fold difference** \u0394 = {R2}(FULL) \u2212 {R2}(CONTROLS).")
doc.add_heading("4.3  Models", 2)
para("A non-parametric regressor: the forecast is the (optionally distance-weighted) average target of the k most "
     "similar training token-days. A QuantileTransformer maps each feature to a normal scale so that no feature dominates "
     "the distance. Grid: k \u2208 {5, 10, 25, 50, 100, 250} \u00d7 {uniform, distance}. Validation chose k = 100 to 250 "
     "in every fold, a first sign that the target is noisy relative to the features. KNN is also run on CONTROLS+EMIS5 "
     "(controls plus the five headline unlock columns) to separate information from the curse of dimensionality.",
     lead="K-nearest neighbours (KNN). ")
para("400 bootstrapped regression trees with random feature subsets (Breiman, 2001), which can capture non-linear effects "
     "and interactions, e.g. an unlock effect that matters only in calm markets. Grid: max_depth \u2208 {None, 8, 12, 16} "
     "\u00d7 min_samples_leaf \u2208 {20, 50, 100} \u00d7 max_features \u2208 {sqrt, 0.33, 0.5}; daily runs evaluate a fixed "
     "seeded subset of 12 configurations for run time. Validation consistently chose large leaves (50 to 100 rows).",
     lead="Random Forest (RF). ")
para("Linear regression with an L2 penalty (Hoerl and Kennard, 1970), a strong benchmark for correlated predictors "
     "such as the three trailing-volatility windows. Volatility controls are logged inside the pipeline (a fixed "
     "transform) and all features standardized. Grid: \u03b1 \u2208 {0.1, \u2026, 10^{7}}. **Elastic Net** adds an L1 "
     "penalty (Zou and Hastie, 2005) that can set coefficients exactly to zero, so it performs feature selection: if "
     "unlock features carry signal, Elastic Net should keep them. Grid: \u03b1 \u2208 {10^{-4}, \u2026, 1} \u00d7 "
     "l1_ratio \u2208 {0.1, 0.5, 0.9}.", lead="Ridge and Elastic Net. ")
para("An L2-penalised classifier (C \u2208 {10^{-5}, \u2026, 10}, tuned by validation log loss) for two events defined "
     "from the forward target: **top20_xs**, the token is in the top 20% of forward volatility across all tokens on date D "
     "(base rate 20%), and **spike_1.5x**, forward volatility exceeds 1.5\u00d7 the token's own trailing 30-day volatility "
     "(base rate 14%). We report ROC-AUC, PR-AUC and the Brier skill score against the training base rate; no resampling "
     "is used, since it would distort the probabilities.", lead="Logistic regression. ")

# ---------------------------------------------------------------- 5 results
doc.add_heading("5  Results", 1)
doc.add_heading("5.1  Predictive performance against the baselines", 2)
rows = []
for k in REG:
    r = m[k]
    rows.append([NAMES[k], f3(r["CONTROLS"]["r2_oos"]), f3(r["FULL"]["r2_oos"]), sg(r["delta"]),
                 f"{r['wins']}/5", f4(r["CONTROLS"]["rmse"]), f4(r["FULL"]["rmse"]),
                 f3(r["CONTROLS"]["spearman"]), f3(r["FULL"]["spearman"])])
rows.append(["Train mean", f3(m["train_mean"]["r2_oos"]), "\u2013", "\u2013", "\u2013", f4(m["train_mean"]["rmse"]), "\u2013", "\u2013", "\u2013"])
rows.append(["Persistence", "0.000", "\u2013", "\u2013", "\u2013", f4(m["persistence"]["rmse"]), "\u2013", "\u2013", "\u2013"])
table(["Model", f"{R2} CTRL", f"{R2} FULL", "\u0394", "FULL wins", "RMSE CTRL", "RMSE FULL", "\u03c1 CTRL", "\u03c1 FULL"],
      rows, [2.8, 1.8, 1.8, 1.4, 1.5, 1.9, 1.9, 1.6, 1.6],
      f"Table 3. Test-set results, daily panel, Y = log RV_{{14}}, mean of 5 folds. \u0394 = FULL \u2212 CONTROLS in "
      f"{R2}; \u201cFULL wins\u201d = folds with \u0394 > 0; \u03c1 = Spearman.")
para("Table 3 and Figure 2 give the main result. **All four regressors beat both baselines** on the same test rows: "
     f"{R2} is {m['knn']['CONTROLS']['r2_oos']:.2f} to {m['ridge']['CONTROLS']['r2_oos']:.2f} on controls alone, against "
     f"{m['train_mean']['r2_oos']:.2f} for the training mean, and RMSE falls from {m['persistence']['rmse']:.3f} "
     f"(persistence) to about 0.443. Linear models are as good as non-linear ones: Ridge on controls "
     f"({m['ridge']['CONTROLS']['r2_oos']:.3f}) ties the Random Forest on all features ({m['rf']['FULL']['r2_oos']:.3f}). "
     "**Adding the 23 unlock and static features barely moves any model**: the mean \u0394 is +0.001 to +0.006, while "
     f"the fold-to-fold standard deviation of {R2} is {min(m[k]['CONTROLS']['r2_std'] for k in REG):.2f} to "
     f"{max(m[k]['CONTROLS']['r2_std'] for k in REG):.2f}, and FULL wins in only two or three of five folds. Table 4 "
     "shows why the small averages are not a signal: for the Random Forest the gain is +0.031 and +0.030 in the two oldest "
     "folds and negative in the three most recent ones (which are trained on the most data); KNN swings more; the linear "
     "models keep the unlock coefficients near zero, so their |\u0394| stays below 0.008.")
figure("compare_r2_oos.png", 15, f"Figure 2. {R2} against persistence, controls only (blue) vs FULL (orange); "
       "bars = \u00b11 s.d. across folds; dotted line = training-mean baseline.")
rows = [[NAMES[k]] + [sg(v) for v in m[k]["delta_folds"]] + [sg(m[k]["delta"])] for k in REG]
table(["Model", "Fold 1", "Fold 2", "Fold 3", "Fold 4", "Fold 5", "Mean"], rows, [3.0, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8],
      f"Table 4. Per-fold \u0394{R2} (FULL \u2212 CONTROLS), daily panel, folds in calendar order.")

doc.add_heading("5.2  Which mistakes remain?", 2)
dims = [("unlock_group", "<0.5%", "Unlock in 30d < 0.5% of float"), ("unlock_group", "0.5-2%", "Unlock 0.5\u20132%"),
        ("unlock_group", "2-5%", "Unlock 2\u20135%"), ("unlock_group", ">5%", "Unlock > 5%"),
        ("cliff_14d", "cliff in 14d", "Cliff unlock within 14 days"),
        ("age_group", "<1y", "Token younger than 1 year"), ("btc_regime", "stressed", "BTC volatility top tercile"),
        ("realized_q", "Q1", "Realized vol bottom quintile*"), ("realized_q", "Q5", "Realized vol top quintile*")]
rows = []
for d, g, lab in dims:
    rows.append([lab, f"{int(eg(d, g, 'n')):,}", f3(eg(d, g, "rmse|Persistence")), f3(eg(d, g, "rmse|Train mean")),
                 f3(eg(d, g, "rmse|Ridge CONTROLS")), f3(eg(d, g, "rmse|RF FULL")),
                 sg(eg(d, g, "delta_rmse|Ridge")), sg(eg(d, g, "delta_rmse|RF"))])
table(["Test rows", "n", "Persist.", "Train mean", "Ridge CTRL", "RF FULL", "\u0394 Ridge", "\u0394 RF"], rows,
      [5.0, 1.6, 1.6, 1.8, 1.8, 1.6, 1.6, 1.6],
      "Table 5. Test RMSE by subgroup, all folds pooled (73,414 rows). \u0394 = RMSE(FULL) \u2212 RMSE(CONTROLS): "
      "negative means the unlock features help. *Grouped by the outcome, to describe errors only.")
ri, rf_ = eg("unlock_group", ">5%", "delta_rmse|Ridge"), eg("unlock_group", ">5%", "delta_rmse|RF")
lv = ERR_LV
under = 1 - lv.loc["Ridge CONTROLS", "share_big_miss_underforecast"]
para("Pooling the five test windows lets us ask where the errors are (Table 5, Figures A1\u2013A2). **The unlock features "
     "do not help where they should**: in the rows where more than 5% of the float unlocks within 30 days, adding them "
     f"raises RMSE by {ri:+.3f} for Ridge and {rf_:+.3f} for the Random Forest, and they also hurt in the rows with a cliff "
     "unlock in the next 14 days; their small gains come from rows with almost no unlocks, i.e. noise. The errors that "
     "remain are **regression to the mean**: every model forecasts too high for tokens that turn calm and too low for "
     "tokens that spike (bottom and top realized quintiles), while being accurate in the middle. The models' clearest gain "
     f"over persistence is in large mistakes: the share of forecasts off by more than a factor of two falls from "
     f"{pct(lv.loc['Persistence', 'share_off_by_2x'])} (persistence) to {pct(lv.loc['Ridge CONTROLS', 'share_off_by_2x'])} "
     f"(Ridge). Of the remaining 2\u00d7 misses, {pct(under)} are over-forecasts of tokens whose volatility collapsed "
     f"(median realized {ERR_BM.loc['2x miss', 'median_rv_fwd_14d']:.2f} vs {ERR_BM.loc['other rows', 'median_rv_fwd_14d']:.2f} "
     "for other rows), and they are less common around cliffs and barely more common in young tokens than other rows; the rest are spikes that no feature "
     "anticipates.")

doc.add_heading("5.3  Interpretation: what each method uses", 2)
para("Validation chose strong penalties (\u03b1 = 10^{4} to 10^{7}); Elastic Net set **every** coefficient to zero "
     "in folds 1 and 3, falling back to the training mean. Elsewhere the largest standardized coefficients are trailing "
     "30-day volatility (+0.04 log-vol per s.d.), token age (\u22120.03) and ETH volatility (\u22120.03); the largest "
     "unlock coefficient, the 90-day unlock share, is +0.008: positive as the narrative predicts, but small (Figure A3).",
     lead="Coefficients (Ridge, Elastic Net). ")
para("Permutation importance on the last fold's test set (Figure A4) ranks trailing 30d, 14d and 7d volatility, the "
     "trailing 30-day return and token age as the five most important features. Summed by group, shuffling the controls "
     f"raises test RMSE by {RFG['controls']:.3f}, the 13 emission features by {RFG['emission']:.3f} and the 10 static "
     f"features by {RFG['static']:.3f}. Partial dependence on 30-day unlock pressure is nearly flat in every BTC regime "
     "(Figure A5). An illustrative depth-3 tree on all 32 features (Figure A6) splits only on trailing volatility, BTC and "
     "ETH volatility, token age and the trailing return: no unlock feature makes the top three levels.",
     lead="Trees (Random Forest). ")
para("For the most unlock-heavy test row (a token with 104% of its float unlocking within 30 days), the 250 nearest "
     "training rows have a median unlock share of only 12.5%: no comparable history exists, so the forecast (0.78) is "
     "driven by trailing volatility and overshoots the realized 0.55 (Figure A7). With 23 extra dimensions the "
     f"neighbourhoods are diluted, which is why KNN does best on CONTROLS+EMIS5 ({m['knn']['CONTROLS+EMIS5']['r2_oos']:.3f}) "
     f"rather than FULL ({m['knn']['FULL']['r2_oos']:.3f}).", lead="Neighbours (KNN). ")

doc.add_heading("5.4  Classification view (logistic regression)", 2)
L = LOGIT
rows = []
for lab, name in (("top20_xs", "Top 20% cross-section"), ("spike_1.5x", "Spike > 1.5\u00d7 own 30d vol")):
    c, f = L.loc[(lab, "daily", "CONTROLS")], L.loc[(lab, "daily", "FULL")]
    naive = f3(L.loc[(lab, "daily", "NONE")]["auc"]) if (lab, "daily", "NONE") in L.index else "\u2013"
    rows.append([name, naive, f3(c.auc), f3(f.auc), sg(f.auc - c.auc), f3(c.pr_auc), f3(f.pr_auc), f3(c.brier_skill), f3(f.brier_skill)])
table(["Event", "AUC naive", "AUC CTRL", "AUC FULL", "\u0394AUC", "PR-AUC CTRL", "PR-AUC FULL", "BSS CTRL", "BSS FULL"],
      rows, [3.6, 1.6, 1.6, 1.6, 1.4, 1.8, 1.8, 1.5, 1.5],
      "Table 6. Logistic regression, daily panel, mean of 5 folds. Naive = rank by trailing 14d volatility; "
      "BSS = Brier skill score vs the training base rate.")
para("On controls, logistic regression identifies high-volatility tokens clearly better than ranking by trailing "
     "volatility (AUC 0.694 vs 0.653). Its coefficients rank token age (younger tokens are more often in the top 20%) and "
     "trailing volatility first; the 90-day unlock share enters with an odds ratio of about 1.1 per s.d., yet adding the "
     "unlock features lowers ROC-AUC, PR-AUC and Brier skill for both events on both panels (Figure A8).")

doc.add_heading("5.5  Robustness", 2)
W = WEEKLY
para("On the **weekly panel**, which removes most overlap between rows, \u0394 is "
     f"{sg(W['rf']['delta'])} (RF), {sg(W['knn']['delta'])} (KNN), {sg(W['ridge']['delta'])} (Ridge) and "
     f"{sg(W['enet']['delta'])} (Elastic Net); the Ridge gain comes almost entirely from fold 1 (+0.082). For "
     "**alternative targets** (7-day, 30-day and Parkinson high-low 14-day volatility) the linear models' \u0394 stays "
     "between +0.001 and +0.011, while the RF FULL model reaches "
     f"{R2} of {TARGETS['log_rv_fwd_14d_parkinson']['rf']['FULL']['r2_oos']:.2f}, "
     f"{TARGETS['log_rv_fwd_7d']['rf']['FULL']['r2_oos']:.2f} and {TARGETS['log_rv_fwd_30d']['rf']['FULL']['r2_oos']:.2f}, "
     "so the pipeline and controls generalise. On the **hand-curated subsample** (where schedules should be cleanest) the "
     f"RF gap is the largest we observe, {sg(INTERNAL['rf']['delta'])}, still about a tenth of the fold spread "
     f"({sg(INTERNAL['ridge']['delta'])} for Ridge, {sg(INTERNAL['enet']['delta'])} for Elastic Net). Full numbers are in Table A2.")

doc.add_heading("5.6  Model comparison and practical relevance", 2)
para("For forecasting, **Ridge on the control features** is our recommended model: best or joint-best RMSE, the highest "
     "rank correlation, seconds to train and interpretable coefficients. The Random Forest is a close second and better on "
     "the 30-day and Parkinson targets; Elastic Net confirms the feature-selection reading; KNN is weakest and sensitive "
     "to the dimension of the feature space. For the research question the model does not matter: none extracts reliable "
     "incremental information from unlock schedules.", lead="Comparison. ")
para("In volatility units the typical error is large for every forecast: the median absolute error is about "
     f"{lv.loc['Ridge CONTROLS', 'median_abs_vol_error']:.2f} annualized-volatility points "
     f"({pct(lv.loc['Ridge CONTROLS', 'median_abs_pct_error'])} of the realized level), and only "
     f"{pct(lv.loc['Ridge CONTROLS', 'share_within_25pct'])} of forecasts are within 25% (persistence: "
     f"{pct(lv.loc['Persistence', 'share_within_25pct'])}). The useful improvement is fewer large misses, which matters "
     "for margin and position limits, where a forecast that is half the realized volatility is the costly case. Unlock "
     "features add nothing to that, while they cost a data subscription, a schedule-maintenance pipeline and revision risk; "
     "for a risk desk the decision is not to pay for them as a volatility input. Cases that still need human review are "
     "those the model systematically misses: tokens entering a spike (exchange listings or delistings, hacks, governance "
     "events), where the forecast is too low, and newly listed tokens with less than 30 days of history, which the model "
     "cannot score at all.", lead="Is the improvement useful for a decision? ")

# ---------------------------------------------------------------- 6 conclusion
doc.add_heading("6  Discussion and Conclusion", 1)
para("Once trailing volatility and the market regime are controlled for, scheduled token unlocks do not add reliable "
     "forecasting power for 14-day forward realized volatility in this panel. Five model families agree, the average gain "
     "is tiny relative to fold-to-fold variation, its sign is unstable, the unlock features hurt where unlocks are "
     "largest, and the classification view shows a small loss. Settings were chosen on validation data and the test "
     "results were reported without changing the models in response.", lead="Answer. ")
para("The models improve on the baselines because they combine persistence with mean reversion: persistence over-reacts "
     "to the last two weeks, the training mean ignores them, and a shrunk combination of trailing volatility at several "
     "horizons beats both. The unlock features fail to improve because their raw correlation with volatility (Figure 1) "
     "is not incremental: heavy-unlock tokens are young, small and already volatile, so the information is in their "
     "trailing volatility. Schedules are also public months ahead, so any predictable effect is plausibly traded before "
     "the event, consistent with semi-strong market efficiency (Fama, 1970).", lead="Explaining improvements and failures. ")
para("(i) One calm-to-moderate regime (2024-09 to 2026-08) with no 2022-style stress; unlocks may matter more when "
     "liquidity is thin. (ii) Schedules are the version curated on the pull date, so revisions are back-filled; this "
     "can only flatter the unlock features, which strengthens the null. (iii) Allocation data are a snapshot. (iv) Only "
     "176 Binance-listed tokens, which favours larger, more liquid names. (v) Daily RF runs used a subset of the grid.",
     lead="Limitations. ")
para("Event studies around large cliff unlocks with intraday data; interactions with liquidity, order-book depth and "
     "funding rates; point-in-time schedule snapshots; and gradient-boosted trees or HAR-style models with unlock terms.",
     lead="Future work. ")

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
    p = para(rf, size=SMALL, align=WD_ALIGN_PARAGRAPH.LEFT, after=1)
    p.paragraph_format.left_indent = Cm(0.6); p.paragraph_format.first_line_indent = Cm(-0.6)

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
    ["log rv_fwd_14d (Y)", "TARGET", "Primary target; robustness: log rv_fwd_7d, rv_fwd_30d, Parkinson 14d"],
]
table(["Column", "Group", "Definition"], A1, [5.6, 2.2, 9.2], "Table A1. Feature and target definitions (after cleaning).",
      left_cols=(0, 2))

rows = []
for lab, d in (("Daily, all tokens (main)", MAIN), ("Weekly panel", WEEKLY), ("INTERNAL subsample", INTERNAL)):
    for k in REG:
        if k in d and "delta" in d[k]:
            rows.append([lab, NAMES[k], f3(d[k]["CONTROLS"]["r2_oos"]), f3(d[k]["FULL"]["r2_oos"]), sg(d[k]["delta"]), f"{d[k]['wins']}/5"])
tn = {"log_rv_fwd_7d": "Target 7d RV", "log_rv_fwd_30d": "Target 30d RV", "log_rv_fwd_14d_parkinson": "Target Parkinson 14d"}
for tk, lab in tn.items():
    for k in REG:
        d = TARGETS[tk].get(k)
        if not d:
            continue
        if "delta" in d:
            rows.append([lab, NAMES[k], f3(d["CONTROLS"]["r2_oos"]), f3(d["FULL"]["r2_oos"]), sg(d["delta"]), f"{d['wins']}/5"])
        elif "FULL" in d:
            rows.append([lab, NAMES[k], "not run", f3(d["FULL"]["r2_oos"]), "\u2013", "\u2013"])
table(["Specification", "Model", f"{R2} CTRL", f"{R2} FULL", "\u0394", "FULL wins"], rows,
      [4.4, 3.0, 2.2, 2.2, 1.8, 1.8], f"Table A2. Robustness: mean {R2} over 5 folds.")

table(["Member", "Models", "Data & EDA", "Methods", "Results", "Report", "Slides"], [
    ["[[Member 1]]", "[[e.g. KNN, RF]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
    ["[[Member 2]]", "[[e.g. Ridge, Elastic Net]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
    ["[[Member 3]]", "[[e.g. Logistic]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]", "[[%]]"],
], [2.8, 3.6, 1.8, 1.8, 1.8, 1.8, 1.8], "Table A3. Contribution of each member (to be completed by the group).")

figure("errors_by_group.png", 17, "Figure A1. Test RMSE by ex-ante subgroup for the two baselines and three models, all folds pooled.")
figure("errors_calibration.png", 16, "Figure A2. Left: forecast deciles against realized volatility (the 45-degree line is perfect "
       "calibration). Right: mean error by quintile of realized volatility.")
figure("linear_coefs_full.png", 15, "Figure A3. Ridge and Elastic Net standardized coefficients (FULL, daily); bars = mean over folds, whiskers = min/max.")
figure("rf_permutation_importance_top15.png", 13, "Figure A4. Random Forest (FULL, last fold): permutation importance on the test set, top 15 features.")
figure("rf_pdp_emis30_x_btc.png", 11, "Figure A5. Random Forest partial dependence on 30-day unlock pressure across BTC volatility regimes.")
figure("tree_depth3_full.png", 17, "Figure A6. Illustrative depth-3 regression tree on all 32 features, fit on the last fold's training rows only.")
figure("knn_neighbour_illustration.png", 15, "Figure A7. KNN: the most unlock-heavy test row of the last fold and its nearest training rows.")
figure("logistic_auc.png", 15, "Figure A8. Logistic regression test ROC-AUC, controls vs FULL; dashed = rank by trailing 14d volatility.")
figure("knn_val_rmse_vs_k.png", 12, "Figure A9. KNN validation RMSE against k (mean over folds), by feature set.")
figure("eda_correlation_heatmap.png", 13, "Figure A10. Spearman correlations between target, controls and emission features.")
para("Code and data: the full pipeline is in MH6805_token_unlock_volatility.ipynb (repository "
     "github.com/watersalamander/MH6805A-Project-Group7), with per-fold results in results/ and figures in figures/.",
     size=SMALL, align=WD_ALIGN_PARAGRAPH.LEFT)

os.makedirs(ROOT + "/report", exist_ok=True)
doc.save(OUT)
print("saved", OUT)
