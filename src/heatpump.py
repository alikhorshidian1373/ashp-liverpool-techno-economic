"""
Heat pump thermodynamic model.

Implements weather-compensated flow temperature control and a Carnot-framework
dynamic COP model following Staffell et al. (2012), calibrated against EN 14511
manufacturer test data for space heating and the MCS 031 a) default seasonal
performance factor for hot water.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ─────────────────────────────────────────────────────────────────────────────
# Weather compensation
# ─────────────────────────────────────────────────────────────────────────────

def flow_temperature(outdoor_temp_C: np.ndarray, t_design_C: float) -> np.ndarray:
    """
    Weather-compensated flow temperature.

    Linear between two anchors: maximum flow at the design outdoor temperature,
    minimum flow at the balance point. The linear form follows from combining
    the heat loss relationship in BS EN 12831-1 (loss proportional to indoor
    minus outdoor) with approximately linear radiator output across this
    operating range (CIBSE Guide A).

    Below the design temperature the curve saturates at maximum flow; above the
    balance point it saturates at minimum and heating ceases.
    """
    span = config.T_BALANCE_POINT_C - t_design_C

    fraction = np.clip(
        (config.T_BALANCE_POINT_C - outdoor_temp_C) / span, 0.0, 1.0
    )

    flow = config.T_FLOW_MIN_C + (
        config.T_FLOW_DESIGN_C - config.T_FLOW_MIN_C
    ) * fraction

    return np.clip(flow, config.T_FLOW_MIN_C, config.T_FLOW_MAX_C)


# ─────────────────────────────────────────────────────────────────────────────
# Efficiency factor calibration
# ─────────────────────────────────────────────────────────────────────────────

def eta_space(cop_a7w55: float) -> float:
    """
    Carnot efficiency factor for space heating.

    The A7/W55 test point is a laboratory condition, not an operating state —
    the weather compensation curve only reaches 55 °C flow at the design outdoor
    temperature, whereas A7 corresponds to a mild 7 °C day. Its role is purely
    to anchor eta against a measured datapoint.

    Calibrating at W55 rather than W35 is deliberate: a retrofit radiator
    circuit operates up to 55 °C, and the lower underfloor test condition would
    systematically overstate performance.
    """
    return cop_a7w55 / config.COP_CARNOT_REF


def eta_dhw(t_outdoor_mean_C: float) -> float:
    """
    Carnot efficiency factor for hot water.

    No manufacturer test condition corresponds to annual-average DHW operation,
    so eta is instead calibrated so the simulated annual mean reproduces the
    MCS 031 a) default SPF of 1.70. Evaluated at the annual mean outdoor
    temperature because the MCS figure is itself an annual seasonal average.
    """
    t_mean_K = t_outdoor_mean_C + 273.15
    cop_carnot = config.T_DHW_K / (config.T_DHW_K - t_mean_K)
    return config.MCS_SPF_DHW / cop_carnot


# ─────────────────────────────────────────────────────────────────────────────
# Hourly COP
# ─────────────────────────────────────────────────────────────────────────────

def cop_space(
    eta: float,
    flow_temp_C: np.ndarray,
    outdoor_temp_C: np.ndarray,
) -> np.ndarray:
    """
    Hourly space heating COP.

    Both sink and source vary hour to hour, though only one is independent:
    flow temperature is itself a function of outdoor temperature through the
    compensation curve. Set to NaN above the balance point, where no space
    heating is called for.
    """
    flow_K = flow_temp_C + 273.15
    outdoor_K = outdoor_temp_C + 273.15

    with np.errstate(divide="ignore", invalid="ignore"):
        cop = eta * flow_K / (flow_K - outdoor_K)

    cop = np.clip(cop, config.COP_SPACE_MIN, config.COP_SPACE_MAX)
    cop = np.where(outdoor_temp_C >= config.T_BALANCE_POINT_C, np.nan, cop)

    return cop


def cop_dhw(eta: float, outdoor_temp_C: np.ndarray) -> np.ndarray:
    """
    Hourly hot water COP.

    The sink is fixed at 55 °C year-round, so unlike space heating only the
    source varies. Source is floored at 0 °C: below freezing an air-source unit
    enters heavy defrost cycling and departs from Carnot behaviour, so allowing
    the denominator to keep growing would predict performance the machine
    cannot deliver.

    Runs all 8,760 hours — hot water demand does not stop in summer.
    """
    source_K = np.maximum(outdoor_temp_C + 273.15, config.T_SOURCE_MIN_K)

    with np.errstate(divide="ignore", invalid="ignore"):
        cop = eta * config.T_DHW_K / (config.T_DHW_K - source_K)

    return np.clip(cop, config.COP_DHW_MIN, config.COP_DHW_MAX)


# ─────────────────────────────────────────────────────────────────────────────
# Assembly
# ─────────────────────────────────────────────────────────────────────────────

def build_cop_profile(
    weather: pd.DataFrame,
    t_design_C: float,
    dwelling: str,
) -> pd.DataFrame:
    """
    Hourly flow temperature and COP series for one dwelling type.

    Returns the weather frame with ``flow_temp_C``, ``cop_space`` and
    ``cop_dhw`` columns appended.
    """
    spec = config.ASHP_SPECS[dwelling]

    df = weather.copy()
    df["flow_temp_C"] = flow_temperature(
        df["outdoor_temp_C"].to_numpy(), t_design_C
    )

    e_space = eta_space(spec["cop_a7w55"])
    e_dhw = eta_dhw(float(weather["outdoor_temp_C"].mean()))

    df["cop_space"] = cop_space(
        e_space,
        df["flow_temp_C"].to_numpy(),
        df["outdoor_temp_C"].to_numpy(),
    )
    df["cop_dhw"] = cop_dhw(e_dhw, df["outdoor_temp_C"].to_numpy())

    return df


def efficiency_factors(weather: pd.DataFrame) -> pd.DataFrame:
    """Calibrated eta values per dwelling, for reporting and audit."""
    e_dhw = eta_dhw(float(weather["outdoor_temp_C"].mean()))

    rows = []
    for dwelling, spec in config.ASHP_SPECS.items():
        rows.append(
            {
                "Dwelling type": dwelling,
                "Model": spec["model"],
                "Capacity (kW)": spec["capacity_kW"],
                "COP A7/W55": spec["cop_a7w55"],
                "eta_space": round(eta_space(spec["cop_a7w55"]), 4),
                "eta_dhw": round(e_dhw, 4),
            }
        )

    return pd.DataFrame(rows)
