"""
Figure generation.

One shared visual theme across every chart so the output reads as a coherent
set rather than a collection of matplotlib defaults.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config

# ─────────────────────────────────────────────────────────────────────────────
# Theme
# ─────────────────────────────────────────────────────────────────────────────

BG_PAGE = "#f8f9fa"
BG_PANEL = "#ffffff"
INK = "#1a1a2e"
INK_SOFT = "#4a5568"
INK_FAINT = "#6b7280"
GRID = "#e5e7eb"

BLUE = "#1d6fa5"
ORANGE = "#e07b39"
RED = "#e63946"
GREEN = "#2a9d5c"
PURPLE = "#6b21a8"
SLATE = "#6b7280"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _canvas(figsize=(11, 6)):
    """A styled figure and axis with the shared theme applied."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(BG_PAGE)
    ax.set_facecolor(BG_PANEL)
    ax.spines[:].set_visible(False)
    ax.tick_params(colors=INK_FAINT, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(INK_FAINT)
    return fig, ax


def _title(ax, main: str, sub: str | None = None):
    ax.set_title(main, color=INK, fontsize=12, fontweight="600",
                 pad=22 if sub else 12)
    if sub:
        ax.text(0.5, 1.015, sub, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=9, color=INK_SOFT)


def _save(fig, name: str):
    out = Path(config.FIGURES_DIR)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Figures
# ─────────────────────────────────────────────────────────────────────────────

def plot_weather_compensation(t_design_C: float, name="01_weather_compensation"):
    """The compensation curve, with its three operating regions marked."""
    from .heatpump import flow_temperature

    fig, ax = _canvas((11, 5.5))

    x = np.linspace(-5, 20, 500)
    y = flow_temperature(x, t_design_C)

    saturated_cold = x <= t_design_C
    active = (x > t_design_C) & (x <= config.T_BALANCE_POINT_C)
    saturated_warm = x > config.T_BALANCE_POINT_C

    ax.axvspan(-5, t_design_C, alpha=0.10, color=PURPLE, zorder=0)
    ax.axvspan(t_design_C, config.T_BALANCE_POINT_C, alpha=0.06, color=BLUE, zorder=0)
    ax.axvspan(config.T_BALANCE_POINT_C, 20, alpha=0.06, color=GREEN, zorder=0)

    ax.plot(x[active], y[active], color=BLUE, lw=2.5, zorder=3,
            label="Flow temperature varies with outdoor temperature")
    ax.plot(x[saturated_cold], y[saturated_cold], color=PURPLE, lw=2.5,
            ls="--", zorder=3, label=f"Fixed at {config.T_FLOW_MAX_C:.0f} °C")
    ax.plot(x[saturated_warm], y[saturated_warm], color=GREEN, lw=2.5,
            ls="--", zorder=3, label=f"Fixed at {config.T_FLOW_MIN_C:.0f} °C — no heating")

    ax.scatter([t_design_C], [config.T_FLOW_MAX_C], color=PURPLE, s=70, zorder=6)
    ax.annotate(f"Design condition\n({t_design_C:.1f} °C → {config.T_FLOW_MAX_C:.0f} °C)",
                xy=(t_design_C, config.T_FLOW_MAX_C),
                xytext=(t_design_C + 2.5, config.T_FLOW_MAX_C - 11),
                fontsize=9, color=PURPLE,
                arrowprops=dict(arrowstyle="->", color=PURPLE, lw=1.2))

    ax.scatter([config.T_BALANCE_POINT_C], [config.T_FLOW_MIN_C],
               color=GREEN, s=70, zorder=6)
    ax.annotate(f"Balance point\n({config.T_BALANCE_POINT_C} °C → {config.T_FLOW_MIN_C:.0f} °C)",
                xy=(config.T_BALANCE_POINT_C, config.T_FLOW_MIN_C),
                xytext=(config.T_BALANCE_POINT_C - 7.5, config.T_FLOW_MIN_C + 5),
                fontsize=9, color=GREEN,
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2))

    ax.set_xlabel("Outdoor air temperature (°C)", color=INK_FAINT, fontsize=10)
    ax.set_ylabel("Flow temperature (°C)", color=INK_FAINT, fontsize=10)
    ax.set_xlim(-5, 20)
    ax.set_ylim(30, 60)
    ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=3, facecolor=BG_PANEL, edgecolor=GRID, labelcolor=INK_SOFT)

    _title(ax, "Weather-compensated flow temperature control",
           f"Range {config.T_FLOW_MIN_C:.0f}–{config.T_FLOW_MAX_C:.0f} °C  ·  "
           f"balance point {config.T_BALANCE_POINT_C} °C  ·  "
           f"design outdoor {t_design_C:.1f} °C")

    fig.tight_layout()
    return _save(fig, name)


