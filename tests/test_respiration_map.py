"""
Unit and validation tests for respiration and MAP design models (Section 5.3).

Tests:
1. Fresh-cut pineapple validation test:
   - Initial respiration ~8.5 mL/kg/h.
   - Target OTR lands in 7,000 - 13,000 mL/(m2.day.atm) (published: 7,300 - 12,500).
   - Target CO2TR lands in 14,000 - 24,000 mL/(m2.day.atm) (published: 13,900 - 23,500).
2. Selectivity assertions:
   - Perforation selectivity is ~0.78 (D_CO2 / D_O2 = 0.160 / 0.205).
   - Polyolefin film selectivity is between 3 and 6.
3. Arrhenius temperature scaling & Q10 fallback with assumption logging.
4. State modifiers for cut, bruised, washed, cured, blanched returning ranges.
5. Selectivity classifier for FILM, PERFORATION, and IMPOSSIBLE.
6. Perforation design solving count given diameter, diameter given count, end-correction, rounding up.
7. Coupled steady-state in-pack equilibrium solver with scipy.optimize.brentq.
8. Non-negotiable hard safety clamps (O2 floor 2.0%, CO2 injury ceiling, structured NoSolution).
"""

import math
import pytest

from engine.models.map_design import (
    MIN_EQUILIBRIUM_O2_FLOOR,
    PERFORATION_SELECTIVITY,
    POLYOLEFIN_SELECTIVITY_RANGE,
    EquilibriumAtmosphereResult,
    NoSolution,
    SelectivityRecommendation,
    equilibrium_atmosphere,
    perforation_design,
    required_co2tr,
    required_otr,
    required_selectivity,
)
from engine.models.respiration import (
    apply_state_modifiers,
    rate_at_temperature,
)


# ---------------------------------------------------------------------------
# Test 1: Validation Anchor — Fresh-Cut Produce (Section 5.3)
# ---------------------------------------------------------------------------

def test_fresh_cut_pineapple_published_modelling_benchmark():
    """
    Validation test from BLUEPRINT.md Section 5.3:
    "model a fresh-cut product with initial respiration around 8.5 mL/kg/h.
    The solver should produce target O2 and CO2 transmission rates of the order
    of 7,000 to 13,000 and 14,000 to 24,000 mL/m2/day/atm respectively.
    Published fresh-cut pineapple modelling gives 7,300 to 12,500 and 13,900 to 23,500.
    Assert your result lands in that band."
    """
    respiration_rate = 8.5  # mL O2 / (kg · h)
    # Typical retail fresh-cut tray: 0.40 kg in 0.045 m2 (load density ~8.89 kg/m2)
    # Published fresh-cut pineapple MAP targets: ~3% to 4% O2, ~8% to 10% CO2
    mass_kg = 0.40
    area_m2 = 0.045
    y_out_o2 = 0.209
    y_in_o2 = 0.040  # 4% target internal O2
    y_in_co2 = 0.090  # 9% target internal CO2
    y_out_co2 = 0.0004

    # 1. Solve required OTR
    otr_res = required_otr(
        respiration_o2=respiration_rate,
        mass=mass_kg,
        area=area_m2,
        y_out=y_out_o2,
        y_in=y_in_o2,
    )
    otr_val = otr_res.required_otr

    # Assert OTR lands within 7,000 to 13,000 mL/(m2.day.atm)
    # (and within the published fresh-cut pineapple band 7,300 - 12,500)
    assert 7000.0 <= otr_val <= 13000.0, f"OTR {otr_val} not in [7000, 13000]"
    assert 7300.0 <= otr_val <= 12500.0, f"OTR {otr_val} not in published [7300, 12500]"

    # 2. Solve required CO2TR (assuming RQ = 1.0)
    co2tr_res = required_co2tr(
        respiration_co2=respiration_rate,
        mass=mass_kg,
        area=area_m2,
        y_in_co2=y_in_co2,
        y_out_co2=y_out_co2,
    )
    co2tr_val = co2tr_res.required_co2tr

    # Assert CO2TR lands within 14,000 to 24,000 mL/(m2.day.atm)
    # (and within the published fresh-cut pineapple band 13,900 - 23,500)
    assert 14000.0 <= co2tr_val <= 24000.0, f"CO2TR {co2tr_val} not in [14000, 24000]"
    assert 13900.0 <= co2tr_val <= 23500.0, f"CO2TR {co2tr_val} not in published [13900, 23500]"


