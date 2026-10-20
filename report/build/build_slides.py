"""Build the draft presentation (PowerPoint) from results/ and figures/."""
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from stats import ERR_BM, ERR_G, ERR_LV, LGBG, INTERNAL, LOGIT, MAIN, NAMES, REG, RFG, TARGETS, WEEKLY

ROOT = "D:/ML-project"
FIG = ROOT + "/figures/"
OUT = ROOT + "/report/Group7_Presentation_DRAFT.pptx"

NAVY = RGBColor(0x14, 0x1B, 0x2D)
INK = RGBColor(0x1F, 0x24, 0x33)
MUTED = RGBColor(0x6B, 0x72, 0x80)
CTRL = RGBColor(0x2B, 0x7B, 0xD6)     # controls only (matches the repo figures)
FULL = RGBColor(0xEB, 0x6A, 0x35)     # controls + emission + static
TINT = RGBColor(0xF2, 0xF4, 0xF7)
LINE = RGBColor(0xD9, 0xDD, 0xE3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ICE = RGBColor(0xC9, 0xD3, 0xE6)
PH = RGBColor(0xC0, 0x39, 0x2B)
HEAD, BODY = "Cambria", "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W = 13.333


def bg(slide, color):
    f = slide.background.fill; f.solid(); f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None, spacing=None):
    """runs: str, or list of paragraphs; each paragraph is a str or list of (text, opts) tuples."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, pr in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing: p.space_after = Pt(spacing)
        for t, o in ([(pr, {})] if isinstance(pr, str) else pr):
            r = p.add_run(); r.text = t
            r.font.name = o.get("font", font); r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold); r.font.italic = o.get("italic", False)
            r.font.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill=TINT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name: s.name = name
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line: s.line.color.rgb = line; s.line.width = Pt(1)
    else: s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE: s.adjustments[0] = radius
    return s


def badge(slide, x, y, label, fill=NAVY, color=WHITE, d=0.5, size=16):
    c = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame; tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = color; r.font.name = BODY
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


def content(title, kicker, notes, speaker):
    s = prs.slides.add_slide(BLANK); bg(s, WHITE)
    text(s, 0.6, 0.35, 12.1, 0.3, kicker.upper(), size=12, color=FULL, bold=True, name="Kicker")
    text(s, 0.6, 0.65, 12.1, 0.9, title, size=32, color=INK, font=HEAD, bold=True, name="Title")
    text(s, 0.6, 7.0, 8, 0.3, "MH6805 Group 7  |  Token unlocks and forward volatility", size=10, color=MUTED, name="Footer")
    text(s, 11.2, 7.0, 1.53, 0.3, str(len(prs.slides)), size=10, color=MUTED, align=PP_ALIGN.RIGHT, name="Slide number")
    s.notes_slide.notes_text_frame.text = f"Speaker: {speaker}\n\n{notes}"
    return s


def style_chart(ch, legend=True, size=12):
    ch.font.size = Pt(size); ch.font.name = BODY; ch.font.color.rgb = INK
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(size)
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = LINE
    va.format.line.fill.background()
    va.tick_labels.font.color.rgb = MUTED; va.tick_labels.font.size = Pt(size - 1)
    ca = ch.category_axis
    ca.format.line.color.rgb = LINE
    ca.tick_labels.font.size = Pt(size)


M = MAIN
SPK = ["[Member 1]", "[Member 2]", "[Member 3]"]

# 1 ------------------------------------------------------------- title
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 1.2, 11, 0.4, "MH6805 MACHINE LEARNING IN FINANCE  |  GROUP 7", size=14, color=FULL, bold=True)
text(s, 0.8, 1.9, 11.5, 2.2, "Do scheduled token unlocks help forecast crypto volatility?", size=46, color=WHITE, font=HEAD, bold=True)
text(s, 0.8, 4.25, 11, 0.6, "Walk-forward evidence from 176 tokens and six machine-learning models", size=20, color=ICE)
text(s, 0.8, 5.7, 11, 0.4, [[("[Member 1]   [Member 2]   [Member 3]", {"color": RGBColor(0xFF, 0x9F, 0x80), "bold": True})]], size=16)
text(s, 0.8, 6.15, 11, 0.4, "[Presentation date]", size=14, color=ICE)
s.notes_slide.notes_text_frame.text = ("Speaker: [Member 1]\n\nIntroduce the group and the question in one sentence: crypto tokens publish "
    "their unlock calendars in advance; we test whether that calendar helps forecast how volatile a token will be "
    "over the next two weeks, beyond what its recent volatility already tells us.")

# 2 ------------------------------------------------------------- motivation
s = content("Unlocks are widely watched as volatility events", "Motivation",
            "Explain vesting: most of a token's supply is locked at launch and released on a published schedule. "
            "The market narrative is that unlocks bring new sellers and so more volatility. Because the schedule is "
            "public in advance it is a legitimate forward-looking input, which is rare in forecasting. But volatility "
            "is very persistent, so any new feature has a high bar to clear.", SPK[0])
steps = [("1", "Supply is locked", "Team, investor and ecosystem allocations vest over months or years"),
         ("2", "Schedule is public", "Unlock dates and sizes are published in advance (Tokenomist tracks 176 of our tokens)"),
         ("3", "Narrative: more sellers", "New supply reaches holders who may sell, so traders expect price swings"),
         ("4", "But volatility persists", "Recent volatility is already a strong forecast, so the bar for a new feature is high")]
for i, (n, h, d) in enumerate(steps):
    x = 0.6 + i * 3.08
    box(s, x, 2.0, 2.85, 3.9, fill=TINT, name=f"Step card {n}")
    badge(s, x + 0.3, 2.3, n, fill=FULL if i == 3 else NAVY, d=0.6, size=18)
    text(s, x + 0.3, 3.15, 2.3, 0.8, h, size=19, bold=True, font=HEAD)
    text(s, x + 0.3, 4.0, 2.3, 1.8, d, size=15, color=MUTED)
text(s, 0.6, 6.25, 12.1, 0.5, [[("Our question: ", {"bold": True}), ("does the unlock calendar add forecasting power for 14-day forward volatility ", {}),
     ("beyond", {"bold": True, "color": FULL}), (" volatility persistence and the market regime?", {})]], size=18)

# 3 ------------------------------------------------------------- design
s = content("Do unlocks add anything beyond persistence?", "Question and design",
            "Motivation: most token supply is locked at launch and released on a published schedule, and traders treat "
            "big unlocks as volatility events. The schedule is public in advance, so it is a legitimate forward-looking "
            "input, but volatility is very persistent, so the bar is high. Design: every model is trained twice with the same rows, folds and tuning grid: once on the nine controls and "
            "once with the 23 unlock and static features added. The difference in out-of-sample R squared is the "
            "finding. We decided up front that a null result is a valid result and we did not tune to change it.", SPK[0])
box(s, 0.6, 2.0, 3.9, 3.7, fill=RGBColor(0xE6, 0xF0, 0xFB), name="Controls card")
text(s, 0.9, 2.25, 3.4, 0.5, "CONTROLS  (9)", size=20, bold=True, color=CTRL, font=HEAD)
text(s, 0.9, 2.85, 3.4, 2.8, ["Trailing volatility 7, 14, 30d", "Trailing return 7, 30d", "BTC and ETH volatility (regime)",
                               "Log market cap, token age"], size=15, spacing=8)
box(s, 4.75, 2.0, 3.9, 3.7, fill=RGBColor(0xFD, 0xEC, 0xE4), name="Full card")
text(s, 5.05, 2.25, 3.4, 0.5, "+ UNLOCK & STATIC (23)", size=20, bold=True, color=FULL, font=HEAD)
text(s, 5.05, 2.85, 3.4, 2.8, ["Share of float unlocking in next 7, 30, 90 days", "Days to and size of next cliff",
                               "30d unlocks by recipient (team, investors, community ...)", "Allocation shares, data-quality flags"], size=15, spacing=8)
arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(8.85), Inches(3.5), Inches(0.7), Inches(0.6))
arrow.fill.solid(); arrow.fill.fore_color.rgb = NAVY; arrow.line.fill.background()
box(s, 9.75, 2.0, 3.0, 3.7, fill=NAVY, name="Delta card")
text(s, 9.75, 2.4, 3.0, 1.0, "\u0394 R\u00b2", size=48, bold=True, color=WHITE, font=HEAD, align=PP_ALIGN.CENTER)
text(s, 10.0, 3.6, 2.5, 1.8, "FULL minus CONTROLS, per fold, same model, same data", size=15, color=ICE, align=PP_ALIGN.CENTER)
text(s, 0.6, 6.05, 12.1, 0.6, "Why ask: traders treat big unlocks as volatility events, and the schedule is public in advance. Y = log forward 14-day realized volatility; metric = out-of-sample R² vs the persistence forecast.", size=15, color=MUTED)

# 4 ------------------------------------------------------------- data
s = content("A daily panel of 176 tokens over two years", "Dataset",
            "Two real sources: Binance daily candles for prices and Tokenomist for unlock schedules and allocations. "
            "One row per token per day from September 2024 to August 2026. Every feature is known at the close of the "
            "day; the only forward-looking inputs are the published schedule columns. One caveat: schedules are the "
            "version curated on our pull date, so later revisions are back-filled.", SPK[0])
stats = [("176", "tokens", "with a Tokenomist schedule and a Binance USDT pair"),
         ("101,393", "token-days", "2024-09-14 to 2026-08-15, median 701 days per token"),
         ("32", "features", "9 controls, 13 emission, 10 static; no missing values after cleaning"),
         ("5", "walk-forward folds", "90-day test windows after a 30-day embargo; rows never shuffled")]
for i, (big, lab, d) in enumerate(stats):
    x = 0.6 + i * 3.08
    text(s, x, 2.1, 2.9, 1.1, big, size=44, bold=True, color=FULL if i == 0 else NAVY, font=HEAD)
    text(s, x, 3.25, 2.9, 0.4, lab, size=18, bold=True)
    text(s, x, 3.75, 2.75, 1.4, d, size=15, color=MUTED)
box(s, 0.6, 5.35, 12.1, 1.35, fill=TINT, name="Sources")
text(s, 0.9, 5.55, 11.5, 1.0, [[("Prices: ", {"bold": True}), ("Binance spot daily klines (open, high, low, close).  ", {}),
     ("Unlocks: ", {"bold": True}), ("Tokenomist API daily emission, unlock events and allocations, pulled 2026-09-14.", {})],
     [("Weekly panel (14,623 rows) used as a robustness check because daily 14-day targets overlap.", {"color": MUTED})]], size=15, spacing=6)

# 5 ------------------------------------------------------------- EDA
s = content("In the raw data, volatility does rise with unlocks", "Data and first look",
            "Data first: 176 tokens, one row per token per day from September 2024 to August 2026, prices from Binance "
            "and unlock schedules from Tokenomist; every feature is known at the close of the day. Then the hook: "
            "unconditionally, there is a relationship. Forward volatility climbs from about 0.97 in the "
            "lowest unlock decile to 1.14 in the highest, and the correlation is positive for three quarters of tokens. "
            "But heavy-unlock tokens are young, small and already volatile, so the question is whether this survives "
            "once trailing volatility is in the model.", SPK[0])
s.shapes.add_picture(FIG + "eda_decile_emission_vs_rv.png", Inches(0.6), Inches(2.45), height=Inches(4.3))
box(s, 0.6, 1.7, 12.1, 0.55, fill=TINT, name="Data strip")
text(s, 0.85, 1.7, 11.7, 0.55, [[("176 tokens", {"bold": True}), ("  ·  101,393 token-days, 2024-09-14 to 2026-08-15  ·  ", {}),
     ("prices: ", {"bold": True}), ("Binance daily klines  ·  ", {}), ("unlocks: ", {"bold": True}),
     ("Tokenomist schedules  ·  32 features", {})]], size=14, anchor=MSO_ANCHOR.MIDDLE)
for i, (big, d) in enumerate([("0.14", "pooled Spearman \u03c1 between 30-day unlock pressure and forward volatility"),
                              ("74%", "of tokens show a positive correlation (per-token median \u03c1 = 0.22)")]):
    text(s, 8.7, 2.5 + i * 1.5, 4.0, 0.8, big, size=40, bold=True, color=NAVY, font=HEAD)
    text(s, 8.7, 3.25 + i * 1.5, 4.0, 0.8, d, size=14, color=MUTED)
box(s, 8.7, 5.55, 4.0, 1.2, fill=RGBColor(0xFD, 0xEC, 0xE4), name="But")
text(s, 8.95, 5.65, 3.5, 1.0, [[("But: ", {"bold": True, "color": FULL}), ("heavy-unlock tokens are young and already volatile. Is this just persistence in disguise?", {})]], size=15)

# 6 ------------------------------------------------------------- protocol
s = content("Walk-forward validation: never shuffle, never peek", "Protocol",
            "Five folds cut by calendar date, all tokens pooled. Training expands; a 30-day embargo separates train from "
            "test because the target looks 14 days ahead. Inside each fold the last 90 days of training are the "
            "validation slice used for tuning; the winner is refit on all training data and scored once on the next "
            "90 days. Scalers live inside the sklearn pipeline, so nothing is fit on test data. Hand over: with the protocol fixed, [Member 2] shows what six models do under it.", SPK[0])
import datetime as dt
t0, t1 = dt.date(2024, 9, 14), dt.date(2026, 8, 15)
X0, XW = 2.0, 10.6
px = lambda d: X0 + XW * (d - t0).days / (t1 - t0).days
cuts = [dt.date(2025, 5, 22), dt.date(2025, 8, 20), dt.date(2025, 11, 18), dt.date(2026, 2, 16), dt.date(2026, 5, 17)]
for i, c in enumerate(cuts):
    y = 2.0 + i * 0.62
    text(s, 0.6, y + 0.02, 1.3, 0.4, f"Fold {i + 1}", size=14, bold=True)
    tr_end, va_start = c - dt.timedelta(days=30), c - dt.timedelta(days=120)
    box(s, px(t0), y, px(va_start) - px(t0), 0.4, fill=CTRL, shape=MSO_SHAPE.RECTANGLE, name=f"Train {i+1}")
    box(s, px(va_start), y, px(tr_end) - px(va_start), 0.4, fill=RGBColor(0x8F, 0xB8, 0xE8), shape=MSO_SHAPE.RECTANGLE, name=f"Val {i+1}")
    box(s, px(c), y, px(min(c + dt.timedelta(days=90), t1)) - px(c), 0.4, fill=FULL, shape=MSO_SHAPE.RECTANGLE, name=f"Test {i+1}")
for d, lab in ((t0, "2024-09"), (dt.date(2025, 6, 1), "2025-06"), (dt.date(2026, 1, 1), "2026-01"), (t1, "2026-08")):
    text(s, px(d) - 0.5, 5.12, 1.0, 0.3, lab, size=12, color=MUTED, align=PP_ALIGN.CENTER)
leg = [(CTRL, "Train"), (RGBColor(0x8F, 0xB8, 0xE8), "Validation (last 90d of train, for tuning)"), (WHITE, "30-day embargo"), (FULL, "Test (90 days, scored once)")]
x = 2.0
for col, lab in leg:
    box(s, x, 5.65, 0.3, 0.3, fill=col, line=LINE if col == WHITE else None, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.4, 5.66, 3.5, 0.3, lab, size=13)
    x += 0.55 + len(lab) * 0.085
text(s, 0.6, 6.25, 12.1, 0.5, "Candidates (pre-processing + model + settings) are compared on validation only; the winner is refit and the test window is scored once, never used to change a model.",
     size=14, color=MUTED)

# 7 ------------------------------------------------------------- models
s = content("Six models, one shared harness", "Methods",
            "Each model sees identical rows, folds and features. KNN tests a local, similarity-based view; Random Forest "
            "can find non-linear effects and interactions, for example unlocks mattering only in calm markets, and "
            "LightGBM boosts small trees on the residuals; Ridge "
            "and Elastic Net are strong linear benchmarks, and Elastic Net can drop features entirely; logistic "
            "regression re-asks the question as classifying high-volatility events. Note what tuning chose: very large "
            "neighbourhoods, large leaves and strong penalties, all signs of a noisy target.", SPK[1])
cards = [("KNN", "Quantile-scaled distance; k from 5 to 250", "Tuned: k = 100\u2013250", "Regression"),
         ("Random Forest", "400 trees, depth \u00d7 leaf \u00d7 features grid", "Tuned: leaves of 50\u2013100 rows", "Regression"),
         ("LightGBM", "Boosted trees; 200 or 500 trees, 7 or 15 leaves", "Tuned: slowest, lr 0.02", "Regression"),
         ("Ridge", "L2 penalty; \u03b1 from 0.1 to 10\u2077", "Tuned: \u03b1 = 10\u2074\u201310\u2077", "Regression"),
         ("Elastic Net", "L1 + L2, \u03b1 \u00d7 l1_ratio grid", "Tuned: all-zero in 2 of 5 folds", "Regression"),
         ("Logistic", "L2; C from 10\u207b\u2075 to 10, log-loss tuning", "Events: top-20% vol, 1.5\u00d7 spike", "Classification")]
for i, (h, d, t, kind) in enumerate(cards):
    x = 0.6 + i * 2.05
    box(s, x, 1.95, 1.88, 4.6, fill=NAVY if i == 5 else TINT, name=f"Model card {h}")
    fg = WHITE if i == 5 else INK
    text(s, x + 0.19, 2.2, 1.5, 0.3, kind.upper(), size=11, bold=True, color=FULL)
    text(s, x + 0.19, 2.55, 1.5, 0.9, h, size=20, bold=True, color=fg, font=HEAD)
    text(s, x + 0.19, 3.5, 1.5, 1.4, d, size=14, color=ICE if i == 5 else MUTED)
    text(s, x + 0.19, 5.0, 1.5, 1.3, t, size=14, bold=True, color=fg)

# 8 ------------------------------------------------------------- headline chart
s = content("All models beat the benchmarks on controls alone", "Result 1",
            "Read the chart pair by pair: blue is controls only, orange adds the unlock and static features. Every model "
            "clears the training-mean benchmark of 0.17 and the persistence benchmark of zero. But within each pair the "
            "bars are almost identical. Ridge on controls alone is as good as anything we built.", SPK[1])
cd = CategoryChartData()
cd.categories = [NAMES[k] for k in REG]
cd.add_series("Controls only", [round(M[k]["CONTROLS"]["r2_oos"], 3) for k in REG])
cd.add_series("Controls + emission + static", [round(M[k]["FULL"]["r2_oos"], 3) for k in REG])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75), Inches(8.3), Inches(5.0), cd)
ch = gf.chart; style_chart(ch)
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0, 0.3
ch.value_axis.tick_labels.number_format = "0.00"; ch.value_axis.tick_labels.number_format_is_linked = False
pl = ch.plots[0]; pl.gap_width = 60; pl.overlap = -5
for ser, col in zip(pl.series, (CTRL, FULL)):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = col
pl.has_data_labels = True
dl = pl.data_labels; dl.number_format = "0.000"; dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END; dl.font.size = Pt(12)
text(s, 9.3, 1.9, 3.4, 0.4, "Out-of-sample R\u00b2 vs persistence", size=14, bold=True)
text(s, 9.3, 2.25, 3.4, 0.4, "daily panel, 5 test folds, same test rows for every forecast", size=13, color=MUTED)
for i, (big, d) in enumerate([(f"{M['train_mean']['r2_oos']:.2f}", "training-mean benchmark: every model is above it"),
                              ("+0.001 to +0.006", "gain from adding 23 unlock and static features")]):
    text(s, 9.3, 3.0 + i * 1.75, 3.5, 0.7, big, size=36 if i == 0 else 30, bold=True, color=NAVY if i == 0 else FULL, font=HEAD)
    text(s, 9.3, 3.75 + i * 1.75, 3.4, 0.8, d, size=15, color=MUTED)

# 9 ------------------------------------------------------------- per fold delta
s = content("The small gain is noise: it flips sign across folds", "Result 2",
            "This is the per-fold paired difference. For the Random Forest the unlock block helps in the two oldest folds "
            "and hurts in the three most recent, which are trained on the most data. KNN swings even more. Linear models "
            "barely move because they shrink the unlock coefficients to almost zero. Meanwhile R squared itself varies "
            "by about 0.15 from fold to fold, so a difference of 0.006 is far inside the noise.", SPK[1])
cd = CategoryChartData()
cd.categories = [f"Fold {i}" for i in range(1, 6)]
cols = {"knn": RGBColor(0x9A, 0xA3, 0xB2), "rf": FULL, "lightgbm": RGBColor(0x1B, 0xAF, 0x7A), "ridge": NAVY, "enet": CTRL}
for k in REG:
    cd.add_series(NAMES[k], [round(v, 3) for v in M[k]["delta_folds"]])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75), Inches(8.3), Inches(5.0), cd)
ch = gf.chart; style_chart(ch)
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = -0.08, 0.12
ch.value_axis.tick_labels.number_format = "+0.00;-0.00;0"; ch.value_axis.tick_labels.number_format_is_linked = False
from pptx.enum.chart import XL_TICK_LABEL_POSITION
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
pl = ch.plots[0]; pl.gap_width = 70
for ser, k in zip(pl.series, REG):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = cols[k]; ser.invert_if_negative = False
text(s, 9.3, 1.9, 3.4, 0.4, "\u0394 R\u00b2oos = FULL \u2212 CONTROLS", size=14, bold=True)
text(s, 9.3, 2.25, 3.4, 0.4, "per test fold, in calendar order", size=13, color=MUTED)
for i, (big, d, col) in enumerate([("1–2 of 5", "folds where FULL beats CONTROLS for the tree models and KNN; 3 of 5 for the linear ones", FULL),
                                   ("\u00b10.15", "fold-to-fold s.d. of R\u00b2oos itself, 25\u00d7 the largest mean gain", NAVY)]):
    text(s, 9.3, 3.0 + i * 1.75, 3.5, 0.7, big, size=36, bold=True, color=col, font=HEAD)
    text(s, 9.3, 3.75 + i * 1.75, 3.4, 0.9, d, size=15, color=MUTED)

# 10 ------------------------------------------------------------- inside models
s = content("Inside the models, unlock features barely register", "Interpretation",
            "We explain each model with the tool that suits it. Random Forest permutation importance: shuffling all "
            "controls costs three times more test RMSE than shuffling all 13 emission features, and partial dependence "
            "on unlock pressure is flat. Coefficients: the largest unlock coefficient is positive, as the narrative "
            "says, but five times smaller than trailing volatility, and Elastic Net drops everything in two folds. A "
            "shallow tree never splits on an unlock feature. Neighbours: for the most unlock-heavy token-day there is "
            "no comparable history, so KNN falls back on trailing volatility. Hand over: on average the answer is no; "
            "[Member 3] shows where the remaining errors are and whether any of this matters in practice.", SPK[1])
cd = CategoryChartData()
cd.categories = ["Controls (9)", "Emission (13)", "Static (10)"]
cd.add_series("RMSE increase", [round(RFG["controls"], 3), round(RFG["emission"], 3), round(RFG["static"], 3)])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(2.25), Inches(6.0), Inches(3.6), cd)
ch = gf.chart; style_chart(ch, legend=False); ch.has_title = False
ch.value_axis.minimum_scale = 0; ch.value_axis.maximum_scale = 0.036
ch.value_axis.tick_labels.number_format = "0.000"; ch.value_axis.tick_labels.number_format_is_linked = False
ch.category_axis.reverse_order = True
from pptx.enum.chart import XL_TICK_LABEL_POSITION as TLP
pl = ch.plots[0]; pl.gap_width = 55; pl.vary_by_categories = False
pl.series[0].format.fill.solid(); pl.series[0].format.fill.fore_color.rgb = NAVY
for idx, col in ((1, FULL), (2, RGBColor(0x9A, 0xA3, 0xB2))):
    pt = pl.series[0].points[idx]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = col
pl.has_data_labels = True; pl.data_labels.number_format = "0.000"; pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END; pl.data_labels.font.size = Pt(12)
text(s, 0.6, 1.8, 6.0, 0.4, "Random Forest: test-RMSE increase when a feature group is shuffled", size=14, bold=True)
text(s, 0.6, 5.95, 6.0, 0.7, f"Top 5 RF features are all controls; partial dependence on unlock pressure is flat. LightGBM: controls take {100 * LGBG['controls']:.0f}% of split gain, emission {100 * LGBG['emission']:.0f}%.",
     size=13, color=MUTED)
for i, (kind, h, d) in enumerate([
        ("COEFFICIENTS", "Ridge / Elastic Net", "Largest unlock coefficient +0.008 vs +0.040 for trailing 30d vol; EN drops every feature in 2 of 5 folds"),
        ("A TREE", "Depth-3 tree, all 32 features", "Splits only on trailing vol, BTC/ETH vol, token age and 30d return"),
        ("NEIGHBOURS", "KNN, most unlock-heavy row", "104% of float unlocking; neighbours' median 12.5%. Forecast 0.78, realized 0.55")]):
    y = 1.85 + i * 1.62
    box(s, 7.1, y, 5.6, 1.42, fill=TINT, name=f"Interpretation card {i}")
    text(s, 7.35, y + 0.18, 5.1, 0.3, kind, size=11, bold=True, color=FULL)
    text(s, 7.35, y + 0.45, 5.1, 0.4, h, size=15, bold=True)
    text(s, 7.35, y + 0.82, 5.1, 0.6, d, size=13, color=MUTED)

# 11 ------------------------------------------------------------- logistic
s = content("Classification view: unlock features slightly hurt", "Result 3",
            "Same question as classification. The model on controls does pick out high-volatility tokens better than just "
            "ranking by recent volatility, AUC 0.69 against 0.65. Adding unlock features lowers AUC, PR-AUC and the "
            "Brier skill score for both events, on both panels. Hand over: on average the answer is no; [Member 3] shows where the "
            "remaining errors are and whether any of this matters in practice.", SPK[1])
L = LOGIT
rows = [("Event", "Base rate", "Naive AUC", "AUC controls", "AUC + unlocks", "\u0394 AUC")]
for lab, name, br in (("top20_xs", "Top 20% most volatile tokens on the date", "20%"), ("spike_1.5x", "Vol jumps above 1.5\u00d7 own 30d level", "14%")):
    c, f = L.loc[(lab, "daily", "CONTROLS")], L.loc[(lab, "daily", "FULL")]
    nv = f"{L.loc[(lab, 'daily', 'NONE')]['auc']:.3f}" if (lab, "daily", "NONE") in L.index else "\u2013"
    rows.append((name, br, nv, f"{c.auc:.3f}", f"{f.auc:.3f}", f"{f.auc - c.auc:+.3f}"))
widths = [4.6, 1.4, 1.5, 1.6, 1.6, 1.4]
tbl = s.shapes.add_table(len(rows), len(widths), Inches(0.6), Inches(2.0), Inches(sum(widths)), Inches(2.1)).table
for j, wd in enumerate(widths): tbl.columns[j].width = Inches(wd)
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        cell = tbl.cell(i, j); cell.text = ""
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY if i == 0 else (TINT if i % 2 == 0 else WHITE)
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
        r = p.add_run(); r.text = v; r.font.size = Pt(15); r.font.name = BODY
        r.font.bold = i == 0 or j == 5; r.font.color.rgb = WHITE if i == 0 else (FULL if j == 5 else INK)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
s.shapes.add_picture(FIG + "logistic_auc.png", Inches(0.6), Inches(4.35), height=Inches(2.45))
box(s, 7.3, 4.45, 5.4, 1.75, fill=TINT, name="Logistic takeaway")
text(s, 7.6, 4.65, 4.9, 1.9, [[("Daily panel, mean of 5 folds. ", {"bold": True}),
     ("PR-AUC and Brier skill fall too, on both panels. Unlock schedules do not help pick the most volatile tokens, nor anticipate a token's own volatility jump.", {})]], size=15)

# 9b ------------------------------------------------------------- which mistakes remain
def eg(dim, group, col):
    r = ERR_G[(ERR_G.dimension == dim) & (ERR_G.group == group)]
    return float(r[col].iloc[0])


s = content("Unlock features do not help even where unlocks are big", "Which mistakes remain?",
            "We pool all test rows and ask where the errors are. If unlock features carried signal, FULL should beat "
            "CONTROLS where more than 5% of the float unlocks, or where a cliff is two weeks away. The opposite happens: "
            "positive bars mean adding unlock features made the forecast worse. What remains is regression to the mean: "
            "too high for tokens that turn calm, too low for tokens that spike. The models' real gain over persistence "
            "is fewer large misses.", SPK[2])
groups = [("unlock_group", "<0.5%", "Unlock <0.5%"), ("unlock_group", "0.5-2%", "Unlock 0.5–2%"),
          ("unlock_group", "2-5%", "Unlock 2–5%"), ("unlock_group", ">5%", "Unlock >5%"), ("cliff_14d", "cliff in 14d", "Cliff ≤14d")]
cd = CategoryChartData()
cd.categories = [g[2] for g in groups]
cd.add_series("Ridge", [round(eg(d, g, "delta_rmse|Ridge"), 4) for d, g, _ in groups])
cd.add_series("Random Forest", [round(eg(d, g, "delta_rmse|RF"), 4) for d, g, _ in groups])
cd.add_series("LightGBM", [round(eg(d, g, "delta_rmse|LGBM"), 4) for d, g, _ in groups])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(2.2), Inches(8.3), Inches(4.55), cd)
ch = gf.chart; style_chart(ch)
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = -0.008, 0.016
ch.value_axis.major_unit = 0.004
ch.value_axis.tick_labels.number_format = "+0.000;-0.000;0"; ch.value_axis.tick_labels.number_format_is_linked = False
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
pl = ch.plots[0]; pl.gap_width = 70
for ser, col in zip(pl.series, (NAVY, FULL, RGBColor(0x1B, 0xAF, 0x7A))):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = col; ser.invert_if_negative = False
pl.has_data_labels = False
text(s, 0.6, 1.8, 8.3, 0.4, "Change in test RMSE from adding unlock features (positive = worse), by 30-day unlock share of float",
     size=14, bold=True)
lvs = ERR_LV
for i, (big, d, col) in enumerate([
        (f"{100 * lvs.loc['Persistence', 'share_off_by_2x']:.0f}% → {100 * lvs.loc['Ridge CONTROLS', 'share_off_by_2x']:.0f}%",
         "forecasts off by more than 2×: persistence vs Ridge. The real gain is fewer large misses", NAVY),
        (f"{100 * (1 - lvs.loc['Ridge CONTROLS', 'share_big_miss_underforecast']):.0f}%",
         "of remaining 2× misses are over-forecasts: volatility collapsed. The rest are spikes no feature sees", FULL)]):
    text(s, 9.3, 1.9 + i * 2.35, 3.5, 0.7, big, size=32, bold=True, color=col, font=HEAD)
    text(s, 9.3, 2.65 + i * 2.35, 3.4, 1.2, d, size=15, color=MUTED)

# 12 ------------------------------------------------------------- robustness
s = content("The null result survives every robustness check", "Robustness and classification",
            "We re-ran the comparison on the weekly panel, on three alternative volatility targets and on the tokens "
            "Tokenomist curates by hand, where schedules should be most accurate. The largest gain anywhere is +0.017, "
            "for the Random Forest on the curated subsample, still about a tenth of the fold-to-fold spread. Ridge on "
            "the Parkinson target is the only case that wins all five folds, by 0.011. LightGBM shows the same picture, "
            "and on the small weekly panel it falls just below the training mean. Classification tells the same story: "
            "logistic regression on controls beats ranking by recent volatility (AUC 0.69 vs 0.65), and adding unlock "
            "features lowers AUC for both high-volatility events.", SPK[2])
rows = [("Specification", "KNN", "Random Forest", "LightGBM", "Ridge", "Elastic Net")]
fmt = lambda d, k: f"{d[k]['delta']:+.3f}" if k in d and "delta" in d[k] else "\u2013"
rows.append(("Daily panel (main)",) + tuple(fmt(M, k) for k in REG))
rows.append(("Weekly panel",) + tuple(fmt(WEEKLY, k) for k in REG))
rows.append(("Hand-curated tokens only",) + tuple(fmt(INTERNAL, k) for k in REG))
for t, lab in (("log_rv_fwd_7d", "Target: 7-day vol"), ("log_rv_fwd_30d", "Target: 30-day vol"), ("log_rv_fwd_14d_parkinson", "Target: Parkinson 14-day")):
    rows.append((lab,) + tuple(fmt(TARGETS[t], k) for k in REG))
widths = [3.2, 1.2, 1.7, 1.4, 1.2, 1.5]
tbl = s.shapes.add_table(len(rows), 6, Inches(0.6), Inches(1.9), Inches(sum(widths)), Inches(4.5)).table
for j, wd in enumerate(widths): tbl.columns[j].width = Inches(wd)
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        cell = tbl.cell(i, j); cell.text = ""
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY if i == 0 else (TINT if i % 2 == 0 else WHITE)
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
        r = p.add_run(); r.text = v.replace("-0.000", "0.000"); r.font.size = Pt(14); r.font.name = BODY
        r.font.bold = i == 0; r.font.color.rgb = WHITE if i == 0 else INK
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
text(s, 0.6, 6.5, 10.5, 0.4, "Cells: mean \u0394 R\u00b2oos (FULL \u2212 CONTROLS) over 5 folds.  \u2013 = controls-only run not done for that specification.", size=12, color=MUTED)
text(s, 11.1, 2.0, 1.9, 0.9, "+0.017", size=30, bold=True, color=FULL, font=HEAD)
text(s, 11.1, 2.75, 1.8, 1.4, "largest gain anywhere (RF curated; LightGBM 30d vol)", size=14, color=MUTED)
dauc = [LOGIT.loc[(e, "daily", "FULL")].auc - LOGIT.loc[(e, "daily", "CONTROLS")].auc for e in ("top20_xs", "spike_1.5x")]
text(s, 11.1, 4.2, 1.9, 0.9, f"{dauc[0]:+.3f}", size=30, bold=True, color=NAVY, font=HEAD)
text(s, 11.1, 4.95, 1.8, 1.5, f"logistic AUC change from unlocks: top-20% event (spike: {dauc[1]:+.3f})", size=14, color=MUTED)

# 12b ------------------------------------------------------------- practical relevance
s = content("Is any improvement useful for the decision?", "Practical relevance",
            "Translate the errors into volatility points. The typical error is large for every forecast, and on the "
            "median the model is no better than persistence. What it does buy is fewer forecasts that are off by a factor "
            "of two, which is what matters for margin and position limits. Unlock features add nothing to that and cost "
            "a data subscription and a maintenance pipeline, so our recommendation to a risk desk is not to pay for them "
            "as a volatility input, and to keep a human in the loop for the cases on the right.", SPK[2])
stats_ = [(f"{lvs.loc['Ridge CONTROLS', 'median_abs_vol_error']:.2f}", "median absolute error, annualized-vol points "
           f"({100 * lvs.loc['Ridge CONTROLS', 'median_abs_pct_error']:.0f}% of the level)"),
          (f"{100 * lvs.loc['Ridge CONTROLS', 'share_within_25pct']:.0f}%", f"of forecasts within 25% of realized "
           f"(persistence {100 * lvs.loc['Persistence', 'share_within_25pct']:.0f}%)"),
          ("None", "useful gain from unlock features, at the cost of a data subscription and upkeep")]
for i, (big, d) in enumerate(stats_):
    y = 1.9 + i * 1.6
    text(s, 0.6, y, 2.6, 0.9, big, size=40, bold=True, color=FULL if i == 2 else NAVY, font=HEAD)
    text(s, 3.3, y + 0.15, 3.6, 1.2, d, size=15, color=MUTED)
box(s, 7.3, 1.9, 5.4, 4.8, fill=TINT, name="Human review")
text(s, 7.6, 2.1, 4.9, 0.5, "Still needs human review", size=20, bold=True, font=HEAD)
for i, it in enumerate(["Tokens entering a spike (listings, delistings, hacks): the forecast is too low",
                        "Tokens whose volatility is collapsing: most remaining 2× misses are over-forecasts",
                        "New listings with under 30 days of history: the model cannot score them",
                        "Regime shifts not seen in 2024–26 training data"]):
    badge(s, 7.6, 2.8 + i * 0.95, str(i + 1), fill=NAVY, d=0.42, size=13)
    text(s, 8.2, 2.8 + i * 0.95, 4.3, 0.9, it, size=15)

# 13 ------------------------------------------------------------- conclusion (dark)
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.6, 0.35, 12, 0.3, "CONCLUSION", size=12, color=FULL, bold=True)
text(s, 0.6, 0.65, 12.1, 0.9, "Unlocks are not a reliable incremental volatility signal", size=32, color=WHITE, font=HEAD, bold=True)
pts = [("1", "Raw link is real, not incremental", "Heavy-unlock tokens are young and already volatile; trailing volatility absorbs the effect."),
       ("2", "Six models agree", "Regressors gain only +0.001 to +0.006 R\u00b2, with unstable sign; logistic AUC falls slightly."),
       ("3", "Best forecaster: Ridge on controls", "Best RMSE and rank correlation, seconds to train, interpretable. RF close second."),
       ("4", "Consistent with an efficient market", "Schedules are public months ahead, so any predictable effect is likely priced before the date.")]
for i, (n, h, d) in enumerate(pts):
    x, y = 0.6 + (i % 2) * 6.2, 2.0 + (i // 2) * 2.25
    badge(s, x, y, n, fill=FULL, d=0.6, size=18)
    text(s, x + 0.85, y - 0.02, 5.0, 0.5, h, size=20, bold=True, color=WHITE, font=HEAD)
    text(s, x + 0.85, y + 0.55, 5.0, 1.3, d, size=16, color=ICE)
text(s, 0.6, 6.55, 12, 0.4, "Limits: one 2024–26 regime; schedules as curated in Sept 2026, so revisions are back-filled.   Thank you. Questions?", size=16, color=ICE)
s.notes_slide.notes_text_frame.text = ("Speaker: [Member 3]\n\nState the answer plainly: once you know a token's recent "
    "volatility and the market regime, its unlock calendar does not help forecast the next two weeks. Give the "
    "interpretation: the unconditional correlation comes from young, volatile tokens having big unlocks. Practical "
    "takeaway: do not bump a volatility forecast just because an unlock is coming. Limitations in one breath: one "
    "calm-to-moderate regime, and back-filled schedule revisions, which can only flatter the unlock features. Then "
    "invite questions; each member takes questions on their own block.")

# 14 ------------------------------------------------------------- limits & next
s = content("Limitations and next steps", "Discussion",
            "Be upfront: one regime, and schedule revisions are back-filled, which if anything flatters the unlock "
            "features and so makes our null stronger. The natural next study is an event study around the largest cliff "
            "unlocks with intraday data, where an effect, if any, would be concentrated.", SPK[2])
for col, (head, colr, items) in enumerate([
        ("Limitations", NAVY, ["One calm-to-moderate regime (2024-09 to 2026-08), no 2022-style stress",
                               "Schedules as curated on 2026-09-14: revisions are back-filled (biases toward finding an effect)",
                               "Allocation and listing data are snapshots",
                               "176 Binance-listed tokens: larger, more liquid names"]),
        ("Next steps", FULL, ["Event study around the largest cliff unlocks",
                              "Intraday data for the hours around each unlock",
                              "Interact unlocks with liquidity, depth and funding rates",
                              "Point-in-time schedule snapshots; boosted trees and HAR models"])]):
    x = 0.6 + col * 6.2
    box(s, x, 1.9, 5.9, 4.8, fill=TINT, name=head)
    text(s, x + 0.35, 2.15, 5.2, 0.5, head, size=22, bold=True, color=colr, font=HEAD)
    for i, it in enumerate(items):
        badge(s, x + 0.35, 2.95 + i * 0.92, str(i + 1), fill=colr, d=0.42, size=13)
        text(s, x + 0.95, 2.95 + i * 0.92, 4.7, 0.85, it, size=16, anchor=MSO_ANCHOR.TOP)

# 15 ------------------------------------------------------------- Q&A
s = prs.slides.add_slide(BLANK); bg(s, NAVY)
text(s, 0.8, 2.0, 11.5, 1.2, "Thank you. Questions?", size=48, color=WHITE, font=HEAD, bold=True)
text(s, 0.8, 3.4, 11.5, 0.6, "Code, per-fold results and figures: github.com/watersalamander/MH6805A-Project-Group7", size=18, color=ICE)
text(s, 0.8, 4.6, 11.5, 0.4, "CONTRIBUTIONS", size=12, color=FULL, bold=True)
text(s, 0.8, 5.0, 11.5, 1.4, [[("[Member 1]: [part / %]     [Member 2]: [part / %]     [Member 3]: [part / %]", {"color": RGBColor(0xFF, 0x9F, 0x80), "bold": True})]], size=16)
s.notes_slide.notes_text_frame.text = "All members: take questions. Each member should be ready to answer on the model they built."

import os
if os.environ.get("FULL_DECK") != "1":
    DROP = ("Unlocks are widely watched as volatility events", "A daily panel of 176 tokens over two years",
            "Classification view: unlock features slightly hurt", "Limitations and next steps", "Thank you. Questions?")
    ids = prs.slides._sldIdLst
    for sl, sid in reversed(list(zip(prs.slides, list(ids)))):
        if any(sh.has_text_frame and sh.text_frame.text in DROP for sh in sl.shapes):
            prs.part.drop_rel(sid.rId); ids.remove(sid)
    for n, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            if sh.name == "Slide number":
                sh.text_frame.paragraphs[0].runs[0].text = str(n)

    # speaker notes = the spoken script, so slides and script never drift apart
    import re
    script = open(ROOT + "/report/PRESENTATION_SCRIPT.md", encoding="utf-8").read()
    lines = re.findall(r"## Slide (\d+) \((Member \d), ~(\d+) s\)\nTitle: [^\n]*\n\n(.*?)(?=\n## |\n---)", script, re.S)
    assert len(lines) == len(prs.slides), f"script has {len(lines)} slides, deck has {len(prs.slides)}"
    for (n, who, sec, body), sl in zip(lines, prs.slides):
        paras = []
        for para in re.sub(r"\*([^*]+)\*", r"\1", body.strip()).split("\n\n"):
            out = []
            for ln in para.split("\n"):
                if ln.startswith("- "):                      # bullet
                    out.append("• " + ln[2:])
                elif ln.startswith("  ") and out:            # bullet continuation
                    out[-1] += " " + ln.strip()
                elif out and not out[-1].startswith("•"):  # wrapped prose line
                    out[-1] += " " + ln
                else:
                    out.append(ln)
            paras.append("\n".join(out))
        spoken = "\n\n".join(paras)
        sl.notes_slide.notes_text_frame.text = f"Speaker: [{who}]  (~{sec} s)\n\n{spoken}"
prs.save(OUT)
print("saved", OUT, len(prs.slides))
