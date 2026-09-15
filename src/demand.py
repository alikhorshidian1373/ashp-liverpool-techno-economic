"""
Heat demand quantification and hourly distribution.

Annual benchmark demands are split into space heating and hot water, then
distributed across the 8,760-hour year — space heating by degree-hour weighting,
hot water uniformly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def annual_demand(dwelling: str) -> dict[str, float]:
    """Annual space heating and hot water demand for one dwelling type, kWh."""
    total = config.ANNUAL_HEAT_DEMAND_KWH[dwelling]

    return {
        "total_kWh": total,
        "space_kWh": total * config.SPACE_HEATING_FRACTION,
        "dhw_kWh": total * config.DHW_FRACTION,
    }


def demand_table() -> pd.DataFrame:
    """Annual demands for all dwelling types — reproduces Table I of the report."""
    rows = []
    for dwelling in config.DWELLING_TYPES:
        d = annual_demand(dwelling)
        rows.append(
            {
                "Dwelling type": dwelling,
                "Total (kWh/yr)": round(d["total_kWh"]),
                "Space heating (kWh/yr)": round(d["space_kWh"]),
                "DHW (kWh/yr)": round(d["dhw_kWh"]),
            }
        )
    return pd.DataFrame(rows)


def degree_hour_weights(weather: pd.DataFrame) -> np.ndarray:
    """
    Normalised hourly weights for distributing space heating demand.

    Weight is proportional to the instantaneous gap between the seasonal indoor
    set point and outdoor temperature, and zero above the balance point. Using
    measured EFUS indoor temperatures rather than a fixed design assumption
    means the profile reflects how people actually heat their homes.
    """
    delta = weather["indoor_temp_C"].to_numpy() - weather["outdoor_temp_C"].to_numpy()
    delta = np.maximum(delta, 0.0)

    heating_active = weather["outdoor_temp_C"].to_numpy() < config.T_BALANCE_POINT_C
    delta = np.where(heating_active, delta, 0.0)

    total = delta.sum()
    if total == 0:
        raise ValueError("No heating hours found — check the weather profile.")

    return delta / total


def distribute(weather: pd.DataFrame, dwelling: str) -> pd.DataFrame:
    """
    Hourly heat demand series for one dwelling.

    Space heating follows the degree-hour profile; hot water is spread evenly,
    reflecting its near-constant year-round draw.
    """
    d = annual_demand(dwelling)
    weights = degree_hour_weights(weather)

    df = weather.copy()
    df["Q_space_kWh"] = d["space_kWh"] * weights
    df["Q_dhw_kWh"] = d["dhw_kWh"] / len(weather)
    df["Q_total_kWh"] = df["Q_space_kWh"] + df["Q_dhw_kWh"]

    return df
