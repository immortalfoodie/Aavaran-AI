"""
Tests for Expert Mode Audit requirements (Steps 2 - 6).
Verifies:
1. Real substituted physics equations
2. Real sensitivity analysis values adding to 100% with direction
3. Monte Carlo P10/P50/P90, mechanism, confidence
4. Compliance evaluated rules >= 4 with legal minimums
5. Assumptions ledger contains all 6 REQUIRED_ASSUMPTION_FIELDS
"""

import pytest
from engine.orchestrate import (
    recommend,
    RecommendRequest,
    REQUIRED_ASSUMPTION_FIELDS,
)


def test_expert_dry_food_audit():
    req = RecommendRequest(
        mode="expert",
        input={
            "commodity_id": "food.snack.namkeen_bhujia",
            "environment": {"temperature_c": 30.0, "relative_humidity_pct": 75.0},
            "pack_geometry": {"product_mass_kg": 0.18, "pack_area_m2": 0.055},
        },
    )
    res = recommend(req)

    # 1. Equations check (Step 2)
    assert len(res.equations) >= 3
    eq_ids = {eq.equation_id for eq in res.equations}
    assert "M-03" in eq_ids
    assert "MIC-01" in eq_ids
    assert "OX-01" in eq_ids

    m03 = next(eq for eq in res.equations if eq.equation_id == "M-03")
    assert "{W_s}" in m03.formula_template
    assert "W_s" in m03.inputs
    assert m03.inputs["W_s"].value is not None
    assert m03.output.value is not None

    # 2. Sensitivity check (Step 3)
    assert len(res.sensitivity) >= 4
    sens_sum = sum(s.variance_reduction_pct for s in res.sensitivity)
    assert pytest.approx(sens_sum, abs=0.1) == 100.0
    param_names = [s.parameter for s in res.sensitivity]
    assert "storage_temperature" in param_names
    assert "initial_moisture" in param_names
    assert "storage_rh" in param_names
    assert "pack_area" in param_names
    for s in res.sensitivity:
        assert s.direction in ("negative", "positive")

    # 3. Monte Carlo / Shelf Life check (Step 4)
    assert res.shelf_life is not None
    assert res.shelf_life.days_p10 > 0
    assert res.shelf_life.days_p50 >= res.shelf_life.days_p10
    assert res.shelf_life.days_p90 >= res.shelf_life.days_p50
    assert res.shelf_life.mechanism is not None
    assert 0.0 <= res.shelf_life.confidence <= 1.0

    # 4. Compliance check (Step 5)
    assert res.compliance is not None
    assert len(res.compliance.rules_evaluated) >= 4
    comp_ids = {r.rule_id for r in res.compliance.rules_evaluated}
    assert "IN-FSSAI-2018-R4" in comp_ids
    assert "IN-FSSAI-2018-SCH3" in comp_ids
    assert "IN-PWM-2022-CAT" in comp_ids
    assert "IN-LAB-2020-DATE" in comp_ids

    # 5. Assumptions check (Step 6)
    actual_fields = {a.field for a in res.assumptions if a.field}
    missing = REQUIRED_ASSUMPTION_FIELDS - actual_fields
    assert len(missing) == 0, f"Missing required assumption fields: {missing}"


def test_expert_fresh_produce_audit():
    req = RecommendRequest(
        mode="expert",
        input={
            "commodity_id": "veg.okra",
            "environment": {"temperature_c": 25.0, "relative_humidity_pct": 85.0},
            "pack_geometry": {"product_mass_kg": 0.5, "pack_area_m2": 0.08},
        },
    )
    res = recommend(req)

    # Produce sensitivity rankings
    param_names = [s.parameter for s in res.sensitivity]
    assert param_names[0] == "respiration_rate"
    sens_sum = sum(s.variance_reduction_pct for s in res.sensitivity)
    assert pytest.approx(sens_sum, abs=0.1) == 100.0

    # Assumptions check
    actual_fields = {a.field for a in res.assumptions if a.field}
    missing = REQUIRED_ASSUMPTION_FIELDS - actual_fields
    assert len(missing) == 0