# ---------------------------------------------------------------------------
# Test 2: Selectivity Ratios Assertion
# ---------------------------------------------------------------------------

def test_selectivity_ratios_assertion():
    """
    Assert:
    - Perforation selectivity is approximately 0.78 (D_CO2 / D_O2 = 0.160 / 0.205).
    - Polyolefin film selectivity is between 3 and 6.
    """
    # Perforation selectivity
    diffusivity_ratio = 0.160 / 0.205
    assert abs(PERFORATION_SELECTIVITY - diffusivity_ratio) < 1e-6
    assert round(PERFORATION_SELECTIVITY, 2) == 0.78

    # Polyolefin film selectivity bounds
    poly_min, poly_max = POLYOLEFIN_SELECTIVITY_RANGE
    assert poly_min == 3.0
    assert poly_max == 6.0


# ---------------------------------------------------------------------------
# Test 3: Respiration Temperature Scaling (Arrhenius & Q10 Fallback)
# ---------------------------------------------------------------------------

def test_arrhenius_respiration_scaling():
    """Arrhenius scaling with known activation energy Ea (RESP-01)."""
    rate_5c = 3.5  # potato at 5 C
    # Scaling to 25 C with Ea = 58 kJ/mol
    res = rate_at_temperature(rate_ref=rate_5c, temp_ref_c=5.0, temp_target_c=25.0, ea_kj_mol=58.0)
    assert res.equation_id == "RESP-01"
    assert res.model_used == "arrhenius"
    assert len(res.assumptions) == 0
    # Expected factor exp[(58/0.008314)*(1/278.15 - 1/298.15)] ≈ 5.16 => rate ≈ 18.06
    assert 17.0 <= res.rate <= 19.5


def test_q10_fallback_and_assumption_logging():
    """Q10 fallback when Ea is unknown, flagging default Q10=2.5 in assumptions (RESP-02)."""
    rate_5c = 10.0
    # Omitting Ea
    res = rate_at_temperature(rate_ref=rate_5c, temp_ref_c=5.0, temp_target_c=25.0)
    assert res.equation_id == "RESP-02"
    assert res.model_used == "q10_fallback"
    # Delta T = 20 C => 2 decades => factor 2.5^2 = 6.25 => rate = 62.5
    assert abs(res.rate - 62.5) < 1e-5
    # Must flag assumption
    assert any("Q10=2.5" in a for a in res.assumptions)


# ---------------------------------------------------------------------------
# Test 4: State Modifiers Return Ranges
# ---------------------------------------------------------------------------

def test_apply_state_modifiers_returns_ranges():
    """Verify multiplier ranges from Section 4.2: cut, bruised, washed, cured, blanched."""
    base_rate = 10.0

    # 1. Cut (wound response): x3 to x7
    res_cut = apply_state_modifiers(base_rate, "cut")
    assert (res_cut.rate_min, res_cut.rate_max) == (30.0, 70.0)
    # Unpackable as tuple
    r_min, r_max = res_cut
    assert (r_min, r_max) == (30.0, 70.0)

    # 2. Bruised: x1.3 to x2.0
    res_bruised = apply_state_modifiers(base_rate, "bruised")
    assert (res_bruised.rate_min, res_bruised.rate_max) == (13.0, 20.0)

    # 3. Washed: x1.0 to x1.0
    res_washed = apply_state_modifiers(base_rate, "washed")
    assert (res_washed.rate_min, res_washed.rate_max) == (10.0, 10.0)

    # 4. Cured: x0.6 to x0.9
    res_cured = apply_state_modifiers(base_rate, "cured")
    assert (res_cured.rate_min, res_cured.rate_max) == (6.0, 9.0)

    # 5. Blanched: x0.0 to x0.0 (respiration ceases)
    res_blanched = apply_state_modifiers(base_rate, "blanched")
    assert (res_blanched.rate_min, res_blanched.rate_max) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Test 5: Selectivity Classifier (FILM, PERFORATION, IMPOSSIBLE)
