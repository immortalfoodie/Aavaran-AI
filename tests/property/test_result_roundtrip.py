from datetime import datetime
import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from engine.types import (
    SourceType,
    ResolutionLevel,
    SafetyStatus,
    Provenance,
    CommodityProfile,
    Environment,
    RequirementVector,
    PackageCandidate,
    ShelfLifeResult,
    SafetyVerdict,
)
from engine.result import SealedResult, ResolvedInputs, ValueOfInformation


# Basic strategies for some generic fields
st_floats = st.floats(allow_nan=False, allow_infinity=False)
st_strs = st.text(min_size=1, max_size=10)

# Build custom strategies for Pydantic models to ensure we don't hit edge cases that
# hypothesis can't infer correctly (like Any or Dict[str, Any]).
st_provenance = st.builds(
    Provenance,
    value=st.one_of(st_floats, st_strs),
    unit=st.one_of(st.none(), st_strs),
    range_low=st.one_of(st.none(), st_floats),
    range_high=st.one_of(st.none(), st_floats),
    source_id=st.one_of(st.none(), st_strs),
    source_type=st.one_of(st.none(), st.sampled_from(SourceType)),
    resolution_level=st.one_of(st.none(), st.sampled_from(ResolutionLevel)),
    confidence=st.one_of(st.none(), st.floats(min_value=0.0, max_value=1.0)),
    note=st.one_of(st.none(), st_strs),
)

st_commodity = st.builds(
    CommodityProfile,
    commodity_id=st_strs,
    names=st.dictionaries(st_strs, st.lists(st_strs)),
    group=st_strs,
    commodity_class=st_strs,
    moisture_pct=st.one_of(st.none(), st_provenance),
    water_activity=st.one_of(st.none(), st_provenance),
    fat_pct=st.one_of(st.none(), st_provenance),
    pH=st.one_of(st.none(), st_provenance),
    respiration_model=st.one_of(st.none(), st_strs),
    respiration_ea_kj_mol=st.one_of(st.none(), st_provenance),
    respiration_ref_t_c=st.one_of(st.none(), st_provenance),
    respiration_ref_rate=st.one_of(st.none(), st_provenance),
    storage_optimum_t_c=st.one_of(st.none(), st_provenance),
    storage_optimum_rh_pct=st.one_of(st.none(), st_provenance),
    storage_life_days=st.one_of(st.none(), st_provenance),
    chilling_sensitive_below_c=st.one_of(st.none(), st_provenance),
    ethylene_production=st.one_of(st.none(), st_strs),
    ethylene_sensitivity=st.one_of(st.none(), st_strs),
    ethylene_note=st.one_of(st.none(), st_strs),
    failure_modes=st.lists(st_strs),
    light_sensitive=st.booleans(),
    light_note=st.one_of(st.none(), st_strs),
    state_modifiers=st.dictionaries(st_strs, st_strs), # simplified for testing
)

st_environment = st.builds(
    Environment,
    temperature=st_provenance,
    relative_humidity=st_provenance,
    duration=st_provenance,
    transport_mode=st.one_of(st.none(), st_provenance),
    storage_type=st.one_of(st.none(), st_provenance),
)

st_requirement_vector = st.builds(
    RequirementVector,
    max_wvtr=st.one_of(st.none(), st_floats),
    max_otr=st.one_of(st.none(), st_floats),
    min_otr=st.one_of(st.none(), st_floats),
    target_o2=st.one_of(st.none(), st_floats),
    target_co2=st.one_of(st.none(), st_floats),
    min_thickness_um=st.one_of(st.none(), st_floats),
    min_seal_strength_n_15mm=st.one_of(st.none(), st_floats),
    min_puncture=st.one_of(st.none(), st_floats),
    light_barrier_od=st.one_of(st.none(), st_floats),
    antifog_required=st.one_of(st.none(), st.booleans()),
    map_required=st.one_of(st.none(), st.booleans()),
    perforation_required=st.one_of(st.none(), st.booleans()),
    equation_id=st.one_of(st.none(), st_strs),
)

st_package_candidate = st.builds(
    PackageCandidate,
    layer_stack=st.lists(st_strs, min_size=1),
    gauge_per_layer=st.lists(st_floats, min_size=1),
    measured_otr=st.one_of(st.none(), st_floats),
    measured_wvtr=st.one_of(st.none(), st_floats),
    test_conditions=st.one_of(st.none(), st_strs),
    cost_per_pack=st.one_of(st.none(), st_floats),
    epr_category=st.one_of(st.none(), st_strs),
    recyclability_score=st.one_of(st.none(), st_floats),
    machine_compatibility=st.lists(st_strs),
    availability=st.one_of(st.none(), st_strs),
)

st_shelf_life_result = st.builds(
    ShelfLifeResult,
    days_p10=st_floats,
    days_p50=st_floats,
    days_p90=st_floats,
    limiting_mechanism=st_strs,
    all_mode_results=st.dictionaries(st_strs, st_floats),
    curve_points=st.lists(st.dictionaries(st_strs, st_floats)),
    safety_factor_applied=st_floats,
    equations_used=st.lists(st_strs),
)

st_safety_verdict = st.builds(
    SafetyVerdict,
    status=st.sampled_from([SafetyStatus.PASS, SafetyStatus.WARN]), # Block tested separately due to validator
    rule_id=st_strs,
    message_key=st_strs,
    is_overridable=st.booleans(),
)

st_resolved_inputs = st.builds(
    ResolvedInputs,
    commodity=st.one_of(st.none(), st_commodity),
    environment=st.one_of(st.none(), st_environment),
    state_modifiers=st.dictionaries(st_strs, st_strs),
)

st_value_of_information = st.builds(
    ValueOfInformation,
    field=st_strs,
    variance_reduction=st_floats,
    description=st_strs,
)

st_sealed_result = st.builds(
    SealedResult,
    result_id=st_strs,
    engine_version=st_strs,
    kb_version=st_strs,
    ruleset_version=st_strs,
    resolved=st_resolved_inputs,
    assumptions=st.lists(st_provenance),
    requirements=st.one_of(st.none(), st_requirement_vector),
    candidates=st.lists(st_package_candidate),
    shelf_life=st.one_of(st.none(), st_shelf_life_result),
    safety=st.one_of(st.none(), st_safety_verdict),
    verdict=st_strs,
    guidance=st.lists(st.dictionaries(st_strs, st_strs)),
    value_of_information=st.one_of(st.none(), st_value_of_information),
    citations=st.lists(st_strs),
    computed_at=st.datetimes(),
)


@given(st_sealed_result)
def test_sealed_result_roundtrip(result: SealedResult) -> None:
    """
    Test that SealedResult serialises to JSON and deserialises back identically.
    """
    json_str = result.model_dump_json()
    reloaded = SealedResult.model_validate_json(json_str)
    assert result == reloaded

def test_safety_verdict_block_override() -> None:
    """
    Test that a SafetyVerdict with status BLOCK cannot be overridable.
    """
    # Should fail if is_overridable=True when status=BLOCK
    with pytest.raises(ValidationError):
        SafetyVerdict(status=SafetyStatus.BLOCK, rule_id="1", message_key="msg", is_overridable=True)

    # Should succeed if is_overridable=False
    v = SafetyVerdict(status=SafetyStatus.BLOCK, rule_id="1", message_key="msg", is_overridable=False)
    assert not v.is_overridable
