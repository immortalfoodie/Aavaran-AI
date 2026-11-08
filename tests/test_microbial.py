"""
Unit and Integration Tests for Microbial Growth and Shelf-Life Models.

Validates Section 5.4 of BLUEPRINT.md:
- Extended Ratkowsky / Belehrádek square-root growth model.
- ComBase-derived parameters for 4 organisms:
    * Pseudomonas spp.
    * Lactic acid bacteria (LAB)
    * Listeria monocytogenes
    * Clostridium botulinum (non-proteolytic type E, T_min = 3.3 °C)
- Bacteriostatic CO2 inhibition term f(CO2) preventing under-prediction
  of MAP shelf life.
- Physiological lag phase: t_lag = h0 / mu_max.
- Boundary cutoffs: temperature, water activity, and pH thresholds.
"""

import math

import pytest

from engine.models.microbial import (
    COMBASE_ORGANISMS,
    MicrobialShelfLifeResult,
    get_organism_params,
    ratkowsky_growth_rate,
    time_to_spoilage,
)
from engine.types import CommodityProfile, Environment, PackageCandidate, Provenance

# ===========================================================================
# 1. ComBase Organism Parameter Registry
# ===========================================================================


def test_combase_organisms_seeded_properly():
    """Validates 4 required organisms are present with ComBase parameters."""
    # 1. Pseudomonas spp.
    pseudo = get_organism_params("pseudomonas")
    assert pseudo.name == "Pseudomonas spp."
    assert pseudo.t_min_c == -3.0
    assert pseudo.aw_min == 0.96
    assert pseudo.ph_min == 5.0
    assert pseudo.co2_sensitivity > 0.50  # High CO2 sensitivity
    assert pseudo.requires_o2 is True

    # 2. Lactic acid bacteria
    lab = get_organism_params("lab")
    assert lab.name == "Lactic acid bacteria"
    assert lab.t_min_c == -1.0
    assert lab.aw_min == 0.93
    assert lab.ph_min == 4.2
    assert lab.co2_sensitivity < 0.25  # Capnophilic / tolerant in MAP

    # 3. Listeria monocytogenes
    listeria = get_organism_params("listeria")
    assert listeria.name == "Listeria monocytogenes"
    assert listeria.t_min_c == -0.4
    assert listeria.aw_min == 0.92
    assert listeria.ph_min == 4.4
    assert listeria.organism_type == "pathogen"

    # 4. Clostridium botulinum type E
    bot = get_organism_params("clostridium_botulinum_type_e")
    assert "Clostridium botulinum" in bot.name
    # CRITICAL: T_min must strictly be 3.3 °C per Blueprint spec
    assert bot.t_min_c == 3.3
    assert bot.aw_min == 0.97
    assert bot.ph_min == 5.0
    assert bot.anaerobic_only is True


def test_organism_alias_resolution():
    """Verifies that organism aliases resolve correctly and invalid names error."""
    assert get_organism_params("Pseudomonas spp.").name == "Pseudomonas spp."
    assert get_organism_params("LAB").name == "Lactic acid bacteria"
    assert get_organism_params("Listeria").name == "Listeria monocytogenes"
    assert get_organism_params("botulinum").t_min_c == 3.3

    with pytest.raises(KeyError):
        get_organism_params("non_existent_bacterium")


# ===========================================================================
# 2. Ratkowsky Square-Root Kinetics & Cutoffs
# ===========================================================================


def test_clostridium_botulinum_type_e_temperature_cutoff():
    """
    CRITICAL SPECIFICATION: Non-proteolytic type E C. botulinum minimum growth
    temperature is 3.3 °C.
    - At 3.0 °C (below 3.3 °C): mu_max == 0.0 (no growth).
    - At 4.0 °C (above 3.3 °C): mu_max > 0.0 (growth occurs in anaerobic conditions).
    """
    # At 3.0 °C in anaerobic conditions (O2 = 0.005)
    res_sub = ratkowsky_growth_rate(
        organism="clostridium_botulinum_type_e",
        temperature_c=3.0,
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.005,
    )
    assert res_sub.growth_possible is False
    assert res_sub.mu_max_per_day == 0.0
    assert "T_min" in str(res_sub.limiting_factor)

    # At 4.0 °C in anaerobic conditions
    res_sup = ratkowsky_growth_rate(
        organism="clostridium_botulinum_type_e",
        temperature_c=4.0,
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.005,
    )
    assert res_sup.growth_possible is True
    assert res_sup.mu_max_per_day > 0.0
    assert res_sup.limiting_factor is None


def test_pseudomonas_aerobic_requirement():
    """
    Pseudomonas spp. is an obligate aerobe.
    - Under aerobic air (O2 = 20.9%): grows rapidly.
    - Under anaerobic MAP (O2 = 0.5%): growth is halted (mu_max == 0.0).
    """
    res_air = ratkowsky_growth_rate(
        organism="pseudomonas",
        temperature_c=10.0,
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.209,
    )
    assert res_air.growth_possible is True
    assert res_air.mu_max_per_day > 0.5

    res_anaerobic = ratkowsky_growth_rate(
        organism="pseudomonas",
        temperature_c=10.0,
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.005,
    )
    assert res_anaerobic.growth_possible is False
    assert res_anaerobic.mu_max_per_day == 0.0
    assert "aerobe" in str(res_anaerobic.limiting_factor).lower()


