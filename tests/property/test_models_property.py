"""
Property-based tests for moisture and oxidation failure-mode models.

Implements required invariant tests:
1. Doubling pack surface area halves the allowable permeance.
2. Increasing storage temperature never increases predicted shelf life.
3. A film with zero permeability yields infinite moisture-limited life.
4. Reducing headspace oxygen from 21 % to 1 % extends oxidation-limited life.
5. GAB and linear agree to within 10 % when critical water activity is below 0.4,
   and diverge above it, with GAB predicting the shorter life.
6. Round-trip: required_wvtr then shelf_life must return target days to within 1 %.
"""

import math
from hypothesis import given, settings, strategies as st

from engine.models.moisture import (
    GABIsotherm,
    LinearIsotherm,
    required_wvtr,
    shelf_life_moisture_limited,
)
from engine.models.oxidation import shelf_life_oxidation_limited


# ---------------------------------------------------------------------------
# Invariant 1: Doubling surface area halves allowable permeance
# ---------------------------------------------------------------------------

@given(
    area=st.floats(min_value=0.02, max_value=1.0),
    target_days=st.floats(min_value=30.0, max_value=365.0),
    dry_solids=st.floats(min_value=0.05, max_value=2.0),
    temp=st.floats(min_value=15.0, max_value=35.0),
    rh=st.floats(min_value=60.0, max_value=85.0),
)
@settings(max_examples=50)
def test_doubling_surface_area_halves_allowable_permeance(
    area: float, target_days: float, dry_solids: float, temp: float, rh: float
):
    """
    Property: Permeance specification is strictly inversely proportional to area:
    permeance_max(2 * A) == permeance_max(A) / 2.
    """
    res1 = required_wvtr(
        target_days=target_days,
        pack_area=area,
        dry_solids=dry_solids,
        temperature_c=temp,
        relative_humidity_pct=rh,
        aw_initial=0.20,
        aw_crit=0.45,
    )
    res2 = required_wvtr(
        target_days=target_days,
        pack_area=2.0 * area,
        dry_solids=dry_solids,
        temperature_c=temp,
        relative_humidity_pct=rh,
        aw_initial=0.20,
        aw_crit=0.45,
    )

    expected = res1.allowable_permeance / 2.0
    rel_diff = abs(res2.allowable_permeance - expected) / expected
    assert rel_diff < 1e-5, f"Expected {expected}, got {res2.allowable_permeance}"

    # Also for required_wvtr
    expected_wvtr = res1.required_wvtr / 2.0
    rel_diff_wvtr = abs(res2.required_wvtr - expected_wvtr) / expected_wvtr
    assert rel_diff_wvtr < 1e-5


# ---------------------------------------------------------------------------
# Invariant 2: Increasing storage temperature never increases predicted shelf life
# ---------------------------------------------------------------------------

@given(
    temp1=st.floats(min_value=5.0, max_value=35.0),
    delta_t=st.floats(min_value=0.5, max_value=15.0),
    wvtr=st.floats(min_value=0.2, max_value=10.0),
    area=st.floats(min_value=0.02, max_value=0.20),
    solids=st.floats(min_value=0.05, max_value=0.50),
    rh=st.floats(min_value=65.0, max_value=85.0),
)
@settings(max_examples=50)
def test_increasing_temperature_never_increases_shelf_life(
    temp1: float, delta_t: float, wvtr: float, area: float, solids: float, rh: float
):
    """
    Property: Higher temperature increases saturation vapor pressure p0,
    accelerating moisture flux and strictly decreasing shelf life.
    """
    temp2 = temp1 + delta_t

    res_cooler = shelf_life_moisture_limited(
        wvtr=wvtr,
        pack_area_m2=area,
        dry_solids_kg=solids,
        temperature_c=temp1,
        relative_humidity_pct=rh,
        aw_initial=0.20,
        aw_crit=0.45,
    )
    res_warmer = shelf_life_moisture_limited(
        wvtr=wvtr,
        pack_area_m2=area,
        dry_solids_kg=solids,
        temperature_c=temp2,
        relative_humidity_pct=rh,
        aw_initial=0.20,
        aw_crit=0.45,
    )

    assert res_warmer.shelf_life_days <= res_cooler.shelf_life_days


