"""
Unit, integration, and validation tests for Aavaran packaging matcher engine (engine/matcher/).

Tests:
1. Section 4.4 Worked Example B (Besan namkeen across Maharashtra):
   - Ranks mono-material BOPP/VMBOPP/CPP (Cat II) above PET/VMPET/LLDPE (Cat III).
   - Verifies mono-material PP meets 6-month target with margin at lower cost.
   - Asserts ordering (BOPP/VMBOPP/CPP > PET/VMPET/LLDPE).
   - Asserts explanation explicitly mentions the EPR category difference.
2. Regime Branching:
   - Verifies respiring produce (tomato/greens) branches to MAP designer.
   - Verifies non-respiring foods (namkeen/powders) branch to barrier design.
   - Verifies blanched produce switches to barrier regime.
3. Mechanical, Thermal, and Optical Requirement Derivations:
   - Pack mass, drop height, stack height scale thickness and seal strength.
   - Retort sets service temperature to 121 °C.
   - Light sensitivity sets light_barrier_od.
4. Hard Constraint Filters:
   - Rejects LLDPE sealant under retort (121 °C).
   - Rejects foil and metallisation under metal detection.
   - Rejects solid foil under microwave reheating.
   - Rejects machine incompatibility with user filling line.
5. Scorer & User Modes:
   - Kisan mode weights cost & availability heavily.
   - Business mode balances cost against shelf life.
   - Expert mode applies configurable weight sliders.
   - Returns at least three options.
   - Always includes at least one lower-environmental-impact candidate.
6. Pareto Frontier:
   - Correct 3D non-dominated frontier across cost, shelf life, and recyclability.
   - Emits UI chart series ready for graphing.
"""

import pytest

from engine.matcher import (
    FilterVerdict,
    compute_pareto_frontier,
    derive,
    filter_candidate,
    filter_candidates,
    is_respiring_produce,
    match_packaging,
    score_candidates,
)
from engine.matcher.score import compute_sustainability_score
from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    PackGeometry,
    Provenance,
    RequirementVector,
)
from kb.loaders import load_kb


# ---------------------------------------------------------------------------
# Test 1: Section 4.4 Worked Example B — Besan Namkeen Benchmark
# ---------------------------------------------------------------------------

def test_besan_namkeen_section_4_4_ranking_and_epr_explanation():
    """
    Validation Test from BLUEPRINT.md Section 4.4:
    "For the besan namkeen case in section 4.4 of BLUEPRINT.md, the
    matcher must rank a mono-material BOPP/VMBOPP/CPP structure above a
    PET/VMPET/LLDPE one, on the grounds that it meets the six-month target
    with margin at lower cost and in a lower EPR category. Assert the ordering
    and assert the explanation mentions the EPR category difference."
    """
    kb = load_kb()
    namkeen = kb.commodities["processed.besan_namkeen.fried_snack"]

    # Storage in Maharashtra ambient (30 °C, 75 % RH) for 6 months (180 days)
    env = {
        "temperature": {"value": 30.0, "unit": "degC"},
        "relative_humidity": {"value": 75.0, "unit": "%"},
        "duration": {"value": 180.0, "unit": "days"},
    }
    geom = PackGeometry(
        pack_area_m2=0.055,
        product_mass_kg=0.10,
        headspace_volume_cc=50.0,
        headspace_o2_fraction=0.01,  # N2 flush
    )

    # Run end-to-end matching in Business Mode
    output = match_packaging(
        profile=namkeen,
        environment=env,
        target_shelf_life=180.0,
        pack_geometry=geom,
        mode="business",
    )

    ranked_options = output.match_result.ranked_options
    assert len(ranked_options) >= 3, "Matcher must return at least three options"

    # Identify ranks of the target structures
    id_to_rank = {opt.candidate.id: opt.rank for opt in ranked_options}
    id_to_opt = {opt.candidate.id: opt for opt in ranked_options}

    assert "struct_bopp20_vmbopp18_cpp40" in id_to_rank, "Mono-PP structure must be present"
    assert "struct_pet12_vmpet12_lldpe50" in id_to_rank, "PET/VMPET/LLDPE structure must be present"

    rank_mono_pp = id_to_rank["struct_bopp20_vmbopp18_cpp40"]
    rank_pet_vmpet = id_to_rank["struct_pet12_vmpet12_lldpe50"]

    # 1. Assert ordering: mono-material PP must be ranked above PET/VMPET/LLDPE
    assert rank_mono_pp < rank_pet_vmpet, (
        f"Mono-material PP rank ({rank_mono_pp}) must be strictly higher than "
        f"PET/VMPET/LLDPE rank ({rank_pet_vmpet})"
    )
    assert rank_mono_pp == 1, f"Mono-material PP should be top recommendation (Rank 1), got {rank_mono_pp}"

    opt_mono_pp = id_to_opt["struct_bopp20_vmbopp18_cpp40"]
    opt_pet_vmpet = id_to_opt["struct_pet12_vmpet12_lldpe50"]

    # 2. Assert cost: mono-material PP is cheaper (~17% lower cost)
    assert opt_mono_pp.cost_per_pack_inr < opt_pet_vmpet.cost_per_pack_inr
    assert opt_mono_pp.cost_per_pack_inr == 1.75
    assert opt_pet_vmpet.cost_per_pack_inr == 2.10

    # 3. Assert EPR Category difference
    assert opt_mono_pp.epr_category == "Cat II"
    assert opt_pet_vmpet.epr_category == "Cat III"

    # 4. Assert explanation mentions the EPR category difference
    combined_explanations = (
        opt_mono_pp.trade_off_explanation + " " + opt_pet_vmpet.trade_off_explanation
    )
    assert any(
        term in combined_explanations for term in ["Cat II", "Category II", "EPR", "mono-material"]
    ), f"Explanation must mention EPR category difference, got: {combined_explanations}"
    assert "Cat III" in combined_explanations or "Category III" in combined_explanations