def plot_seasonal_profile(df: pd.DataFrame, dwelling: str,
                          name="02_seasonal_profile"):
    """Monthly flow temperature and COP, showing cause above effect."""
    monthly_flow = df.groupby("month")["flow_temp_C"].mean()
    monthly_out = df.groupby("month")["outdoor_temp_C"].mean()
    monthly_cop = df.groupby("month")["cop_space"].mean()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.08},
    )
    fig.patch.set_facecolor(BG_PAGE)

    for ax in (ax1, ax2):
        ax.set_facecolor(BG_PANEL)
        ax.spines[:].set_visible(False)
        ax.tick_params(colors=INK_FAINT, labelsize=9, length=0)
        ax.yaxis.grid(True, color=GRID, linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)
        for lab in ax.get_yticklabels():
            lab.set_color(INK_FAINT)

    x = np.arange(1, 13)

    ax1.fill_between(x, monthly_out, monthly_flow, alpha=0.10,
                     color=RED, zorder=1, label="Temperature lift")
    ax1.plot(x, monthly_flow, color=RED, lw=2.5, marker="o", ms=6,
             zorder=4, label="Flow temperature")
    ax1.plot(x, monthly_out, color=BLUE, lw=2.0, marker="s", ms=5, ls="--",
             zorder=4, label="Outdoor temperature")

    for xi, yf in zip(x, monthly_flow):
        ax1.text(xi, yf + 1.2, f"{yf:.1f}°", ha="center", va="bottom",
                 fontsize=8, color=RED, fontweight="600")

    ax1.axhline(config.T_BALANCE_POINT_C, color=INK_FAINT, lw=0.8,
                ls=":", alpha=0.6)
    ax1.set_ylabel("Temperature (°C)", color=INK_FAINT, fontsize=10)
    ax1.set_ylim(-2, 58)
    ax1.legend(fontsize=8.5, loc="upper right", facecolor=BG_PANEL,
               edgecolor=GRID, labelcolor=INK_SOFT)

    ax2.fill_between(x, 0, monthly_cop, alpha=0.08, color=PURPLE, zorder=1)
    ax2.plot(x, monthly_cop, color=PURPLE, lw=2.5, marker="o", ms=6, zorder=4)

    for xi, yc in zip(x, monthly_cop):
        if not np.isnan(yc):
            ax2.text(xi, yc + 0.10, f"{yc:.2f}", ha="center", va="bottom",
                     fontsize=8, color=PURPLE, fontweight="600")

    rated = config.ASHP_SPECS[dwelling]["cop_a7w55"]
    ax2.axhline(rated, color=INK_FAINT, lw=0.9, ls=":", alpha=0.7)
    ax2.text(12.4, rated, f"Rated A7/W55\n{rated:.2f}", va="center",
             fontsize=7.5, color=INK_FAINT)

    mean_cop = float(np.nanmean(monthly_cop))
    ax2.axhline(mean_cop, color=PURPLE, lw=1.0, ls="--", alpha=0.6)
    ax2.text(12.4, mean_cop, f"Season mean\n{mean_cop:.2f}", va="center",
             fontsize=7.5, color=PURPLE)

    ax2.set_ylabel("COP (–)", color=INK_FAINT, fontsize=10)
    ax2.set_ylim(0, 5.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(MONTHS, color=INK_FAINT, fontsize=9)
    ax2.set_xlim(0.4, 13.2)

    fig.suptitle(
        f"Flow temperature drives seasonal COP — {dwelling}\n"
        f"{config.LOCATION_NAME} representative year "
        f"({config.WEATHER_START_YEAR}–{config.WEATHER_END_YEAR})",
        color=INK, fontsize=12, fontweight="600", y=0.98,
    )
    fig.subplots_adjust(top=0.90, bottom=0.07, left=0.07, right=0.93)
    return _save(fig, name)


def plot_running_costs(results: pd.DataFrame, name="03_running_costs"):
    """Side-by-side annual running cost, both systems."""
    fig, ax = _canvas((11, 6))

    dwellings = results["Dwelling type"].tolist()
    gas = results["Gas cost (GBP/yr)"].tolist()
    ashp = results["ASHP cost (GBP/yr)"].tolist()

    x = np.arange(len(dwellings))
    w = 0.38

    b1 = ax.bar(x - w / 2, gas, w, color=ORANGE, zorder=3,
                label=f"Gas boiler ({config.GAS_PRICE_P_PER_KWH:.2f} p/kWh, "
                      f"{int(config.BOILER_EFFICIENCY * 100)}% eff.)")
    b2 = ax.bar(x + w / 2, ashp, w, color=BLUE, zorder=3,
                label=f"ASHP ({config.OFGEM_ANNUAL_AVG_P:.2f} p/kWh avg)")

    for bar, val in zip(list(b1) + list(b2), gas + ashp):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 15,
                f"£{val:,.0f}", ha="center", va="bottom",
                fontsize=9, color=INK, fontweight="600")

    ax.set_xticks(x)
    ax.set_xticklabels(dwellings, color=INK, fontsize=10)
    ax.set_ylabel("Annual running cost (£)", color=INK_FAINT, fontsize=10)
    ax.set_ylim(0, max(ashp) * 1.20)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"£{int(v):,}"))
    ax.legend(fontsize=9, loc="upper left", facecolor=BG_PANEL,
              edgecolor=GRID, labelcolor=INK_SOFT)

    _title(ax, "The heat pump costs more to run in every dwelling type",
           "Ofgem standard variable tariff 2025, quarterly rates applied hourly")

    fig.tight_layout()
    return _save(fig, name)