def test_water_activity_and_ph_cutoffs():
    """Verifies that falling below aw_min or pH_min halts growth."""
    # Water activity below aw_min for Pseudomonas (aw_min = 0.96)
    res_dry = ratkowsky_growth_rate(
        organism="pseudomonas",
        temperature_c=15.0,
        water_activity=0.94,  # Below 0.96
        ph=6.5,
    )
    assert res_dry.growth_possible is False
    assert res_dry.mu_max_per_day == 0.0

    # pH below pH_min for Listeria (pH_min = 4.4)
    res_acid = ratkowsky_growth_rate(
        organism="listeria",
        temperature_c=15.0,
        water_activity=0.98,
        ph=4.2,  # Below 4.4
    )
    assert res_acid.growth_possible is False
    assert res_acid.mu_max_per_day == 0.0


# ===========================================================================
# 3. Bacteriostatic CO2 Inhibition in MAP
# ===========================================================================


def test_co2_inhibition_extends_shelf_life():
    """
    CRITICAL SPECIFICATION: CO2 in MAP is bacteriostatic.
    Including the CO2 inhibition term must reduce mu_max and extend shelf life.
    Omitting it systematically under-predicts MAP shelf life.
    """
    # Chilled product at 4 °C in Air (0% CO2)
    spoil_air = time_to_spoilage(
        organism="pseudomonas",
        temperature_c=4.0,
        water_activity=0.98,
        ph=6.5,
        co2_fraction=0.0,
        o2_fraction=0.209,
    )

    # Same product at 4 °C in MAP with 30% CO2 (O2 kept at 10% to isolate CO2 effect)
    spoil_map_co2 = time_to_spoilage(
        organism="pseudomonas",
        temperature_c=4.0,
        water_activity=0.98,
        ph=6.5,
        co2_fraction=0.30,
        o2_fraction=0.10,
    )

    # Specific growth rate must be lower in elevated CO2
    assert spoil_map_co2.growth_rate_per_day < spoil_air.growth_rate_per_day
    # Shelf life must be longer in MAP with CO2
    assert spoil_map_co2.shelf_life_days > spoil_air.shelf_life_days
    # CO2 inhibition factor must be < 1.0
    assert spoil_map_co2.co2_inhibition_factor < 1.0

    # Check that shelf_life_without_co2_days is reported and
    # demonstrates under-prediction when CO2 is omitted
    assert spoil_map_co2.shelf_life_without_co2_days is not None
    assert spoil_map_co2.shelf_life_without_co2_days < spoil_map_co2.shelf_life_days


# ===========================================================================
# 4. Lag Phase and Time to Spoilage Equation
# ===========================================================================


def test_lag_phase_calculation():
    """
    Verifies physiological lag phase: t_lag = h0 / mu_max.
    Also verifies logarithmic growth phase: delta_log / (mu_max / ln 10).
    Total time to spoilage = t_lag + t_growth.
    """
    res = time_to_spoilage(
        organism="lactic_acid_bacteria",
        temperature_c=8.0,
        water_activity=0.97,
        ph=5.8,
        initial_count_log10=2.0,
        spoilage_threshold_log10=7.0,
    )
    assert res.shelf_life_days > 0.0
    assert res.lag_phase_days > 0.0
    assert res.shelf_life_days > res.lag_phase_days

    # Recompute manually to verify mathematical exactness
    mu = res.growth_rate_per_day
    expected_lag = 2.0 / mu  # h0 = 2.0 for LAB
    expected_growth = (7.0 - 2.0) / (mu / math.log(10.0))
    expected_total = expected_lag + expected_growth

    assert pytest.approx(res.lag_phase_days, rel=1e-2) == expected_lag
    assert pytest.approx(res.shelf_life_days, rel=1e-2) == expected_total


def test_time_to_spoilage_with_profile_and_package():
    """Verifies integration with CommodityProfile and PackageCandidate models."""
    profile = CommodityProfile(
        commodity_id="veg.potato.solanum_tuberosum",
        names={"en": ["potato"]},
        group="root_tuber",
        commodity_class="high_moisture_starchy",
        water_activity=Provenance(value=0.98),
        pH=Provenance(value=6.1),
    )
    environment = Environment(
        temperature=Provenance(value=4.0, unit="degC"),
        relative_humidity=Provenance(value=90.0, unit="%"),
        duration=Provenance(value=10.0, unit="days"),
    )
    package = PackageCandidate(
        layer_stack=["LDPE"],
        gauge_per_layer=[50.0],
    )

    result = time_to_spoilage(
        profile=profile,
        environment=environment,
        package=package,
    )
    assert isinstance(result, MicrobialShelfLifeResult)
    assert result.shelf_life_days > 0.0
    assert result.limiting_organism in [org.name for org in COMBASE_ORGANISMS.values()]
    assert result.equation_id == "MIC-01"