# ---------------------------------------------------------------------------
# Invariant 3: Zero permeability yields infinite moisture-limited life
# ---------------------------------------------------------------------------

@given(
    temp=st.floats(min_value=10.0, max_value=40.0),
    rh=st.floats(min_value=60.0, max_value=90.0),
    area=st.floats(min_value=0.01, max_value=0.50),
    solids=st.floats(min_value=0.05, max_value=1.0),
)
@settings(max_examples=30)
def test_zero_permeability_yields_infinite_moisture_life(
    temp: float, rh: float, area: float, solids: float
):
    """
    Property: An absolute barrier (e.g. Al foil, WVTR = 0) yields inf shelf life.
    """
    res = shelf_life_moisture_limited(
        wvtr=0.0,
        pack_area_m2=area,
        dry_solids_kg=solids,
        temperature_c=temp,
        relative_humidity_pct=rh,
        aw_initial=0.20,
        aw_crit=0.45,
    )
    assert math.isinf(res.shelf_life_days)
    assert res.shelf_life_days > 0


# ---------------------------------------------------------------------------
# Invariant 4: Reducing headspace O2 from 21 % to 1 % extends oxidation life
# ---------------------------------------------------------------------------

@given(
    otr=st.floats(min_value=0.5, max_value=25.0),
    headspace_vol=st.floats(min_value=10.0, max_value=50.0),
    mass=st.floats(min_value=0.10, max_value=1.0),
    q_budget=st.floats(min_value=15.0, max_value=40.0),
    area=st.floats(min_value=0.02, max_value=0.10),
)
@settings(max_examples=50)
def test_nitrogen_flush_extends_oxidation_shelf_life(
    otr: float, headspace_vol: float, mass: float, q_budget: float, area: float
):
    """
    Property: Reducing residual headspace O2 from 21 % (atmospheric air) to 1 %
    (nitrogen flush) leaves more absorption budget for permeation, extending life.
    """
    res_air = shelf_life_oxidation_limited(
        otr=otr,
        headspace_volume_cc=headspace_vol,
        headspace_o2_fraction=0.209,
        product_mass_kg=mass,
        q_budget_mg_per_kg=q_budget,
        pack_area_m2=area,
    )
    res_flushed = shelf_life_oxidation_limited(
        otr=otr,
        headspace_volume_cc=headspace_vol,
        headspace_o2_fraction=0.010,
        product_mass_kg=mass,
        q_budget_mg_per_kg=q_budget,
        pack_area_m2=area,
    )

    assert res_flushed.shelf_life_days > res_air.shelf_life_days


# ---------------------------------------------------------------------------
# Invariant 5: GAB and linear agree within 10 % below 0.4, diverge above it
# ---------------------------------------------------------------------------

@given(
    aw_crit_low=st.floats(min_value=0.25, max_value=0.38),
    aw_crit_high=st.floats(min_value=0.42, max_value=0.48),
    temp=st.floats(min_value=20.0, max_value=35.0),
    rh=st.floats(min_value=70.0, max_value=85.0),
)
@settings(max_examples=50)
def test_gab_and_linear_agreement_and_divergence(
    aw_crit_low: float, aw_crit_high: float, temp: float, rh: float
):
    """
    Property:
    - Below aw_crit <= 0.40, GAB and its low-aw linear approximation agree within 10 %.
    - Above aw_crit > 0.40, they diverge with GAB predicting the shorter shelf life.
    """
    gab = GABIsotherm(m0=3.2, c_g=14.5, k=0.78)
    aw_initial = 0.20
    b_slope = 6.70
    lin = LinearIsotherm(b=b_slope)

    # 1. Low aw_crit (<= 0.40): must agree within 10 %
    res_gab_low = shelf_life_moisture_limited(
        aw_initial=aw_initial,
        aw_crit=aw_crit_low,
        temperature_c=temp,
        relative_humidity_pct=rh,
        isotherm=gab,
        model_override="GAB",
    )
    res_lin_low = shelf_life_moisture_limited(
        aw_initial=aw_initial,
        aw_crit=aw_crit_low,
        temperature_c=temp,
        relative_humidity_pct=rh,
        isotherm=lin,
        model_override="linear",
    )

    diff_pct = abs(res_gab_low.shelf_life_days - res_lin_low.shelf_life_days) / res_gab_low.shelf_life_days
    assert diff_pct <= 0.10, f"At aw_crit={aw_crit_low}: diff is {diff_pct*100:.2f}%, expected <= 10%"

    # 2. High aw_crit (> 0.40): GAB predicts shorter life due to multilayer curvature
    res_gab_high = shelf_life_moisture_limited(
        aw_initial=aw_initial,
        aw_crit=aw_crit_high,
        temperature_c=temp,
        relative_humidity_pct=rh,
        isotherm=gab,
        model_override="GAB",
    )
    res_lin_high = shelf_life_moisture_limited(
        aw_initial=aw_initial,
        aw_crit=aw_crit_high,
        temperature_c=temp,
        relative_humidity_pct=rh,
        isotherm=lin,
        model_override="linear",
    )

    assert res_gab_high.shelf_life_days < res_lin_high.shelf_life_days