def plot_npv(results: pd.DataFrame, name="04_npv"):
    """Fifteen-year NPV, all negative, deepening with dwelling size."""
    fig, ax = _canvas((11, 6))

    dwellings = results["Dwelling type"].tolist()
    npv = results[f"NPV {config.APPRAISAL_YEARS}yr (GBP)"].tolist()

    shades = ["#4895ef", "#3a78c9", "#2563a8", "#1e4d87"][: len(dwellings)]
    x = np.arange(len(dwellings))

    bars = ax.bar(x, npv, 0.55, color=shades, zorder=3)

    for bar, val in zip(bars, npv):
        ax.text(bar.get_x() + bar.get_width() / 2,
                val - abs(min(npv)) * 0.025,
                f"−£{abs(val):,.0f}", ha="center", va="top",
                fontsize=9.5, color=INK, fontweight="600")

    ax.axhline(0, color=INK_FAINT, lw=1.2, ls="--", zorder=4,
               label="Break-even (NPV = 0)")

    ax.set_xticks(x)
    ax.set_xticklabels(dwellings, color=INK, fontsize=10)
    ax.set_ylabel("Net present value (£)", color=INK_FAINT, fontsize=10)
    ax.set_ylim(min(npv) * 1.20, abs(min(npv)) * 0.08)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"−£{abs(v/1000):.0f}k" if v < 0 else "£0")
    )
    ax.legend(fontsize=9, loc="lower left", facecolor=BG_PANEL,
              edgecolor=GRID, labelcolor=INK_SOFT)

    _title(ax, f"No dwelling type reaches break-even over {config.APPRAISAL_YEARS} years",
           f"Net of £{config.BUS_GRANT_GBP:,} BUS grant  ·  "
           f"{config.DISCOUNT_RATE*100:.1f}% real discount rate")

    fig.tight_layout()
    return _save(fig, name)


