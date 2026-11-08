"""
Microbially-limited shelf-life and predictive growth models for Aavaran.

Implements Section 5.4 of BLUEPRINT.md:
- Extended Ratkowsky / Belehrádek square-root growth-rate model:
    √μ_max = b · (T − T_min) · f(a_w) · f(pH) · f(CO₂)
- Organism parameters seeded from ComBase predictive microbiology models:
    * Pseudomonas spp. (strictly aerobic psychrotrophic spoilage)
    * Lactic acid bacteria (facultative anaerobe spoilage in MAP)
    * Listeria monocytogenes (psychrotrophic pathogen)
    * Clostridium botulinum (non-proteolytic type E, T_min = 3.3 °C)
- Time to spoilage calculation including physiological lag phase:
    t_spoil = (log10 N_spoil − log10 N_0) / (μ_max / ln10) + t_lag
- Explicit dissolved CO2 inhibition term f(CO2), preventing systematic
  under-prediction of MAP shelf life.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from pydantic import BaseModel, Field

from engine.types import CommodityProfile, Environment, PackageCandidate

logger = logging.getLogger(__name__)

# Equation IDs
EQ_MICROBIAL_GROWTH = "MIC-01"


# ---------------------------------------------------------------------------
# Organism Parameters Schema & ComBase Registry
# ---------------------------------------------------------------------------


class OrganismParams(BaseModel):
    """Kinetic parameters for microbial growth from ComBase-derived data."""

    name: str = Field(..., description="Organism scientific or common group name")
    organism_type: str = Field(..., description="'spoilage' or 'pathogen'")
    b: float = Field(
        ...,
        description="Ratkowsky temperature coefficient in (degC · day^(1/2))^(-1)",
    )
    t_min_c: float = Field(
        ..., description="Theoretical minimum growth temperature in degC"
    )
    t_max_c: float = Field(
        default=42.0, description="Maximum growth temperature in degC"
    )
    t_opt_c: float = Field(
        default=30.0, description="Optimal growth temperature in degC"
    )
    aw_min: float = Field(..., description="Minimum water activity supporting growth")
    ph_min: float = Field(..., description="Minimum pH supporting growth")
    ph_max: float = Field(default=9.0, description="Maximum pH supporting growth")
    co2_sensitivity: float = Field(
        default=0.0,
        description="Sensitivity coefficient k_CO2 to in-pack/dissolved CO2 inhibition",
    )
    requires_o2: bool = Field(
        default=False,
        description="True for obligate aerobes stalled at O2 < 1%",
    )
    anaerobic_only: bool = Field(
        default=False,
        description="True for obligate anaerobes inhibited at O2 >= 2%",
    )
    n_0_default: float = Field(
        default=3.0,
        description="Default initial population in log10(CFU/g)",
    )
    n_spoil_default: float = Field(
        default=7.0,
        description="Default spoilage/regulatory threshold in log10(CFU/g)",
    )
    h0_lag: float = Field(
        default=2.0,
        description="Dimensionless physiological lag parameter (h0 = mu * t_lag)",
    )
    combase_ref: str | None = Field(
        default=None,
        description="Reference citation in ComBase database",
    )


# Seeded ComBase Organism Database
COMBASE_ORGANISMS: dict[str, OrganismParams] = {
    "pseudomonas": OrganismParams(
        name="Pseudomonas spp.",
        organism_type="spoilage",
        b=0.165,
        t_min_c=-3.0,
        t_max_c=35.0,
        t_opt_c=25.0,
        aw_min=0.96,
        ph_min=5.0,
        ph_max=8.5,
        co2_sensitivity=0.70,  # Highly sensitive to CO2 inhibition
        requires_o2=True,  # Obligate aerobe: requires >= 1% O2
        anaerobic_only=False,
        n_0_default=3.0,
        n_spoil_default=7.5,  # Slime / off-odor threshold
        h0_lag=2.0,
        combase_ref="ComBase: Pseudomonas spp. in aerobic/MAP food systems",
    ),
    "lactic_acid_bacteria": OrganismParams(
        name="Lactic acid bacteria",
        organism_type="spoilage",
        b=0.130,
        t_min_c=-1.0,
        t_max_c=40.0,
        t_opt_c=30.0,
        aw_min=0.93,
        ph_min=4.2,
        ph_max=8.5,
        co2_sensitivity=0.15,  # Low sensitivity: capnophilic in MAP
        requires_o2=False,  # Facultative anaerobe
        anaerobic_only=False,
        n_0_default=2.0,
        n_spoil_default=7.0,  # Souring / gas threshold
        h0_lag=2.0,
        combase_ref="ComBase: Lactic acid bacteria (Carnobacterium/Lactobacillus) MAP",
    ),
    "listeria_monocytogenes": OrganismParams(
        name="Listeria monocytogenes",
        organism_type="pathogen",
        b=0.120,
        t_min_c=-0.4,
        t_max_c=45.0,
        t_opt_c=37.0,
        aw_min=0.92,
        ph_min=4.4,
        ph_max=9.4,
        co2_sensitivity=0.40,  # Moderately inhibited by CO2
        requires_o2=False,  # Facultative anaerobe
        anaerobic_only=False,
        n_0_default=1.0,
        n_spoil_default=2.0,  # 100 CFU/g regulatory safety limit
        h0_lag=2.5,
        combase_ref="ComBase: Listeria monocytogenes broth and food matrix models",
    ),
    "clostridium_botulinum_type_e": OrganismParams(
        name="Clostridium botulinum (non-proteolytic type E)",
        organism_type="pathogen",
        b=0.110,
        t_min_c=3.3,  # Strictly 3.3 °C per Blueprint specification
        t_max_c=42.0,
        t_opt_c=30.0,
        aw_min=0.97,
        ph_min=5.0,
        ph_max=8.5,
        co2_sensitivity=0.0,  # Obligate anaerobe: not inhibited by CO2
        requires_o2=False,
        anaerobic_only=True,  # Requires O2 < 2% (0.02) to grow
        n_0_default=0.0,  # 1 spore/g (log10 = 0)
        n_spoil_default=2.0,  # Toxin detection threshold
        h0_lag=4.0,  # Spore germination + outgrowth lag
        combase_ref="ComBase: C. botulinum non-proteolytic type E models",
    ),
}

# Organism alias lookup
_ORGANISM_ALIASES: dict[str, str] = {
    "pseudomonas": "pseudomonas",
    "pseudomonas spp.": "pseudomonas",
    "pseudomonas spp": "pseudomonas",
    "lab": "lactic_acid_bacteria",
    "lactic acid bacteria": "lactic_acid_bacteria",
    "lactic_acid_bacteria": "lactic_acid_bacteria",
    "lactobacillus": "lactic_acid_bacteria",
    "listeria": "listeria_monocytogenes",
    "listeria monocytogenes": "listeria_monocytogenes",
    "listeria_monocytogenes": "listeria_monocytogenes",
    "botulinum": "clostridium_botulinum_type_e",
    "c. botulinum": "clostridium_botulinum_type_e",
    "clostridium botulinum": "clostridium_botulinum_type_e",
    "clostridium_botulinum": "clostridium_botulinum_type_e",
    "clostridium_botulinum_type_e": "clostridium_botulinum_type_e",
    "botulinum_type_e": "clostridium_botulinum_type_e",
}


def get_organism_params(identifier: str) -> OrganismParams:
    """Retrieve organism parameters by canonical ID or common name alias."""
    key = identifier.strip().lower()
    canonical = _ORGANISM_ALIASES.get(key, key)
    if canonical not in COMBASE_ORGANISMS:
        available = list(COMBASE_ORGANISMS.keys())
        msg = f"Organism '{identifier}' not found in ComBase. Available: {available}"
        raise KeyError(msg)
    return COMBASE_ORGANISMS[canonical]


# ---------------------------------------------------------------------------
# Ratkowsky Square-Root Kinetic Equations
# ---------------------------------------------------------------------------


class MicrobialGrowthResult(BaseModel):
    """Specific growth rate and cardinal term breakdown."""

    organism: str
    mu_max_per_day: float = Field(
        ..., description="Maximum specific growth rate in 1/day"
    )
    mu_max_per_hour: float = Field(
        ..., description="Maximum specific growth rate in 1/hour"
    )
    sqrt_mu_max: float = Field(..., description="Square root of mu_max")
    generation_time_hours: float = Field(
        ..., description="Doubling time in hours (ln 2 / mu_hour)"
    )
    temp_term: float = Field(..., description="Temperature factor: b * (T - T_min)")
    aw_term: float = Field(..., description="Water activity factor f(aw)")
    ph_term: float = Field(..., description="pH factor f(pH)")
    co2_term: float = Field(..., description="CO2 inhibition factor f(CO2)")
    o2_term: float = Field(..., description="Oxygen availability factor f(O2)")
    growth_possible: bool = Field(
        ..., description="True if conditions permit positive growth"
    )
    limiting_factor: str | None = Field(
        None, description="Factor halting or limiting growth"
    )


def ratkowsky_growth_rate(
    organism: str | OrganismParams,
    temperature_c: float,
    water_activity: float,
    ph: float,
    *,
    co2_fraction: float = 0.0,
    o2_fraction: float = 0.209,
    dissolved_co2_ppm: float | None = None,
) -> MicrobialGrowthResult:
    """
    Compute specific growth rate using the extended Ratkowsky square-root model:
        √μ_max = b · (T − T_min) · f(a_w) · f(pH) · f(CO₂) · f(O₂)
    """
    if isinstance(organism, str):
        params = get_organism_params(organism)
    else:
        params = organism

    # Clamp physical inputs to reasonable limits
    water_activity = max(0.0, min(1.0, float(water_activity)))
    temperature_c = float(temperature_c)
    ph = float(ph)
    co2_fraction = max(0.0, min(1.0, float(co2_fraction)))
    o2_fraction = max(0.0, min(1.0, float(o2_fraction)))

    # 1. Temperature Term: b * (T - T_min)
    if temperature_c <= params.t_min_c:
        msg = f"Temperature {temperature_c:.1f}°C <= T_min ({params.t_min_c:.1f}°C)"
        return MicrobialGrowthResult(
            organism=params.name,
            mu_max_per_day=0.0,
            mu_max_per_hour=0.0,
            sqrt_mu_max=0.0,
            generation_time_hours=float("inf"),
            temp_term=0.0,
            aw_term=0.0,
            ph_term=0.0,
            co2_term=0.0,
            o2_term=0.0,
            growth_possible=False,
            limiting_factor=msg,
        )
    if temperature_c >= params.t_max_c:
        msg = f"Temperature {temperature_c:.1f}°C >= T_max ({params.t_max_c:.1f}°C)"
        return MicrobialGrowthResult(
            organism=params.name,
            mu_max_per_day=0.0,
            mu_max_per_hour=0.0,
            sqrt_mu_max=0.0,
            generation_time_hours=float("inf"),
            temp_term=0.0,
            aw_term=0.0,
            ph_term=0.0,
            co2_term=0.0,
            o2_term=0.0,
            growth_possible=False,
            limiting_factor=msg,
        )

    temp_term = params.b * (temperature_c - params.t_min_c)

    # 2. Water Activity Term: f(aw) = sqrt((aw - aw_min) / (1 - aw_min))
    if water_activity <= params.aw_min:
        msg = f"Water activity {water_activity:.3f} <= aw_min ({params.aw_min:.2f})"
        return MicrobialGrowthResult(
            organism=params.name,
            mu_max_per_day=0.0,
            mu_max_per_hour=0.0,
            sqrt_mu_max=0.0,
            generation_time_hours=float("inf"),
            temp_term=temp_term,
            aw_term=0.0,
            ph_term=0.0,
            co2_term=0.0,
            o2_term=0.0,
            growth_possible=False,
            limiting_factor=msg,
        )
    aw_term = math.sqrt((water_activity - params.aw_min) / (1.0 - params.aw_min))

    # 3. pH Term: f(pH) = sqrt(1 - 10^(pH_min - pH))
    if ph <= params.ph_min or ph >= params.ph_max:
        msg = f"pH {ph:.2f} out of bounds [{params.ph_min:.2f}, {params.ph_max:.2f}]"
        return MicrobialGrowthResult(
            organism=params.name,
            mu_max_per_day=0.0,
            mu_max_per_hour=0.0,
            sqrt_mu_max=0.0,
            generation_time_hours=float("inf"),
            temp_term=temp_term,
            aw_term=aw_term,
            ph_term=0.0,
            co2_term=0.0,
            o2_term=0.0,
            growth_possible=False,
            limiting_factor=msg,
        )
    ph_delta = params.ph_min - ph
    ph_term = math.sqrt(max(0.0, 1.0 - (10.0**ph_delta)))

    # 4. CO2 Inhibition Term: f(CO2) = max(0, 1 - k_CO2 * y_CO2)
    effective_co2_frac = co2_fraction
    if dissolved_co2_ppm is not None and dissolved_co2_ppm > 0:
        approx_henry_mg_l_atm = 2000.0
        effective_co2_frac = max(
            effective_co2_frac, dissolved_co2_ppm / approx_henry_mg_l_atm
        )

    co2_inhibition_raw = 1.0 - params.co2_sensitivity * effective_co2_frac
    co2_term = max(0.0, min(1.0, co2_inhibition_raw))

    # 5. Oxygen Term: f(O2)
    o2_term = 1.0
    if params.requires_o2:
        if o2_fraction < 0.01:
            msg = (
                f"Obligate aerobe requires O2 >= 1.0%, present O2 = "
                f"{o2_fraction * 100:.1f}%"
            )
            return MicrobialGrowthResult(
                organism=params.name,
                mu_max_per_day=0.0,
                mu_max_per_hour=0.0,
                sqrt_mu_max=0.0,
                generation_time_hours=float("inf"),
                temp_term=temp_term,
                aw_term=aw_term,
                ph_term=ph_term,
                co2_term=co2_term,
                o2_term=0.0,
                growth_possible=False,
                limiting_factor=msg,
            )
        if o2_fraction < 0.05:
            o2_term = math.sqrt(o2_fraction / 0.05)

    if params.anaerobic_only:
        if o2_fraction >= 0.02:
            msg = f"Obligate anaerobe inhibited by O2 >= 2%, got {o2_fraction*100:.1f}%"
            return MicrobialGrowthResult(
                organism=params.name,
                mu_max_per_day=0.0,
                mu_max_per_hour=0.0,
                sqrt_mu_max=0.0,
                generation_time_hours=float("inf"),
                temp_term=temp_term,
                aw_term=aw_term,
                ph_term=ph_term,
                co2_term=co2_term,
                o2_term=0.0,
                growth_possible=False,
                limiting_factor=msg,
            )
        if o2_fraction > 0.01:
            o2_term = (0.02 - o2_fraction) / 0.01

    sqrt_mu_max = temp_term * aw_term * ph_term * co2_term * o2_term
    mu_max_per_day = sqrt_mu_max**2.0
    mu_max_per_hour = mu_max_per_day / 24.0

    if mu_max_per_hour > 0:
        generation_time_hours = math.log(2.0) / mu_max_per_hour
    else:
        generation_time_hours = float("inf")

    return MicrobialGrowthResult(
        organism=params.name,
        mu_max_per_day=round(mu_max_per_day, 6),
        mu_max_per_hour=round(mu_max_per_hour, 6),
        sqrt_mu_max=round(sqrt_mu_max, 6),
        generation_time_hours=round(generation_time_hours, 2),
        temp_term=round(temp_term, 6),
        aw_term=round(aw_term, 6),
        ph_term=round(ph_term, 6),
        co2_term=round(co2_term, 6),
        o2_term=round(o2_term, 6),
        growth_possible=True,
        limiting_factor=None,
    )


# ---------------------------------------------------------------------------
# Shelf Life & Spoilage Prediction Model
# ---------------------------------------------------------------------------


class MicrobialShelfLifeResult(BaseModel):
    """Result of microbially-limited shelf-life prediction."""

    shelf_life_days: float = Field(
        ..., description="Time to microbial spoilage or limit in days"
    )
    limiting_organism: str = Field(
        ..., description="Organism causing earliest spoilage or safety limit"
    )
    growth_rate_per_day: float = Field(
        ..., description="Specific growth rate mu_max in 1/day"
    )
    lag_phase_days: float = Field(
        ..., description="Duration of physiological lag phase in days"
    )
    generation_time_hours: float = Field(
        ..., description="Cell doubling time in hours"
    )
    co2_inhibition_factor: float = Field(
        ..., description="CO2 term f(CO2) applied (1.0 = no inhibition)"
    )
    shelf_life_without_co2_days: float | None = Field(
        None,
        description="Shelf life if CO2 inhibition omitted (shows under-prediction)",
    )
    equation_id: str = Field(default=EQ_MICROBIAL_GROWTH)
    all_organism_results: dict[str, Any] = Field(default_factory=dict)
    inputs_used: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def time_to_spoilage(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    organism: str | OrganismParams | None = None,
    temperature_c: float | None = None,
    water_activity: float | None = None,
    ph: float | None = None,
    co2_fraction: float | None = None,
    o2_fraction: float | None = None,
    initial_count_log10: float | None = None,
    spoilage_threshold_log10: float | None = None,
) -> MicrobialShelfLifeResult:
    """
    Predict time to microbial spoilage including lag phase per Section 5.4:
        Time to spoilage = (log10 N_spoil − log10 N_0) / (μ_max / ln 10) + lag phase
    """
    notes: list[str] = []

    # 1. Resolve Commodity Profile
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if water_activity is None:
            aw_entry = p_dict.get("water_activity")
            if isinstance(aw_entry, dict):
                water_activity = aw_entry.get("value")
            elif isinstance(aw_entry, (int, float)):
                water_activity = float(aw_entry)
        if ph is None:
            ph_entry = p_dict.get("pH")
            if isinstance(ph_entry, dict):
                ph = ph_entry.get("value")
            elif isinstance(ph_entry, (int, float)):
                ph = float(ph_entry)

    aw_val = float(water_activity if water_activity is not None else 0.98)
    ph_val = float(ph if ph is not None else 6.0)

    # 2. Resolve Environment
    if environment is not None:
        e_dict = (
            environment if isinstance(environment, dict) else environment.model_dump()
        )
        if temperature_c is None:
            t_entry = e_dict.get("temperature")
            if isinstance(t_entry, dict):
                temperature_c = t_entry.get("value")
            elif isinstance(t_entry, (int, float)):
                temperature_c = float(t_entry)

    temp_val = float(temperature_c if temperature_c is not None else 4.0)

    # 3. Resolve Packaging Headspace Atmosphere
    if package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        if co2_fraction is None:
            co2_fraction = pkg_dict.get("headspace_co2_fraction") or pkg_dict.get(
                "target_co2"
            )
        if o2_fraction is None:
            o2_fraction = pkg_dict.get("headspace_o2_fraction") or pkg_dict.get(
                "target_o2"
            )

    co2_val = float(co2_fraction if co2_fraction is not None else 0.0)
    o2_val = float(o2_fraction if o2_fraction is not None else 0.209)

    # Organisms to evaluate
    eval_list: list[OrganismParams] = []
    if organism is not None:
        if isinstance(organism, str):
            eval_list.append(get_organism_params(organism))
        else:
            eval_list.append(organism)
    else:
        eval_list = list(COMBASE_ORGANISMS.values())

    all_results: dict[str, Any] = {}
    shortest_days = float("inf")
    limiting_org_name = eval_list[0].name
    limiting_growth_res: MicrobialGrowthResult | None = None
    limiting_lag_days = 0.0
    limiting_org_params: OrganismParams = eval_list[0]

    for org in eval_list:
        growth = ratkowsky_growth_rate(
            organism=org,
            temperature_c=temp_val,
            water_activity=aw_val,
            ph=ph_val,
            co2_fraction=co2_val,
            o2_fraction=o2_val,
        )

        n0 = initial_count_log10 if initial_count_log10 is not None else org.n_0_default
        nspoil = (
            spoilage_threshold_log10
            if spoilage_threshold_log10 is not None
            else org.n_spoil_default
        )
        delta_log = max(0.0, nspoil - n0)

        if not growth.growth_possible or growth.mu_max_per_day <= 0.0:
            spoil_days = float("inf")
            lag_days = float("inf")
        else:
            lag_days = org.h0_lag / growth.mu_max_per_day
            growth_days = delta_log / (growth.mu_max_per_day / math.log(10.0))
            spoil_days = lag_days + growth_days

        all_results[org.name] = {
            "mu_max_per_day": growth.mu_max_per_day,
            "generation_time_hours": growth.generation_time_hours,
            "lag_days": round(lag_days, 2) if math.isfinite(lag_days) else "inf",
            "spoilage_days": (
                round(spoil_days, 2) if math.isfinite(spoil_days) else "inf"
            ),
            "limiting_factor": growth.limiting_factor,
            "co2_inhibition_term": growth.co2_term,
        }

        if spoil_days < shortest_days:
            shortest_days = spoil_days
            limiting_org_name = org.name
            limiting_growth_res = growth
            limiting_lag_days = lag_days
            limiting_org_params = org

    if limiting_growth_res is None:
        limiting_growth_res = ratkowsky_growth_rate(
            organism=limiting_org_params,
            temperature_c=temp_val,
            water_activity=aw_val,
            ph=ph_val,
            co2_fraction=co2_val,
            o2_fraction=o2_val,
        )

    shelf_life_no_co2: float | None = None
    if co2_val > 0.0 and math.isfinite(shortest_days):
        growth_no_co2 = ratkowsky_growth_rate(
            organism=limiting_org_params,
            temperature_c=temp_val,
            water_activity=aw_val,
            ph=ph_val,
            co2_fraction=0.0,  # Air baseline
            o2_fraction=o2_val,
        )
        if growth_no_co2.growth_possible and growth_no_co2.mu_max_per_day > 0:
            n0 = (
                initial_count_log10
                if initial_count_log10 is not None
                else limiting_org_params.n_0_default
            )
            nspoil = (
                spoilage_threshold_log10
                if spoilage_threshold_log10 is not None
                else limiting_org_params.n_spoil_default
            )
            delta_log = max(0.0, nspoil - n0)
            lag_no_co2 = limiting_org_params.h0_lag / growth_no_co2.mu_max_per_day
            g_days = delta_log / (growth_no_co2.mu_max_per_day / math.log(10.0))
            shelf_life_no_co2 = round(lag_no_co2 + g_days, 2)

    notes.append(
        f"Limiting organism: {limiting_org_name} (shelf life: "
        f"{round(shortest_days, 1) if math.isfinite(shortest_days) else 'inf'} days)"
    )
    if co2_val > 0.0:
        notes.append(
            f"CO2 inhibition factor f(CO2) = {limiting_growth_res.co2_term:.2f} "
            f"at {co2_val * 100:.1f}% CO2"
        )
        if shelf_life_no_co2 is not None and shelf_life_no_co2 < shortest_days:
            notes.append(
                f"Omitting CO2 inhibition would under-predict MAP shelf life as "
                f"{shelf_life_no_co2:.1f} days vs actual {shortest_days:.1f} days"
            )

    return MicrobialShelfLifeResult(
        shelf_life_days=(
            round(shortest_days, 2) if math.isfinite(shortest_days) else float("inf")
        ),
        limiting_organism=limiting_org_name,
        growth_rate_per_day=limiting_growth_res.mu_max_per_day,
        lag_phase_days=(
            round(limiting_lag_days, 2)
            if math.isfinite(limiting_lag_days)
            else float("inf")
        ),
        generation_time_hours=limiting_growth_res.generation_time_hours,
        co2_inhibition_factor=limiting_growth_res.co2_term,
        shelf_life_without_co2_days=shelf_life_no_co2,
        equation_id=EQ_MICROBIAL_GROWTH,
        all_organism_results=all_results,
        inputs_used={
            "temperature_c": temp_val,
            "water_activity": aw_val,
            "ph": ph_val,
            "co2_fraction": co2_val,
            "o2_fraction": o2_val,
        },
        notes=notes,
    )
