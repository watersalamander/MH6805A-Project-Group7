"""Slide version of Figure A4: Random Forest permutation importance, top 10 features.

Run from the repo root:  python report/build/fig_rf_importance_slide.py
Reads results/rf_permutation_importance.csv (written by scripts/03_rf.py) and writes
figures/rf_permutation_importance_top10_slide.png. One panel, plain-English labels,
white background so it sits on the slide without a visible box.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common as C  # noqa: E402

TOP = 10
COLORS = {"controls": "#2a78d6", "emission": "#eb6834", "static": "#f3a37f"}
GROUP_NAMES = {"controls": "Controls", "emission": "Unlock schedule", "static": "Token design (static)"}
LABELS = {
    "rv_past_30d": "Trailing volatility, 30d",
    "rv_past_14d": "Trailing volatility, 14d",
    "rv_past_7d": "Trailing volatility, 7d",
    "ret_past_30d": "Trailing return, 30d",
    "ret_past_7d": "Trailing return, 7d",
    "days_since_tge": "Token age",
    "log_mcap_pit": "Market cap (log)",
    "emis_next_90d_pct_float": "Unlocks next 90d, % of float",
    "emis_next_30d_pct_float": "Unlocks next 30d, % of float",
    "emis_next_30d_pct_total": "Unlocks next 30d, % of supply",
    "next_cliff_pct_float": "Next cliff size, % of float",
    "days_to_next_cliff": "Days to next cliff",
    "alloc_share_founderTeam": "Team allocation share",
    "alloc_share_community": "Community allocation share",
    "alloc_share_reserve": "Reserve allocation share",
}


def main():
    C.set_style()
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white"})

    p = pd.read_csv(C.RESULTS_DIR / "rf_permutation_importance.csv")
    p = p[p.model_variant == "FULL"].sort_values("perm_importance_mean", ascending=False)
    p = p.reset_index(drop=True)
    p["rank"] = p.index + 1
    top = p.head(TOP).iloc[::-1]

    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    y = range(len(top))
    ax.barh(list(y), top.perm_importance_mean, xerr=top.perm_importance_std, height=0.7,
            color=[COLORS[g] for g in top.group], error_kw={"ecolor": C.INK_2, "lw": 1})
    ax.set_yticks(list(y))
    ax.set_yticklabels([LABELS.get(f, f) for f in top.feature], fontsize=14)
    for yi, v, s in zip(y, top.perm_importance_mean, top.perm_importance_std):
        ax.text(v + s + 0.00012, yi, f"{v:.4f}", va="center", fontsize=12, color=C.INK_2)
    ax.set_xlabel("increase in test RMSE when the feature is shuffled (log-vol)", fontsize=13)
    ax.tick_params(axis="x", labelsize=12)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, top.perm_importance_mean.max() * 1.18)

    # call out the best unlock feature against the best control
    best_ctrl = p.iloc[0]
    best_emis = p[p.group == "emission"].iloc[0]
    yb = list(top.feature).index(best_emis.feature)
    ratio = best_emis.perm_importance_mean / best_ctrl.perm_importance_mean
    ax.annotate(f"Best unlock feature ranks #{best_emis['rank']}:\n"
                f"about 1/{round(1 / ratio)} of trailing 30d volatility",
                xy=(best_emis.perm_importance_mean + 0.0016, yb),
                xytext=(0.0056, yb + 0.15), fontsize=13, color=COLORS["emission"],
                fontweight="bold", va="center",
                arrowprops={"arrowstyle": "->", "color": COLORS["emission"], "lw": 1.5})

    groups = [g for g in COLORS if g in set(top.group)]
    ax.legend(handles=[Patch(color=COLORS[g], label=GROUP_NAMES[g]) for g in groups],
              loc="lower right", fontsize=13)
    C.savefig(fig, "rf_permutation_importance_top10_slide.png")


if __name__ == "__main__":
    main()