def plot_breakeven(results: pd.DataFrame, name="05_breakeven_price"):
    """Break-even price against the actual quarterly range."""
    fig, ax = _canvas((11, 6.5))

    dwellings = results["Dwelling type"].tolist()
    breakeven = results["Break-even price (p/kWh)"].tolist()
    reduction = results["Required reduction (p/kWh)"].tolist()
    pct = results["Required reduction (%)"].tolist()

    q = list(config.OFGEM_QUARTERLY_P.values())
    x = np.arange(len(dwellings))

    ax.axhspan(min(q), max(q), color="#cbd5e1", alpha=0.35, zorder=1)
    ax.text(len(dwellings) - 0.35, (min(q) + max(q)) / 2,
            f"Ofgem 2025\nquarterly range\n{min(q):.2f}–{max(q):.2f}p",
            fontsize=8, color=INK_SOFT, va="center", ha="left", linespacing=1.4)

    ax.bar(x, breakeven, 0.46, color=BLUE, zorder=3,
           label="Break-even electricity price")
    ax.bar(x, reduction, 0.46, bottom=breakeven, color=RED, alpha=0.85,
           zorder=3, label="Reduction still required")

    for xi, be, rd, pc in zip(x, breakeven, reduction, pct):
        ax.text(xi, be / 2, f"{be:.2f}p", ha="center", va="center",
                fontsize=10, color="white", fontweight="600")
        ax.text(xi, be + rd / 2, f"−{rd:.2f}p", ha="center", va="center",
                fontsize=9, color="white", fontweight="600")
        ax.text(xi, be + rd + 0.35, f"−{pc:.1f}%", ha="center", va="bottom",
                fontsize=9, color=RED, fontweight="600")

    ax.axhline(config.OFGEM_ANNUAL_AVG_P, color=ORANGE, lw=2.0, zorder=5,
               label=f"Ofgem 2025 average ({config.OFGEM_ANNUAL_AVG_P:.2f} p/kWh)")

    ax.set_xticks(x)
    ax.set_xticklabels(dwellings, color=INK, fontsize=10)
    ax.set_ylabel("Electricity price (p/kWh)", color=INK_FAINT, fontsize=10)
    ax.set_ylim(0, config.OFGEM_ANNUAL_AVG_P * 1.24)
    ax.set_xlim(-0.6, len(dwellings) - 0.05)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}p"))
    ax.legend(fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.09),
              ncol=3, facecolor=BG_PANEL, edgecolor=GRID, labelcolor=INK_SOFT)

    _title(ax, "Every Ofgem 2025 quarterly rate sits above break-even",
           f"Gas {config.GAS_PRICE_P_PER_KWH:.2f} p/kWh at "
           f"{int(config.BOILER_EFFICIENCY*100)}% efficiency  ·  "
           f"heat cost {config.GAS_PRICE_P_PER_KWH/config.BOILER_EFFICIENCY:.2f} p/kWh")

    fig.tight_layout()
    return _save(fig, name)


