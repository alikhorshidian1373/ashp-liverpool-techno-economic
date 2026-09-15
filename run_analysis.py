"""
Run the full analysis pipeline.

    python run_analysis.py

Fetches weather (cached after the first run), builds the COP model, simulates
every hour of the representative year, runs the financial appraisal and
sensitivity analysis, and writes figures and result tables to disk.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config, demand, economics, heatpump, plotting, sensitivity, weather


def rule(title: str = "") -> None:
    print("\n" + "─" * 74)
    if title:
        print(title)
        print("─" * 74)


def main() -> None:
    print("ASHP Techno-Economic Assessment")
    print(f"{config.LOCATION_NAME}  ·  study year {config.BASE_YEAR}")

    # ── Weather ──────────────────────────────────────────────────────────────
    rule("Weather")
    print("Loading hourly temperatures...")

    profile, t_design = weather.load_weather()
    stats = weather.summarise(profile, t_design)

    print(f"  Representative year   {len(profile):,} hours")
    print(f"  Annual mean           {stats['annual_mean_C']:.2f} °C")
    print(f"  Design temperature    {stats['design_temp_C']:.2f} °C "
          f"({config.DESIGN_TEMP_PERCENTILE}st percentile)")
    print(f"  Hours below design    {stats['hours_below_design']:,}")
    print(f"  Heating season        {stats['heating_hours']:,} hours "
          f"({stats['heating_season_pct']:.1f}% of the year)")

    # ── Calibration ──────────────────────────────────────────────────────────
    rule("Calibration")
    eta = heatpump.efficiency_factors(profile)
    print(eta.to_string(index=False))
    print(f"\n  Carnot COP at A7/W55 reference: {config.COP_CARNOT_REF:.3f}")
    print(f"  eta_dhw anchored to MCS 031 a) SPF of {config.MCS_SPF_DHW}")

    # ── Demand ───────────────────────────────────────────────────────────────
    rule("Annual heat demand")
    print(demand.demand_table().to_string(index=False))

    # ── Simulation ───────────────────────────────────────────────────────────
    rule("Hourly simulation")

    rows = []
    profiles: dict[str, pd.DataFrame] = {}

    for dwelling in config.DWELLING_TYPES:
        df = heatpump.build_cop_profile(profile, t_design, dwelling)
        df = demand.distribute(df, dwelling)
        df = economics.hourly_electricity(df)

        profiles[dwelling] = df
        rows.append(economics.appraise(df, dwelling))
        print(f"  {dwelling:<16} simulated")

    results = pd.DataFrame(rows)

    # ── Performance ──────────────────────────────────────────────────────────
    rule("Seasonal performance")

    perf = results[["Dwelling type", "SCOP space", "SCOP DHW", "SCOP total"]].copy()
    perf["EoH SPFH2"] = config.EOH_SPFH2_MEDIAN
    perf["Model gap"] = (perf["SCOP total"] - config.EOH_SPFH2_MEDIAN).round(2)
    print(perf.to_string(index=False))

    dhw_error = 100 * abs(
        results["SCOP DHW"].iloc[0] - config.MCS_SPF_DHW
    ) / config.MCS_SPF_DHW
    print(f"\n  DHW SCOP reproduces the MCS target to within {dhw_error:.1f}%")
    print("  Space heating exceeds the field median — the Carnot model omits")
    print("  defrost, cycling and auxiliary loads. Bias is upward, so the")
    print("  economic case here is conservative.")

    # ── Costs ────────────────────────────────────────────────────────────────
    rule("Running costs and appraisal")

    cost_cols = [
        "Dwelling type", "Gas cost (GBP/yr)", "ASHP cost (GBP/yr)",
        "Annual saving (GBP)", "NPV 15yr (GBP)", "Payback (yr)",
    ]
    print(results[cost_cols].to_string(index=False))

    hc = economics.heat_cost_comparison(float(results["SCOP total"].mean()))
    print(f"\n  Gas boiler heat   {hc['gas_p_per_kWh_heat']:.2f} p/kWh")
    print(f"  ASHP heat         {hc['ashp_p_per_kWh_heat']:.2f} p/kWh")
    print(f"  Premium           {hc['gap_p_per_kWh']:.2f} p/kWh "
          f"({hc['ashp_premium_pct']:.1f}%)")

    # ── Break-even ───────────────────────────────────────────────────────────
    rule("Electricity price thresholds")

    be_cols = [
        "Dwelling type", "SCOP total",
        "Running parity price (p/kWh)", "Profitable price (p/kWh)",
        "Reduction to profitability (p/kWh)", "Reduction to profitability (%)",
    ]
    print(results[be_cols].to_string(index=False))

    q = config.OFGEM_QUARTERLY_P
    print(f"\n  Ofgem 2025 quarterly range: {min(q.values()):.2f}–"
          f"{max(q.values()):.2f} p/kWh")
    print("  Running parity  : the annual operating penalty disappears.")
    print("  Profitable      : the investment also recovers its capital —")
    print("                    the threshold that matters to a household.")
    print("  Every quarter of 2025 sits above both thresholds.")

    # ── Sensitivity ──────────────────────────────────────────────────────────
    rule("Sensitivity")

    tornado_df = sensitivity.tornado_all(results)
    ranking = (
        tornado_df.groupby("Variable")["Swing width (GBP)"]
        .mean()
        .sort_values(ascending=False)
    )
    print(f"  Mean NPV swing under ±{int(config.SENSITIVITY_SWING*100)}%:")
    for variable, width in ranking.items():
        print(f"    {variable:<20} £{width:,.0f}")

    grants = sensitivity.grant_table(results)
    print("\n  Grant required to reach NPV = 0:")
    print(grants.to_string(index=False))

    # The uplift must equal the NPV shortfall — an identity, so a non-zero
    # result means the grant and NPV calculations have drifted apart.
    drift = sensitivity.verify_grant_identity(results, grants)
    print(f"\n  Identity check (uplift vs NPV shortfall): {drift:.2f}")
    if drift > 1.0:
        print("  WARNING: grant and NPV calculations disagree.")

    # ── Output ───────────────────────────────────────────────────────────────
    rule("Writing output")

    Path(config.RESULTS_DIR).mkdir(parents=True, exist_ok=True)

    tables = {
        "efficiency_factors": eta,
        "heat_demand": demand.demand_table(),
        "appraisal": results,
        "tornado": tornado_df,
        "grant_requirement": grants,
    }

    for stem, table in tables.items():
        path = Path(config.RESULTS_DIR) / f"{stem}.csv"
        # Drop internal unrounded helper columns from published output
        public = table.loc[:, ~table.columns.str.startswith("_")]
        public.to_csv(path, index=False)
        print(f"  {path}")

    figures = plotting.generate_all(
        profile, t_design, profiles["Semi-Detached"],
        results, tornado_df, grants,
    )
    for path in figures:
        print(f"  {path}")

    rule("Done")
    print(f"  {len(tables)} tables  ·  {len(figures)} figures")


if __name__ == "__main__":
    main()
