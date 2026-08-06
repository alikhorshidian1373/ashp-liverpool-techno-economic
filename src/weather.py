"""
Weather data retrieval and representative year construction.

Pulls hourly outdoor temperatures from the Open-Meteo Historical Archive API,
caches them locally, and collapses several years into a single representative
8,760-hour profile.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import config

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def _cache_path() -> Path:
    """Where the raw download lives once fetched."""
    name = (
        f"{config.LOCATION_NAME.lower()}_"
        f"{config.WEATHER_START_YEAR}_{config.WEATHER_END_YEAR}.parquet"
    )
    return Path(config.CACHE_DIR) / name


def fetch_hourly_temperatures(use_cache: bool = True) -> pd.DataFrame:
    """
    Retrieve hourly 2 m air temperature for the configured location and period.

    Returns a frame indexed by timestamp with a single ``outdoor_temp_C`` column.
    The API is queried once and the result cached, so repeat runs are offline.
    """
    cache = _cache_path()

    if use_cache and cache.exists():
        return pd.read_parquet(cache)

    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "start_date": f"{config.WEATHER_START_YEAR}-01-01",
        "end_date": f"{config.WEATHER_END_YEAR}-12-31",
        "hourly": "temperature_2m",
        "timezone": "Europe/London",
    }

    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(payload["hourly"]["time"]),
            "outdoor_temp_C": payload["hourly"]["temperature_2m"],
        }
    ).set_index("timestamp")

    df = df.dropna()

    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)

    return df


def build_representative_year(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse a multi-year record into one representative 8,760-hour year.

    Averaging by (month, day, hour) keeps the diurnal and seasonal structure the
    COP model depends on while damping any single anomalous heating season.
    29 February is dropped so every year contributes equally.
    """
    df = raw.copy()
    df["month"] = df.index.month
    df["day"] = df.index.day
    df["hour"] = df.index.hour

    df = df[~((df["month"] == 2) & (df["day"] == 29))]

    profile = (
        df.groupby(["month", "day", "hour"])["outdoor_temp_C"]
        .mean()
        .reset_index()
        .sort_values(["month", "day", "hour"])
        .reset_index(drop=True)
    )

    profile["hour_of_year"] = profile.index
    profile["quarter"] = ((profile["month"] - 1) // 3) + 1
    profile["season"] = profile["month"].map(config.MONTH_TO_SEASON)
    profile["indoor_temp_C"] = profile["season"].map(config.INDOOR_TEMP_C)
    profile["outdoor_temp_K"] = profile["outdoor_temp_C"] + 273.15

    return profile


def design_temperature(raw: pd.DataFrame) -> float:
    """
    Outdoor design temperature, taken as the 1st percentile of the full hourly
    record.

    This is the same thing as the 99th percentile exceedance temperature that
    MCS MIS 3005-D Table 2 Col A specifies: the temperature exceeded 99% of
    hours. Derived from the whole record rather than winter only, because that
    is how the standard defines it — and in a maritime climate the bottom 1% is
    winter nights regardless.
    """
    return float(
        np.percentile(raw["outdoor_temp_C"], config.DESIGN_TEMP_PERCENTILE)
    )


def load_weather(use_cache: bool = True) -> tuple[pd.DataFrame, float]:
    """Convenience wrapper: representative year plus design temperature."""
    raw = fetch_hourly_temperatures(use_cache=use_cache)
    return build_representative_year(raw), design_temperature(raw)


def summarise(profile: pd.DataFrame, t_design: float) -> dict:
    """Descriptive statistics for the README and for sanity-checking a run."""
    heating_hours = int((profile["outdoor_temp_C"] < config.T_BALANCE_POINT_C).sum())

    return {
        "annual_mean_C": round(float(profile["outdoor_temp_C"].mean()), 2),
        "design_temp_C": round(t_design, 2),
        "coldest_hour_C": round(float(profile["outdoor_temp_C"].min()), 2),
        "warmest_hour_C": round(float(profile["outdoor_temp_C"].max()), 2),
        "heating_hours": heating_hours,
        "heating_season_pct": round(100 * heating_hours / len(profile), 1),
        "hours_below_design": int(
            (profile["outdoor_temp_C"] < t_design).sum()
        ),
    }
