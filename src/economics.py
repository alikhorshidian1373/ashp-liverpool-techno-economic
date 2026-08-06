"""
Financial appraisal.

Running costs, net present value, simple payback, and break-even electricity
price. Electricity is costed at the Ofgem quarterly rate applying to each hour
rather than an annual average, so the seasonal concentration of heat pump demand
interacts properly with the tariff structure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ─────────────────────────────────────────────────────────────────────────────
# Running costs
# ─────────────────────────────────────────────────────────────────────────────

def hourly_electricity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Electricity consumed each hour, kWh.

    Space heating COP is NaN outside the heating season; the fill leaves those
    hours contributing nothing rather than propagating NaN through the sum.
    """
    out = df.copy()

    out["E_space_kWh"] = (out["Q_space_kWh"] / out["cop_space"]).fillna(0.0)
    out["E_dhw_kWh"] = out["Q_dhw_kWh"] / out["cop_dhw"]
    out["E_total_kWh"] = out["E_space_kWh"] + out["E_dhw_kWh"]

    return out


def ashp_annual_cost(df: pd.DataFrame, quarterly: bool = True) -> float:
    """
    Annual ASHP running cost, GBP.

    With ``quarterly=True`` each hour is priced at its own quarter's unit rate.
    The alternative applies the annual average throughout, which is what most
    published studies do — the difference is small here but worth being able to
    quantify rather than assume.
    """
    if quarterly:
        rates_p = df["quarter"].map(config.OFGEM_QUARTERLY_P).to_numpy()
    else:
        rates_p = np.full(len(df), config.OFGEM_ANNUAL_AVG_P)

    return float((df["E_total_kWh"].to_numpy() * rates_p / 100).sum())


def gas_annual_cost(dwelling_demand_kWh: float) -> float:
    """
    Annual gas boiler running cost, GBP.

    Gas input exceeds delivered heat by the inverse of seasonal efficiency.
    """
    gas_input = dwelling_demand_kWh / config.BOILER_EFFICIENCY
    return gas_input * config.GAS_PRICE_GBP_PER_KWH


# ─────────────────────────────────────────────────────────────────────────────
# Seasonal performance
# ─────────────────────────────────────────────────────────────────────────────

def seasonal_cop(df: pd.DataFrame) -> dict[str, float]:
    """
    Seasonal COP — delivered heat divided by consumed electricity.

    Space heating is summed over heating hours only; hot water and total over
    the full year.
    """
    heating = df["cop_space"].notna()

    return {
        "scop_space": float(
            df.loc[heating, "Q_space_kWh"].sum()
            / df.loc[heating, "E_space_kWh"].sum()
        ),
        "scop_dhw": float(df["Q_dhw_kWh"].sum() / df["E_dhw_kWh"].sum()),
        "scop_total": float(df["Q_total_kWh"].sum() / df["E_total_kWh"].sum()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Appraisal
# ─────────────────────────────────────────────────────────────────────────────

def annuity_factor(rate: float, years: int) -> float:
    """Present value of one unit received annually for ``years`` years."""
    return (1 - (1 + rate) ** -years) / rate


def net_present_value(
    net_capital_gbp: float,
    annual_saving_gbp: float,
    years: int = config.APPRAISAL_YEARS,
    rate: float = config.DISCOUNT_RATE,
) -> float:
    """
    NPV of the switch.

    Where the annual saving is negative — as it is throughout this study — a
    longer horizon makes the NPV worse rather than better, since the operational
    cash flow itself is a cost.
    """
    return -net_capital_gbp + annual_saving_gbp * annuity_factor(rate, years)


def simple_payback(net_capital_gbp: float, annual_saving_gbp: float) -> float:
    """
    Years to recover capital from operational savings.

    Undefined when the saving is negative: cumulative savings never reach the
    capital cost because they move further from it each year.
    """
    if annual_saving_gbp <= 0:
        return float("nan")
    return net_capital_gbp / annual_saving_gbp


def breakeven_electricity_price_p(scop_total: float) -> float:
    """
    Electricity price at which ASHP and gas boiler heat cost the same, p/kWh.

    Setting cost per kWh of delivered heat equal for both systems:
        P_elec / SCOP = P_gas / eta_boiler
    """
    gas_heat_cost_p = config.GAS_PRICE_P_PER_KWH / config.BOILER_EFFICIENCY
    return gas_heat_cost_p * scop_total


def heat_cost_comparison(scop_total: float) -> dict[str, float]:
    """Cost per kWh of delivered heat, both systems, p/kWh."""
    gas = config.GAS_PRICE_P_PER_KWH / config.BOILER_EFFICIENCY
    ashp = config.OFGEM_ANNUAL_AVG_P / scop_total

    return {
        "gas_p_per_kWh_heat": gas,
        "ashp_p_per_kWh_heat": ashp,
        "gap_p_per_kWh": ashp - gas,
        "ashp_premium_pct": 100 * (ashp - gas) / gas,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Per-dwelling assembly
# ─────────────────────────────────────────────────────────────────────────────

def appraise(df: pd.DataFrame, dwelling: str) -> dict:
    """Full appraisal for one dwelling type."""
    spec = config.ASHP_SPECS[dwelling]
    total_demand = config.ANNUAL_HEAT_DEMAND_KWH[dwelling]

    cop = seasonal_cop(df)
    ashp_cost = ashp_annual_cost(df, quarterly=True)
    gas_cost = gas_annual_cost(total_demand)
    saving = gas_cost - ashp_cost

    net_capital = spec["installed_cost_gbp"] - config.BUS_GRANT_GBP
    breakeven = breakeven_electricity_price_p(cop["scop_total"])

    result = {
        "Dwelling type": dwelling,
        "SCOP space": round(cop["scop_space"], 2),
        "SCOP DHW": round(cop["scop_dhw"], 2),
        "SCOP total": round(cop["scop_total"], 2),
        "ASHP cost (GBP/yr)": round(ashp_cost),
        "Gas cost (GBP/yr)": round(gas_cost),
        "Annual saving (GBP)": round(saving),
        "Installed cost (GBP)": spec["installed_cost_gbp"],
        "Net capital (GBP)": net_capital,
        "Payback (yr)": round(simple_payback(net_capital, saving), 1),
        "Break-even price (p/kWh)": round(breakeven, 2),
        "Required reduction (p/kWh)": round(
            config.OFGEM_ANNUAL_AVG_P - breakeven, 2
        ),
        "Required reduction (%)": round(
            100 * (config.OFGEM_ANNUAL_AVG_P - breakeven)
            / config.OFGEM_ANNUAL_AVG_P,
            1,
        ),
    }

    for years in config.APPRAISAL_HORIZONS:
        result[f"NPV {years}yr (GBP)"] = round(
            net_present_value(net_capital, saving, years)
        )

    return result
