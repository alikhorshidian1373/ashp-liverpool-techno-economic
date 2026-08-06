"""
Model configuration.

Every constant here traces to a published source. Where a value is an engineering
judgement rather than a citation, the comment says so.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Study definition
# ─────────────────────────────────────────────────────────────────────────────

BASE_YEAR = 2025

# Liverpool city centre. Used for the Open-Meteo request.
LATITUDE = 53.4084
LONGITUDE = -2.9916
LOCATION_NAME = "Liverpool"

# Five complete years averaged into one representative year. Long enough to
# smooth out an anomalous heating season, short enough to stay representative
# of the current climate.
WEATHER_START_YEAR = 2020
WEATHER_END_YEAR = 2025


# ─────────────────────────────────────────────────────────────────────────────
# Energy prices — Ofgem standard variable tariff, 2025
# Source: Ofgem quarterly price cap announcements
# The SVT applies to roughly 29 million UK households (HoC Library CBP-9491),
# which makes it the right basis for a study of typical household economics.
# ─────────────────────────────────────────────────────────────────────────────

OFGEM_Q1_P = 24.86  # Jan–Mar, p/kWh
OFGEM_Q2_P = 27.03  # Apr–Jun
OFGEM_Q3_P = 25.73  # Jul–Sep
OFGEM_Q4_P = 26.35  # Oct–Dec

OFGEM_QUARTERLY_P = {1: OFGEM_Q1_P, 2: OFGEM_Q2_P, 3: OFGEM_Q3_P, 4: OFGEM_Q4_P}
OFGEM_ANNUAL_AVG_P = sum(OFGEM_QUARTERLY_P.values()) / 4  # 25.99 p/kWh

# Gas: 2025 SVT annual average. Quarterly variation is only 0.70 p/kWh across
# the year, small enough that a flat rate introduces negligible error.
GAS_PRICE_P_PER_KWH = 6.49
GAS_PRICE_GBP_PER_KWH = GAS_PRICE_P_PER_KWH / 100

# Seasonal efficiency of a modern condensing boiler in situ. Lower than the
# lab-rated figure because real return temperatures often exceed the dew point.
BOILER_EFFICIENCY = 0.90


# ─────────────────────────────────────────────────────────────────────────────
# Financial appraisal
# ─────────────────────────────────────────────────────────────────────────────

# Social Time Preference Rate, HM Treasury Green Book
DISCOUNT_RATE = 0.035

# Boiler Upgrade Scheme, DESNZ
BUS_GRANT_GBP = 7500

APPRAISAL_YEARS = 15
APPRAISAL_HORIZONS = (10, 15, 20)

# Applied to electricity price, gas price and installed cost in the tornado
SENSITIVITY_SWING = 0.20


# ─────────────────────────────────────────────────────────────────────────────
# Flow temperature and weather compensation
# ─────────────────────────────────────────────────────────────────────────────

# UK standard heating threshold — above this, internal and solar gains meet
# demand. Park et al. (2021); CIBSE Guide A.
T_BALANCE_POINT_C = 15.5

# Lower limit for standard radiator output. Below this a retrofit radiator
# circuit cannot deliver useful heat. Staffell et al. (2012); CIBSE Guide A.
T_FLOW_MIN_C = 35.0

# MCS MIS 3005-D ss. 3.4.3, 3.5.5. Must equal T_FLOW_DESIGN_C so the curve is
# consistent with the A7/W55 calibration point.
T_FLOW_MAX_C = 55.0
T_FLOW_DESIGN_C = 55.0

# Design outdoor temperature is not hardcoded — it is derived at runtime as the
# 1st percentile of the hourly record, which is what MCS MIS 3005-D Table 2
# Col A specifies (99th percentile exceedance). For Liverpool this comes out
# around -0.6 °C.
DESIGN_TEMP_PERCENTILE = 1


# ─────────────────────────────────────────────────────────────────────────────
# Domestic hot water
# ─────────────────────────────────────────────────────────────────────────────

# Cylinder target. Fixed year-round — weather compensation does not apply to
# DHW. MCS MIS 3005-D.
T_DHW_C = 55.0
T_DHW_K = T_DHW_C + 273.15

# MCS 031 a) Issue 1.0, operative Jan–Dec 2025. eta_dhw is calibrated to
# reproduce this figure, so it is an input, not a result.
MCS_SPF_DHW = 1.70

# Air-source extraction below freezing enters heavy defrost cycling and departs
# from Carnot behaviour. Flooring the source keeps the model defensible.
T_SOURCE_MIN_K = 273.15


# ─────────────────────────────────────────────────────────────────────────────
# COP clipping
# Guards against the Carnot relationship producing values the machine could
# not physically deliver at extreme temperature differences.
# ─────────────────────────────────────────────────────────────────────────────

COP_SPACE_MIN, COP_SPACE_MAX = 1.5, 5.0
COP_DHW_MIN, COP_DHW_MAX = 1.2, 3.2


# ─────────────────────────────────────────────────────────────────────────────
# EN 14511 reference test condition (A7/W55)
# 7 °C outdoor air, 55 °C flow water. BS EN 14511-2:2022 Table 14.
# This is a laboratory condition, not an operating state — the weather
# compensation curve only reaches 55 °C flow at the design outdoor temperature.
# ─────────────────────────────────────────────────────────────────────────────

T_AIR_REF_K = 7 + 273.15    # 280.15
T_FLOW_REF_K = 55 + 273.15  # 328.15
COP_CARNOT_REF = T_FLOW_REF_K / (T_FLOW_REF_K - T_AIR_REF_K)  # 6.836


# ─────────────────────────────────────────────────────────────────────────────
# Heat demand
# DECC (2014) URN 14D/435 benchmarks for North West England, +1% for
# Liverpool's sub-regional position. Split follows Phillips and Wilson (2024),
# who separate temperature-dependent from baseload gas consumption.
# Cooking gas excluded — heating system replacement does not affect it.
# ─────────────────────────────────────────────────────────────────────────────

SPACE_HEATING_FRACTION = 0.88
DHW_FRACTION = 0.12

ANNUAL_HEAT_DEMAND_KWH = {
    "Flat": 7026.34,
    "Mid-Terrace": 9459.23,
    "Semi-Detached": 11645.78,
    "Detached": 17468.67,
}


# ─────────────────────────────────────────────────────────────────────────────
# Heat pump units — Vaillant aroTHERM plus
# COP figures from the manufacturer technical data (p. 45), measured under
# EN 14511 at A7/W55. Installed costs from DESNZ BUS statistics and the UKERC
# evidence review.
# ─────────────────────────────────────────────────────────────────────────────

ASHP_SPECS = {
    "Flat": {
        "capacity_kW": 5,
        "installed_cost_gbp": 9000,
        "cop_a7w55": 2.80,
        "model": "Vaillant VWL 55/6 A S3",
    },
    "Mid-Terrace": {
        "capacity_kW": 6,
        "installed_cost_gbp": 10000,
        "cop_a7w55": 2.90,
        "model": "Vaillant VWL 85/6 A S3",
    },
    "Semi-Detached": {
        "capacity_kW": 9,
        "installed_cost_gbp": 11500,
        "cop_a7w55": 2.90,
        "model": "Vaillant VWL 85/6 A S3",
    },
    "Detached": {
        "capacity_kW": 12,
        "installed_cost_gbp": 13500,
        "cop_a7w55": 2.90,
        "model": "Vaillant VWL 95/6 A S3",
    },
}

DWELLING_TYPES = list(ASHP_SPECS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Indoor temperatures
# Measured, not assumed. EFUS 2011 Report 2 — what people actually heat their
# homes to, which is lower than design assumptions in winter.
# ─────────────────────────────────────────────────────────────────────────────

INDOOR_TEMP_C = {
    "winter": 19.0,  # Dec–Feb
    "spring": 19.5,  # Mar–May
    "summer": 21.5,  # Jun–Aug
    "autumn": 19.5,  # Sep–Nov
}

MONTH_TO_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


# ─────────────────────────────────────────────────────────────────────────────
# Field validation benchmark
# Energy Systems Catapult (2024), Electrification of Heat. 742 monitored
# installations, the best UK field dataset available.
# ─────────────────────────────────────────────────────────────────────────────

EOH_SPFH2_MEDIAN = 2.93  # excludes auxiliary loads — comparable to model SCOP
EOH_SPFH4_MEDIAN = 2.78  # whole-system boundary — the conservative figure


# ─────────────────────────────────────────────────────────────────────────────
# Output paths
# ─────────────────────────────────────────────────────────────────────────────

FIGURES_DIR = "figures"
RESULTS_DIR = "results"
CACHE_DIR = "data/cache"

FIGURE_DPI = 300