# ---------------------------------------------------------------------------
# Test 2: Regime Branching (Respiring Produce vs Non-Respiring Barrier)
# ---------------------------------------------------------------------------

def test_regime_branching_respiring_vs_barrier():
    """
    Branch on regime first: respiring produce versus non-respiring.
    Barrier pack has OTR < ~70, while produce passive MAP sits in 1,085 to 7,000 range.
    Must not share a code path.
    """
    env = {
        "temperature": {"value": 10.0},
        "relative_humidity": {"value": 90.0},
        "duration": {"value": 10.0},
    }
    geom = PackGeometry(pack_area_m2=0.045, product_mass_kg=0.40)

    # 1. Respiring fresh produce (Tomato)
    tomato = {
        "commodity_id": "veg.tomato.fresh",
        "group": "fruit",
        "class": "fresh_produce",
        "respiration_model": "arrhenius",
        "respiration_ref_rate": {"value": 12.0},
        "respiration_ref_t_c": {"value": 10.0},
        "water_activity": {"value": 0.98},
    }
    assert is_respiring_produce(tomato) is True

    req_tomato = derive(profile=tomato, environment=env, target_shelf_life=10.0, pack_geometry=geom)
    assert req_tomato.regime == "respiring_produce"
    assert req_tomato.map_required is True
    assert req_tomato.min_otr is not None
    # MAP produce OTR sits comfortably in the 1,000 to 15,000 range
    assert req_tomato.min_otr > 1000.0

    # 2. Non-respiring processed dry food
    biscuit = {
        "commodity_id": "processed.biscuit",
        "group": "bakery",
        "class": "dry_baked",
        "water_activity": {"value": 0.20},
        "aw_crit": 0.40,
    }
    assert is_respiring_produce(biscuit) is False

    req_biscuit = derive(profile=biscuit, environment=env, target_shelf_life=180.0, pack_geometry=geom)
    assert req_biscuit.regime == "non_respiring_barrier"
    assert req_biscuit.map_required is False
    assert req_biscuit.max_wvtr is not None
    # Barrier pack OTR is <= 70
    assert req_biscuit.max_otr <= 70.0

    # 3. Blanched vegetable (enzymes inactivated, respiring extinguished)
    blanched_veg = {
        "commodity_id": "veg.spinach.blanched",
        "group": "vegetable",
        "state_modifiers": {"blanched": True},
    }
    assert is_respiring_produce(blanched_veg) is False
    req_blanched = derive(profile=blanched_veg, environment=env, target_shelf_life=30.0, pack_geometry=geom)
    assert req_blanched.regime == "non_respiring_barrier"


# ---------------------------------------------------------------------------
# Test 3: Mechanical, Thermal, and Optical Derivations
# ---------------------------------------------------------------------------

def test_mechanical_thermal_optical_derivations():
    """
    Verify mechanical requirements (mass, drop, stack), thermal (process),
    and optical (light sensitivity).
    """
    profile = {
        "commodity_id": "processed.milk_powder",
        "class": "dry_powder",
        "light_sensitive": True,
        "fat_pct": {"value": 26.0},
    }

    # Heavy pack with drop height and stack height
    geom_heavy = PackGeometry(
        product_mass_kg=2.5,
        drop_height_m=1.5,
        stack_height_m=2.5,
        process="hot_fill",
    )

    req = derive(profile=profile, target_shelf_life=365.0, pack_geometry=geom_heavy)

    # Mechanical checks
    assert req.min_thickness_um >= 80.0
    assert req.min_seal_strength_n_15mm >= 30.0

    # Thermal checks
    assert req.process == "hot_fill"
    assert req.service_temp_max_c == 95.0

    # Optical checks
    assert req.light_barrier_od is not None
    assert req.light_barrier_od >= 2.0

    # Retort process
    geom_retort = PackGeometry(process="retort")
    req_retort = derive(profile=profile, target_shelf_life=180.0, pack_geometry=geom_retort)
    assert req_retort.service_temp_max_c == 121.0
    assert req_retort.min_seal_strength_n_15mm >= 35.0


