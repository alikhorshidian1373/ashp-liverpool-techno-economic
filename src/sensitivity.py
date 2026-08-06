"""
Sensitivity and policy scenario analysis.

Tornado analysis over the three cost drivers, and the capital grant that would
be needed to reach a target payback under current prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, economics


# ─────────────────────────────────────────────────────────────────────────────
# Tornado
# ─────────────────────────────────────────────────────────────────────────────

def _npv_with(
    ashp_cost: float,
    gas_cost: float,
    net_capital: float,
    years: int,
) -> float:
    return economics.net_present_value(net_capital, gas_cost - ashp_cost, years)


def tornado(
    row: dict,
    swing: float = config.SENSITIVITY_SWING,
    years: int = config.APPRAISAL_YEARS,
) -> pd.DataFrame:
    """
    NPV response to a symmetric swing in each cost driver.

    The swing is applied to the *input* and the appraisal re-solved — not
    applied to the NPV output. The response is not proportional, because
    electricity and gas prices act through the annual saving while installed
    cost acts on the capital term alone.
    """
    ashp = row["ASHP cost (GBP/yr)"]
    gas = row["Gas cost (GBP/yr)"]
    capital = row["Net capital (GBP)"]

    base = _npv_with(ashp, gas, capital, years)

    cases = {
        # Dearer electricity raises the ASHP running cost
        "Electricity price": (
            _npv_with(ashp * (1 + swing), gas, capital, years),
            _npv_with(ashp * (1 - swing), gas, capital, years),
        ),
        # Dearer gas raises the boiler baseline, which helps the ASHP
        "Gas price": (
            _npv_with(ashp, gas * (1 + swing), capital, years),
            _npv_with(ashp, gas * (1 - swing), capital, years),
        ),
        # Installed cost moves the capital term only
        "Installed cost": (
            _npv_with(ashp, gas, capital * (1 + swing), years),
            _npv_with(ashp, gas, capital * (1 - swing), years),
        ),
    }

    rows = []
    for variable, (high, low) in cases.items():
        rows.append(
            {
                "Dwelling type": row["Dwelling type"],
                "Variable": variable,
                "Base NPV (GBP)": round(base),
                "NPV at +swing (GBP)": round(high),
                "NPV at -swing (GBP)": round(low),
                "Swing width (GBP)": round(abs(high - low)),
            }
        )

    out = pd.DataFrame(rows)
    return out.sort_values("Swing width (GBP)", ascending=False).reset_index(drop=True)


def tornado_all(results: pd.DataFrame) -> pd.DataFrame:
    """Tornado for every dwelling type, stacked."""
    frames = [tornado(row) for _, row in results.iterrows()]
    return pd.concat(frames, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Required capital grant
# ─────────────────────────────────────────────────────────────────────────────

def required_grant(
    row: dict,
    target_years: int = config.APPRAISAL_YEARS,
) -> float:
    """
    Grant needed to bring NPV to zero over the target horizon.

    With a negative annual saving the grant has to cover the installed cost
    *and* offset the discounted running cost penalty, so it necessarily exceeds
    the capital cost alone.
    """
    saving = row["Annual saving (GBP)"]
    installed = row["Installed cost (GBP)"]
    af = economics.annuity_factor(config.DISCOUNT_RATE, target_years)

    return installed - saving * af


def grant_table(
    results: pd.DataFrame,
    target_years: int = config.APPRAISAL_YEARS,
) -> pd.DataFrame:
    """Required versus current grant, per dwelling type."""
    rows = []
    for _, row in results.iterrows():
        needed = required_grant(row, target_years)
        rows.append(
            {
                "Dwelling type": row["Dwelling type"],
                "Installed cost (GBP)": row["Installed cost (GBP)"],
                "Current BUS grant (GBP)": config.BUS_GRANT_GBP,
                "Required grant (GBP)": round(needed),
                "Shortfall (GBP)": round(needed - config.BUS_GRANT_GBP),
            }
        )
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Policy scenarios
# ─────────────────────────────────────────────────────────────────────────────

def policy_scenarios(results: pd.DataFrame) -> pd.DataFrame:
    """
    NPV under three candidate interventions.

    Levy rebalancing figure follows Rosenow et al. (2025), who model the removal
    of environmental and social levies from electricity bills as worth roughly
    6 p/kWh.
    """
    scenarios = {
        "Base case": {"elec_cut_p": 0.0, "grant": config.BUS_GRANT_GBP},
        "Levy rebalancing (-6p/kWh)": {"elec_cut_p": 6.0, "grant": config.BUS_GRANT_GBP},
        "Grant uplift to GBP 10,000": {"elec_cut_p": 0.0, "grant": 10000},
        "Combined (-10% elec + GBP 10,000)": {
            "elec_cut_p": config.OFGEM_ANNUAL_AVG_P * 0.10,
            "grant": 10000,
        },
    }

    rows = []
    for _, row in results.iterrows():
        for name, s in scenarios.items():
            # Scale running cost by the proportional price change
            factor = (
                config.OFGEM_ANNUAL_AVG_P - s["elec_cut_p"]
            ) / config.OFGEM_ANNUAL_AVG_P

            ashp = row["ASHP cost (GBP/yr)"] * factor
            saving = row["Gas cost (GBP/yr)"] - ashp
            capital = row["Installed cost (GBP)"] - s["grant"]

            npv = economics.net_present_value(capital, saving)

            rows.append(
                {
                    "Dwelling type": row["Dwelling type"],
                    "Scenario": name,
                    "Annual saving (GBP)": round(saving),
                    "NPV 15yr (GBP)": round(npv),
                    "Viable": "Yes" if npv > 0 else "No",
                }
            )

    return pd.DataFrame(rows)