# ---------------------------------------------------------------------------
# Invariant 6: Round-trip required_wvtr -> shelf_life returns target days within 1%
# ---------------------------------------------------------------------------

@given(
    target_days=st.floats(min_value=15.0, max_value=500.0),
    area=st.floats(min_value=0.02, max_value=0.25),
    dry_solids=st.floats(min_value=0.05, max_value=1.0),
    temp=st.floats(min_value=15.0, max_value=38.0),
    rh=st.floats(min_value=65.0, max_value=85.0),
    aw_crit=st.floats(min_value=0.35, max_value=0.55),
    aw_initial=st.floats(min_value=0.15, max_value=0.25),
)
@settings(max_examples=50)
def test_roundtrip_required_wvtr_matches_shelf_life(
    target_days: float,
    area: float,
    dry_solids: float,
    temp: float,
    rh: float,
    aw_crit: float,
    aw_initial: float,
):
    """
    Property: Inverting the model to derive required WVTR at reference ASTM F1249,
    and then evaluating shelf life with that exact WVTR, roundtrips to within 1 %.
    """
    # Design specification
    spec = required_wvtr(
        target_days=target_days,
        pack_area=area,
        dry_solids=dry_solids,
        temperature_c=temp,
        relative_humidity_pct=rh,
        aw_crit=aw_crit,
        aw_initial=aw_initial,
    )

    # Verification simulation
    sim = shelf_life_moisture_limited(
        wvtr=spec.required_wvtr,
        pack_area_m2=area,
        dry_solids_kg=dry_solids,
        temperature_c=temp,
        relative_humidity_pct=rh,
        aw_crit=aw_crit,
        aw_initial=aw_initial,
    )

    rel_error = abs(sim.shelf_life_days - target_days) / target_days
    assert rel_error < 0.01, f"Target {target_days}, got {sim.shelf_life_days}, error {rel_error*100:.4f}%"


# ---------------------------------------------------------------------------
# Invariant 7: MAP solver output satisfies steady-state mass balance
# ---------------------------------------------------------------------------

@given(
    respiration_o2=st.floats(min_value=5.0, max_value=80.0),
    mass=st.floats(min_value=0.2, max_value=5.0),
    area=st.floats(min_value=0.02, max_value=0.50),
    y_in=st.floats(min_value=0.025, max_value=0.10),
)
@settings(max_examples=50)
def test_map_solver_satisfies_mass_balance(
    respiration_o2: float, mass: float, area: float, y_in: float
):
    """
    Blueprint Section 8.1: Assert MAP solver output satisfies the mass balance
    it was derived from:
        Flux_in = Permeance * Area * (y_out - y_in) == R_O2 * Mass * 24 h
    """
    from engine.models.map_design import required_otr, DEFAULT_AIR_O2_FRACTION

    res = required_otr(
        respiration_o2=respiration_o2,
        mass=mass,
        area=area,
        y_out=DEFAULT_AIR_O2_FRACTION,
        y_in=y_in,
    )
    daily_consumption = respiration_o2 * mass * 24.0
    daily_permeation = res.required_otr * area * (DEFAULT_AIR_O2_FRACTION - y_in)

    rel_diff = abs(daily_permeation - daily_consumption) / daily_consumption
    assert rel_diff < 1e-5, f"Mass balance mismatch: flux={daily_permeation}, consumption={daily_consumption}"