# ---------------------------------------------------------------------------
# Test 4: Hard Constraint Filters
# ---------------------------------------------------------------------------

def test_filter_hard_constraints():
    """
    Test the 6 hard constraints that remove candidates:
    - Service temp (LLDPE in retort)
    - Metal detection vs foil/metallisation
    - Microwave vs foil
    - Machine incompatibility
    - Barrier requirement not met
    """
    candidates = [
        # 1. Standard LLDPE sealant (fails retort)
        PackageCandidate(
            id="c_lldpe",
            layer_stack=["PET", "LLDPE"],
            gauge_per_layer=[12.0, 50.0],
            measured_otr=65.0,
            measured_wvtr=8.5,
            machine_compatibility=["VFFS"],
        ),
        # 2. Retort grade CPP pouch
        PackageCandidate(
            id="c_retort_cpp",
            layer_stack=["PET", "AluFoil", "CPP"],
            gauge_per_layer=[12.0, 9.0, 70.0],
            measured_otr=0.01,
            measured_wvtr=0.02,
            machine_compatibility=["pre_formed_pouch"],
        ),
        # 3. Transparent AlOx with LLDPE
        PackageCandidate(
            id="c_alox",
            layer_stack=["AlOx-PET", "LLDPE"],
            gauge_per_layer=[12.0, 50.0],
            measured_otr=1.4,
            measured_wvtr=1.1,
            machine_compatibility=["VFFS", "HFFS"],
        ),
        # 4. Metallised BOPP/CPP
        PackageCandidate(
            id="c_vmbopp",
            layer_stack=["BOPP", "VMBOPP", "CPP"],
            gauge_per_layer=[20.0, 18.0, 40.0],
            measured_otr=22.0,
            measured_wvtr=0.65,
            machine_compatibility=["VFFS", "flow_wrap"],
        ),
    ]

    # 1. Retort process constraint
    req_retort = RequirementVector(process="retort", service_temp_max_c=121.0)
    res_retort = filter_candidates(candidates, req_retort)
    survivor_ids = [c.id for c in res_retort.survivors]
    assert "c_lldpe" not in survivor_ids, "LLDPE sealant must be rejected in retort"
    assert "c_retort_cpp" in survivor_ids, "CPP retort pouch must survive retort"

    # 2. Metal detection constraint
    req_std = RequirementVector(regime="non_respiring_barrier", max_wvtr=2.0)
    geom_metal = PackGeometry(metal_detection_required=True)
    res_metal = filter_candidates(candidates, req_std, pack_geometry=geom_metal)
    metal_survivors = [c.id for c in res_metal.survivors]
    assert "c_retort_cpp" not in metal_survivors, "AluFoil must be rejected under metal detection"
    assert "c_vmbopp" not in metal_survivors, "VMBOPP must be rejected under metal detection"
    assert "c_alox" in metal_survivors, "AlOx transparent barrier must pass metal detection"

    # 3. Microwave constraint
    geom_micro = PackGeometry(microwave_required=True)
    res_micro = filter_candidates(candidates, req_std, pack_geometry=geom_micro)
    micro_survivors = [c.id for c in res_micro.survivors]
    assert "c_retort_cpp" not in micro_survivors, "AluFoil must be rejected for microwave"
    assert "c_alox" in micro_survivors, "AlOx structure is microwaveable"

    # 4. Machine incompatibility
    geom_machine = PackGeometry(filling_line="flow_wrap")
    res_machine = filter_candidates(candidates, req_std, pack_geometry=geom_machine)
    machine_survivors = [c.id for c in res_machine.survivors]
    assert "c_vmbopp" in machine_survivors
    assert "c_retort_cpp" not in machine_survivors, "Pre-formed pouch candidate cannot run on flow-wrap"


# ---------------------------------------------------------------------------
# Test 5: Scorer Behavior Across Modes and Policies
# ---------------------------------------------------------------------------