# ---------------------------------------------------------------------------

def test_selectivity_classification():
    """Test selectivity branch point: FILM, PERFORATION, or IMPOSSIBLE."""
    # Case A: beta ~ 4.0 => FILM
    res_film = required_selectivity(y_out_o2=0.209, y_in_o2=0.05, y_in_co2=0.04, y_out_co2=0.0004)
    # beta = (0.209 - 0.05) / (0.04 - 0.0004) = 0.159 / 0.0396 ≈ 4.015
    assert res_film.recommendation == SelectivityRecommendation.FILM
    assert 3.0 <= res_film.beta_required <= 6.0

    # Case B: beta ~ 1.0 => PERFORATION (e.g. high CO2 tolerant produce: target 3% O2, 18% CO2)
    res_perf = required_selectivity(y_out_o2=0.209, y_in_o2=0.03, y_in_co2=0.18, y_out_co2=0.0004)
    # beta = (0.209 - 0.03) / (0.18 - 0.0004) = 0.179 / 0.1796 ≈ 0.997
    assert res_perf.recommendation == SelectivityRecommendation.PERFORATION
    assert abs(res_perf.beta_required - 1.0) < 0.15

    # Case C: beta ~ 11.0 => IMPOSSIBLE (target 10% O2, 1% CO2)
    res_imp = required_selectivity(y_out_o2=0.209, y_in_o2=0.10, y_in_co2=0.01, y_out_co2=0.0004)
    assert res_imp.recommendation == SelectivityRecommendation.IMPOSSIBLE

    # Case D: Safety clamp violation (target O2 < 2%) => IMPOSSIBLE
    res_o2_floor = required_selectivity(y_out_o2=0.209, y_in_o2=0.015, y_in_co2=0.05)
    assert res_o2_floor.recommendation == SelectivityRecommendation.IMPOSSIBLE
    assert res_o2_floor.is_safe is False
    assert "2.0% safety floor" in res_o2_floor.reason

    # Case E: Safety clamp violation (target CO2 > injury ceiling) => IMPOSSIBLE
    res_co2_ceil = required_selectivity(
        y_out_o2=0.209, y_in_o2=0.05, y_in_co2=0.12, co2_injury_ceiling=0.10
    )
    assert res_co2_ceil.recommendation == SelectivityRecommendation.IMPOSSIBLE
    assert res_co2_ceil.is_safe is False
    assert "injury threshold" in res_co2_ceil.reason


# ---------------------------------------------------------------------------
# Test 6: Perforation Design (End-Correction & Rounding Up)
# ---------------------------------------------------------------------------

def test_perforation_design_sizing_and_inversion():
    """Perforation sizing using Fick with L_eff = L + 1.18r, rounding count UP."""
    respiration_rate = 8.5  # mL/kg.h
    mass = 0.40  # kg
    thickness_um = 30.0  # um
    hole_d_um = 100.0  # 100 um pore diameter

    res_holes = perforation_design(
        respiration_o2=respiration_rate,
        mass=mass,
        film_thickness_um=thickness_um,
        hole_diameter_um=hole_d_um,
        y_out=0.209,
        y_in=0.03,
    )

    # 1. Hole count is an integer and always rounded up
    assert isinstance(res_holes.hole_count, int)
    assert res_holes.hole_count >= 1

    # 2. Verify effective length with end correction L_eff = L + 1.18 * r = 30 + 1.18 * 50 = 89 um
    expected_l_eff = 30.0 + 1.18 * 50.0
    assert abs(res_holes.effective_length_um - expected_l_eff) < 1e-5

    # 3. Round-trip: given the computed hole_count, solving for diameter must return close to hole_d_um
    res_d = perforation_design(
        respiration_o2=respiration_rate,
        mass=mass,
        film_thickness_um=thickness_um,
        hole_count=res_holes.hole_count,
        y_out=0.209,
        y_in=0.03,
    )
    # Because hole_count was rounded up, the exact diameter required for that count is slightly <= 100 um
    assert res_d.hole_diameter_um <= hole_d_um + 1e-4
    assert res_d.hole_diameter_um >= hole_d_um * 0.70  # close match


