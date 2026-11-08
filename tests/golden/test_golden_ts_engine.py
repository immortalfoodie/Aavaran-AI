"""
Verification script for shared golden model test file.
Asserts that Python engine models reproduce tests/golden/golden_models.json values.
"""

import json
from pathlib import Path
import pytest

from engine.models.moisture import shelf_life_moisture_limited, required_wvtr, LinearIsotherm, GABIsotherm
from engine.models.oxidation import shelf_life_oxidation_limited
from engine.models.respiration import rate_at_temperature
from engine.models.map_design import perforation_design
from engine.models.microbial import ratkowsky_growth_rate
from engine.models.safety import botulinum_gate, histamine_gate, fresh_cut_gate

GOLDEN_PATH = Path(__file__).parent / "golden_models.json"


def test_python_models_match_golden_file():
    assert GOLDEN_PATH.exists(), f"Golden benchmark file not found at {GOLDEN_PATH}"
    with open(GOLDEN_PATH, "r") as f:
        golden = json.load(f)

    # 1. Moisture
    iso = LinearIsotherm(0.45, 0.01)
    m1 = shelf_life_moisture_limited(
        wvtr=1.2,
        pack_area_m2=0.05,
        dry_solids_kg=0.2,
        temperature_c=30.0,
        relative_humidity_pct=75.0,
        aw_initial=0.20,
        aw_crit=0.45,
        isotherm=iso,
    )
    assert abs(m1.shelf_life_days - golden["moisture"]["shelf_life_days"]) < 0.01

    m2 = required_wvtr(
        target_days=180.0,
        pack_area=0.05,
        dry_solids=0.2,
        temperature_c=30.0,
        relative_humidity_pct=75.0,
        aw_initial=0.20,
        aw_crit=0.45,
    )
    assert abs(m2.required_wvtr - golden["moisture"]["required_wvtr"]) < 0.01

    gab = GABIsotherm(m0=0.04, c_g=15.0, k=0.85)
    assert abs(gab.moisture_at_aw(0.4) - golden["moisture"]["gab_moisture_at_aw_0_4"]) < 0.001

    # 2. Oxidation
    ox = shelf_life_oxidation_limited(
        otr=2.0,
        pack_area_m2=0.05,
        product_mass_kg=0.25,
        q_budget_mg_per_kg=15.0,
        headspace_volume_cc=50.0,
        headspace_o2_fraction=0.02,
        delta_p_atm=0.209,
    )
    assert abs(ox.shelf_life_days - golden["oxidation"]["shelf_life_days"]) < 0.01

    # 3. Respiration
    r_arr = rate_at_temperature(rate_ref=12.0, temp_ref_c=5.0, temp_target_c=25.0, ea_kj_mol=55.0)
    assert abs(r_arr.rate - golden["respiration"]["arrhenius_rate"]) < 0.01

    r_q10 = rate_at_temperature(rate_ref=12.0, temp_ref_c=5.0, temp_target_c=25.0, q10=2.5)
    assert abs(r_q10.rate - golden["respiration"]["q10_rate"]) < 0.01

    # 4. MAP Perforation
    perf = perforation_design(
        respiration_o2=45.0,
        mass=1.0,
        film_thickness_um=30.0,
        hole_diameter_um=100.0,
        y_out=0.209,
        y_in=0.05,
        temperature_c=20.0,
    )
    assert perf.hole_count == golden["map"]["hole_count"]

    # 5. Microbial
    growth = ratkowsky_growth_rate(
        organism="pseudomonas",
        temperature_c=25.0,
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.209,
    )
    assert abs(growth.mu_max_per_day - golden["microbial"]["mu_max_per_day"]) < 0.01

    # 6. Safety
    b_gate = botulinum_gate(water_activity=0.98, ph=6.1, o2_fraction=0.01, max_temperature_c=30.0)
    assert (b_gate.status.value == "BLOCK") == golden["safety"]["botulinum_blocked"]

    h_gate = histamine_gate(profile={"commodity_id": "fish.tuna.albacore"}, max_temperature_c=18.0)
    assert (h_gate.status.value == "BLOCK") == golden["safety"]["histamine_blocked"]

    fc_gate = fresh_cut_gate(state_modifiers={"cut": True}, max_temperature_c=30.0, o2_fraction=0.01)
    assert (fc_gate.status.value == "BLOCK") == golden["safety"]["fresh_cut_blocked"]