def plot_tornado(tornado_df: pd.DataFrame, name="06_tornado"):
    """One bar per driver, widest on top, shared x-axis across dwellings."""
    dwellings = tornado_df["Dwelling type"].unique()
    colours = {"Electricity price": BLUE, "Gas price": ORANGE,
               "Installed cost": SLATE}

    all_vals = pd.concat([
        tornado_df["NPV at +swing (GBP)"], tornado_df["NPV at -swing (GBP)"]
    ])
    pad = abs(all_vals.min()) * 0.10
    xlim = (all_vals.min() - pad, all_vals.max() + pad)

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True, sharey=True)
    fig.patch.set_facecolor(BG_PAGE)

    for ax, dwelling in zip(axes.flatten(), dwellings):
        sub = tornado_df[tornado_df["Dwelling type"] == dwelling]
        sub = sub.sort_values("Swing width (GBP)")

        ax.set_facecolor(BG_PANEL)
        ax.spines[:].set_visible(False)
        ax.tick_params(colors=INK_FAINT, labelsize=9, length=0)
        ax.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)

        base = sub["Base NPV (GBP)"].iloc[0]

        for i, (_, r) in enumerate(sub.iterrows()):
            lo = min(r["NPV at +swing (GBP)"], r["NPV at -swing (GBP)"])
            hi = max(r["NPV at +swing (GBP)"], r["NPV at -swing (GBP)"])

            ax.barh(i, hi - lo, left=lo, height=0.5,
                    color=colours[r["Variable"]], alpha=0.85, zorder=3)
            ax.plot([base, base], [i - 0.25, i + 0.25],
                    color="white", lw=2.5, zorder=5)

        ax.axvline(base, color="#374151", lw=1.2, ls="--", zorder=4)
        ax.text(base, len(sub) - 0.42, f" base £{base:,.0f}",
                fontsize=8, color="#374151", va="top", fontweight="600")

        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels(sub["Variable"], fontsize=10, color=INK)
        ax.set_ylim(-0.6, len(sub) - 0.3)
        ax.set_xlim(*xlim)
        ax.set_title(dwelling, color=INK, fontsize=11, fontweight="600", pad=10)
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"−£{abs(v/1000):.0f}k" if v < 0 else "£0")
        )
        for lab in ax.get_xticklabels():
            lab.set_color(INK_FAINT)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.85)
               for c in colours.values()]
    fig.legend(handles, [f"{k}  (±{int(config.SENSITIVITY_SWING*100)}%)"
                         for k in colours],
               fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.04),
               ncol=3, facecolor=BG_PANEL, edgecolor=GRID, labelcolor=INK_SOFT)

    fig.suptitle(
        "Electricity price dominates every dwelling type\n"
        f"±{int(config.SENSITIVITY_SWING*100)}% swing on 15-year NPV  ·  "
        "shared axis  ·  white tick marks the base case",
        color=INK, fontsize=12, fontweight="600", y=1.0,
    )
    fig.tight_layout()
    return _save(fig, name)


def plot_grant_gap(grants: pd.DataFrame, name="07_grant_gap"):
    """Required grant against the current scheme."""
    fig, ax = _canvas((11, 6.5))

    dwellings = grants["Dwelling type"].tolist()
    required = grants["Required grant (GBP)"].tolist()
    current = config.BUS_GRANT_GBP

    x = np.arange(len(dwellings))
    w = 0.38

    b1 = ax.bar(x - w / 2, required, w, color=BLUE, zorder=3,
                label=f"Required for {config.APPRAISAL_YEARS}-year payback")
    ax.bar(x + w / 2, [current] * len(dwellings), w, color=ORANGE, zorder=3,
           label=f"Current BUS grant (£{current:,})")

    for bar, val in zip(b1, required):
        ax.text(bar.get_x() + bar.get_width() / 2, val / 2, f"£{val:,.0f}",
                ha="center", va="center", fontsize=9, color="white",
                fontweight="600")
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(required) * 0.02,
                f"+£{val - current:,.0f}", ha="center", va="bottom",
                fontsize=8.5, color=RED, fontweight="600")

    ax.axhline(current, color=ORANGE, lw=1.5, ls="--", alpha=0.7, zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels(dwellings, color=INK, fontsize=10)
    ax.set_ylabel("Grant (£)", color=INK_FAINT, fontsize=10)
    ax.set_ylim(0, max(required) * 1.22)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"£{int(v):,}"))
    ax.legend(fontsize=9, loc="upper left", facecolor=BG_PANEL,
              edgecolor=GRID, labelcolor=INK_SOFT)

    _title(ax, "The current grant falls short for every dwelling type",
           "Shortfall grows with dwelling size — a flat grant helps larger homes least")

    fig.tight_layout()
    return _save(fig, name)


def generate_all(weather, t_design, cop_profile, results, tornado_df, grants,
                 representative="Semi-Detached"):
    """Produce the full figure set. Returns the paths written."""
    return [
        plot_weather_compensation(t_design),
        plot_seasonal_profile(cop_profile, representative),
        plot_running_costs(results),
        plot_npv(results),
        plot_breakeven(results),
        plot_tornado(tornado_df),
        plot_grant_gap(grants),
    ]