def test_scorer_modes_and_policies():
    """
    Verify mode weight behavior (Kisan vs Business vs Expert),
    enforcement of >= 3 options, and guarantee of lower-environmental-impact candidate.
    """
    kb = load_kb()
    candidates = [
        # Cat II mono-material
        PackageCandidate(
            id="c_mono_pp",
            name="Mono-PP",
            layer_stack=["BOPP", "VMBOPP", "CPP"],
            gauge_per_layer=[20.0, 18.0, 40.0],
            measured_otr=22.0,
            measured_wvtr=0.65,
            cost_per_pack=1.75,
            epr_category="Cat II",
            recyclability_score=0.95,
        ),
        # Cat III multi-layer
        PackageCandidate(
            id="c_vmpet",
            name="VMPET Triplex",
            layer_stack=["PET", "VMPET", "LLDPE"],
            gauge_per_layer=[12.0, 12.0, 50.0],
            measured_otr=0.85,
            measured_wvtr=0.95,
            cost_per_pack=2.10,
            epr_category="Cat III",
            recyclability_score=0.30,
        ),
        # Cat III foil
        PackageCandidate(
            id="c_foil",
            name="Foil Triplex",
            layer_stack=["PET", "AluFoil", "LLDPE"],
            gauge_per_layer=[12.0, 9.0, 50.0],
            measured_otr=0.05,
            measured_wvtr=0.05,
            cost_per_pack=3.40,
            epr_category="Cat III",
            recyclability_score=0.20,
        ),
    ]

    req = RequirementVector(regime="non_respiring_barrier", max_wvtr=0.6, max_otr=1.2)

    # 1. Kisan mode: cost & availability are top priorities
    kisan_res = score_candidates(candidates, req, mode="kisan")
    assert len(kisan_res.ranked_options) >= 3
    assert kisan_res.ranked_options[0].candidate.id == "c_mono_pp"  # Cheapest

    # 2. Business mode
    biz_res = score_candidates(candidates, req, mode="business")
    assert len(biz_res.ranked_options) >= 3
    assert any(opt.is_lower_environmental_impact for opt in biz_res.ranked_options)

    # 3. Expert mode with custom sliders favoring shelf life heavily
    expert_weights = {
        "barrier_margin": 0.80,
        "cost": 0.05,
        "sustainability": 0.05,
        "machinability": 0.05,
        "availability": 0.05,
    }
    expert_res = score_candidates(candidates, req, mode="expert", weights=expert_weights)
    # When shelf life is 80% weighted, maximum barrier foil or VMPET moves to rank 1
    assert expert_res.ranked_options[0].candidate.id in ["c_foil", "c_vmpet"]
    # Even when eco option does not win, it is still included in top 3
    assert any(opt.is_lower_environmental_impact for opt in expert_res.ranked_options[:3])


# ---------------------------------------------------------------------------
# Test 6: Pareto Frontier Computation
# ---------------------------------------------------------------------------

def test_pareto_frontier_computation():
    """
    Verify 3D non-dominated frontier across cost, shelf life, and recyclability.
    """
    candidates = [
        PackageCandidate(
            id="c_cheap_green",
            layer_stack=["BOPP", "CPP"],
            gauge_per_layer=[20.0, 40.0],
            cost_per_pack=0.95,
            epr_category="Cat II",
            recyclability_score=0.95,
        ),
        PackageCandidate(
            id="c_mid_barrier",
            layer_stack=["BOPP", "VMBOPP", "CPP"],
            gauge_per_layer=[20.0, 18.0, 40.0],
            cost_per_pack=1.75,
            epr_category="Cat II",
            recyclability_score=0.95,
        ),
        PackageCandidate(
            id="c_high_barrier",
            layer_stack=["PET", "VMPET", "LLDPE"],
            gauge_per_layer=[12.0, 12.0, 50.0],
            cost_per_pack=2.10,
            epr_category="Cat III",
            recyclability_score=0.30,
        ),
        PackageCandidate(
            id="c_foil",
            layer_stack=["PET", "AluFoil", "LLDPE"],
            gauge_per_layer=[12.0, 9.0, 50.0],
            cost_per_pack=3.40,
            epr_category="Cat III",
            recyclability_score=0.20,
        ),
    ]

    shelf_life_map = {
        "c_cheap_green": 60.0,
        "c_mid_barrier": 180.0,
        "c_high_barrier": 240.0,
        "c_foil": 365.0,
    }

    result = compute_pareto_frontier(candidates=candidates, shelf_life_map=shelf_life_map)

    # All four candidates represent distinct optimal trade-offs:
    # - c_cheap_green: lowest cost (0.95)
    # - c_mid_barrier: higher life (180) + highest recyclability (0.95)
    # - c_high_barrier: higher life (240)
    # - c_foil: longest life (365)
    frontier_ids = [p.id for p in result.frontier]
    assert len(frontier_ids) >= 3
    assert "c_mid_barrier" in frontier_ids
    assert "c_foil" in frontier_ids

    # Verify chart series output format
    assert result.chart_series.axes["x"] == "Cost (₹/pack)"
    assert len(result.chart_series.frontier_series) == len(result.frontier)
    assert len(result.trade_off_notes) > 0