# ---------------------------------------------------------------------------
# Test 7: Coupled Steady-State Atmosphere Solver (`brentq`)
# ---------------------------------------------------------------------------

def test_equilibrium_atmosphere_solver():
    """Verify coupled in-pack steady-state solver with scipy.optimize.brentq."""
    mass = 0.40
    area = 0.045
    resp_rate = 8.5  # mL/kg.h

    # Given a film matching the fresh-cut target (~10,000 mL/m2.day.atm OTR, ~20,000 CO2TR)
    film_otr = 10000.0
    film_co2tr = 20000.0

    res = equilibrium_atmosphere(
        film_otr=film_otr,
        film_co2tr=film_co2tr,
        pack_area_m2=area,
        mass_kg=mass,
        respiration_o2_ml_kg_h=resp_rate,
        rq=1.0,
        co2_injury_ceiling=0.15,
    )

    assert isinstance(res, EquilibriumAtmosphereResult)
    assert res.is_solvable is True
    assert res.is_safe is True
    # O2 must be inside safe envelope (between 2% floor and 20.9% air)
    assert 0.02 <= res.equilibrium_o2 <= 0.209
    # Verify exact steady state: Ingress(O2) == Consumption(O2)
    ingress_o2 = (film_otr * area / 24.0) * (0.209 - res.equilibrium_o2)
    consumption_o2 = mass * res.respiration_rate_o2_ml_kg_h
    assert abs(ingress_o2 - consumption_o2) < 1e-4


# ---------------------------------------------------------------------------
# Test 8: Non-Negotiable Hard Safety Clamps
# ---------------------------------------------------------------------------

def test_hard_clamps_emit_structured_no_solution():
    """
    Verify hard safety clamps:
    - O2 floor (< 2.0%) returns NoSolution with violation_type="O2_FLOOR".
    - CO2 ceiling exceeds injury threshold returns NoSolution with violation_type="CO2_CEILING".
    - Never clamped-and-silent!
    """
    mass = 1.0  # heavy pack
    area = 0.02  # tiny surface area
    resp_rate = 30.0  # very high respiration (e.g. spinach)

    # 1. Under-permeable film => severe hypoxia (O2 drops below 2.0%)
    low_barrier_otr = 50.0  # very low OTR for high-respiration produce
    res_hypoxia = equilibrium_atmosphere(
        film_otr=low_barrier_otr,
        film_co2tr=200.0,
        pack_area_m2=area,
        mass_kg=mass,
        respiration_o2_ml_kg_h=resp_rate,
        co2_injury_ceiling=0.20,
    )

    assert isinstance(res_hypoxia, NoSolution)
    assert res_hypoxia.is_solvable is False
    assert res_hypoxia.violation_type == "O2_FLOOR"
    assert "2.0%" in res_hypoxia.reason
    assert "Clostridium botulinum" in res_hypoxia.reason
    assert len(res_hypoxia.suggested_action) > 0

    # 2. High OTR but low CO2TR => CO2 exceeds commodity injury ceiling
    res_co2_injury = equilibrium_atmosphere(
        film_otr=50000.0,
        film_co2tr=1000.0,  # trap CO2
        pack_area_m2=0.05,
        mass_kg=0.5,
        respiration_o2_ml_kg_h=15.0,
        co2_injury_ceiling=0.05,  # strict 5% ceiling
    )

    assert isinstance(res_co2_injury, NoSolution)
    assert res_co2_injury.is_solvable is False
    assert res_co2_injury.violation_type == "CO2_CEILING"
    assert "exceeds the commodity injury ceiling" in res_co2_injury.reason
    assert len(res_co2_injury.suggested_action) > 0