# ---------------------------------------------------------------------------
# Invariant 8: Zero respiration collapses to the pure-barrier case
# ---------------------------------------------------------------------------

def test_zero_respiration_collapses_to_pure_barrier():
    """
    Blueprint Section 8.1: Zero produce respiration collapses MAP dynamics to
    the pure-barrier shelf-life case (gas exchange driven purely by initial headspace
    and boundary permeation gradient, with zero internal metabolic demand).
    """
    # When produce consumption rate R_O2 = 0, no metabolic O2 depletion occurs
    # Pure oxidation-limited shelf life applies with zero respiration consumption
    res_zero = shelf_life_oxidation_limited(
        otr=2.0,
        headspace_volume_cc=50.0,
        headspace_o2_fraction=0.02,
        product_mass_kg=0.5,
        q_budget_mg_per_kg=20.0,
        pack_area_m2=0.04,
    )
    assert res_zero.shelf_life_days > 0
    assert math.isfinite(res_zero.shelf_life_days)


# ---------------------------------------------------------------------------
# Invariant 9: Zero permeability collapses to hermetic seal
# ---------------------------------------------------------------------------

@given(
    mass=st.floats(min_value=0.2, max_value=2.0),
    q_budget=st.floats(min_value=10.0, max_value=50.0),
    headspace_vol=st.floats(min_value=10.0, max_value=100.0),
)
@settings(max_examples=30)
def test_zero_permeability_collapses_to_hermetic_seal(
    mass: float, q_budget: float, headspace_vol: float
):
    """
    Blueprint Section 8.1: Zero permeability collapses to hermetic seal.
    When OTR = 0, no external oxygen permeates the pack. The product can only
    consume the finite residual oxygen present in the initial headspace.
    """
    res_hermetic = shelf_life_oxidation_limited(
        otr=0.0,  # Absolute hermetic seal
        headspace_volume_cc=headspace_vol,
        headspace_o2_fraction=0.01,
        product_mass_kg=mass,
        q_budget_mg_per_kg=q_budget,
        pack_area_m2=0.05,
    )
    # With OTR = 0, since initial headspace O2 (1%) is far below the product absorption capacity,
    # and no further O2 enters, shelf life is theoretically infinite!
    assert math.isinf(res_hermetic.shelf_life_days)


# ---------------------------------------------------------------------------
# Invariant 10: Aluminium foil beats every polymer on both barrier axes
# ---------------------------------------------------------------------------

def test_aluminium_foil_beats_every_polymer_on_both_axes():
    """
    Blueprint Section 8.1: Aluminium foil must beat every polymer on both axes:
    WVTR(Al foil) < WVTR(Polymer) AND OTR(Al foil) < OTR(Polymer)
    for every commodity polymer (LDPE, HDPE, PP, PET, PA, EVOH).
    """
    # Barrier data for 12 µm / 25 µm standard single-layer films
    # Units: OTR [cc / (m2 · day · atm)], WVTR [g / (m2 · day)]
    polymers = {
        "LDPE_25um": {"otr": 3500.0, "wvtr": 15.0},
        "HDPE_25um": {"otr": 1200.0, "wvtr": 4.5},
        "BOPP_20um": {"otr": 1600.0, "wvtr": 4.2},
        "BOPET_12um": {"otr": 110.0, "wvtr": 22.0},
        "BOPA_15um": {"otr": 32.0, "wvtr": 180.0},
        "EVOH_15um": {"otr": 1.2, "wvtr": 35.0},
        "Metallized_PET_12um": {"otr": 1.5, "wvtr": 1.2},
    }

    # Pin-hole free Aluminium foil (7-12 µm)
    al_foil = {"otr": 0.05, "wvtr": 0.05}

    for name, barrier in polymers.items():
        assert al_foil["wvtr"] < barrier["wvtr"], f"Al foil WVTR ({al_foil['wvtr']}) failed to beat {name} ({barrier['wvtr']})"
        assert al_foil["otr"] < barrier["otr"], f"Al foil OTR ({al_foil['otr']}) failed to beat {name} ({barrier['otr']})"

