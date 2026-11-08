"""
Adversarial Food Safety Gate Test Suite.

Contains 20+ deliberately unsafe input combinations across all non-negotiable
food safety gates per Section 5.4 of BLUEPRINT.md:
1. Botulinum gate: aw > 0.92, pH > 4.6, O2 < 2%, T > 5 °C
2. Fresh-cut gate: fresh-cut produce in reduced-oxygen packaging with T > 5 °C
3. Light gate: potato in transparent/non-UV pack (solanine/glycoalkaloid safety hazard)
4. Acidified gate: acidified foods at ambient with pH > 4.60
5. Histamine gate: scombroid-prone fish exposed to T > 5 °C
6. Allergen cross-contact gate: allergen-derived packaging or unsegregated lines

CRITICAL INVARIANTS:
- Every unsafe combination MUST evaluate to SafetyStatus.BLOCK.
- Every BLOCK verdict MUST have is_overridable == False.
- No caller in any mode, including 'Expert' mode, may bypass or override a BLOCK.
- Favorable quality/shelf-life numbers must NEVER mask a safety failure.
"""

import pytest

from engine.models.microbial import time_to_spoilage
from engine.models.safety import (
    RULE_ACIDIFIED,
    RULE_ALLERGEN,
    RULE_BOTULINUM,
    RULE_FRESH_CUT,
    RULE_HISTAMINE,
    RULE_LIGHT_POTATO,
    acidified_gate,
    allergen_crosscontact_gate,
    botulinum_gate,
    enforce_safety_interlock,
    fresh_cut_gate,
    histamine_gate,
    light_gate,
    safety_gate,
)
from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    Provenance,
    SafetyStatus,
    SafetyVerdict,
)

# ===========================================================================
# 1. Botulinum Hazard Gate (5 adversarial cases)
# ===========================================================================


def test_botulinum_ambient_low_acid_canned():
    """Case 1: Low-acid high-aw food under anaerobic ambient conditions."""
    verdict = botulinum_gate(
        water_activity=0.98,
        ph=6.2,
        o2_fraction=0.005,  # 0.5% O2 (< 2%)
        max_temperature_c=25.0,  # Ambient 25 °C (> 5 °C)
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False


def test_botulinum_mild_chill_abuse_protein():
    """Case 2: Mild temperature abuse (6.0 °C, just above 5.0 °C cold chain limit)."""
    verdict = botulinum_gate(
        water_activity=0.96,
        ph=5.8,
        o2_fraction=0.010,  # 1.0% O2 (< 2%)
        max_temperature_c=6.0,  # 6.0 °C (> 5.0 °C)
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False


def test_botulinum_vacuum_packed_paneer_ambient():
    """Case 3: High-moisture paneer (aw=0.99, pH=6.3) in vacuum pack at 30 °C."""
    profile = CommodityProfile(
        commodity_id="dairy.paneer",
        names={"en": ["paneer"]},
        group="dairy",
        commodity_class="fresh_cheese",
        water_activity=Provenance(value=0.99),
        pH=Provenance(value=6.3),
    )
    package = PackageCandidate(
        layer_stack=["PA", "PE"],
        gauge_per_layer=[15.0, 50.0],
    )
    environment = Environment(
        temperature=Provenance(value=30.0, unit="degC"),
        relative_humidity=Provenance(value=70.0, unit="%"),
        duration=Provenance(value=7.0, unit="days"),
    )
    verdict = botulinum_gate(
        profile=profile,
        environment=environment,
        package=package,
        o2_fraction=0.001,  # Vacuum pouch residual O2 = 0.1%
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False


def test_botulinum_cut_potato_vacuum_at_30c():
    """Case 4: Blueprint classic - Cut potato at 30 °C in anaerobic pack."""
    profile = CommodityProfile(
        commodity_id="veg.potato.solanum_tuberosum",
        names={"en": ["potato"], "hi": ["aloo"]},
        group="root_tuber",
        commodity_class="high_moisture_starchy",
        water_activity=Provenance(value=0.98),
        pH=Provenance(value=6.1),
        state_modifiers={"cut": {"microbial_risk": "high"}},
    )
    verdict = botulinum_gate(
        profile=profile,
        max_temperature_c=30.0,
        o2_fraction=0.002,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False


def test_botulinum_near_boundary_unsafe():
    """Case 5: Exact boundary edge case: aw=0.921, pH=4.61, O2=1.9%, T=5.1 °C."""
    verdict = botulinum_gate(
        water_activity=0.921,
        ph=4.61,
        o2_fraction=0.019,
        max_temperature_c=5.1,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False


# ===========================================================================
# 2. Fresh-Cut Produce Cold Chain Gate (4 adversarial cases)
# ===========================================================================


def test_fresh_cut_watermelon_map_at_12c():
    """Case 6: Fresh-cut watermelon in reduced oxygen MAP at 12 °C."""
    profile = CommodityProfile(
        commodity_id="fruit.watermelon.cut",
        names={"en": ["cut watermelon"]},
        group="fruit",
        commodity_class="fresh_cut",
        state_modifiers={"cut": {}},
    )
    verdict = fresh_cut_gate(
        profile=profile,
        o2_fraction=0.03,  # 3% O2 ROP
        max_temperature_c=12.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_FRESH_CUT
    assert verdict.is_overridable is False


def test_fresh_cut_pineapple_barrier_bag_at_8c():
    """Case 7: Fresh-cut pineapple in barrier bag (ROP) at 8 °C."""
    package = PackageCandidate(
        layer_stack=["PET", "EVOH", "PE"],
        gauge_per_layer=[12.0, 5.0, 40.0],
    )
    verdict = fresh_cut_gate(
        package=package,
        is_fresh_cut=True,
        o2_fraction=0.01,
        max_temperature_c=8.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_FRESH_CUT
    assert verdict.is_overridable is False


def test_fresh_cut_spinach_nitrogen_flush_at_15c():
    """Case 8: Cut spinach leaves in nitrogen-flushed pouch at 15 °C."""
    profile = CommodityProfile(
        commodity_id="veg.spinach",
        names={"en": ["spinach"]},
        group="leafy_green",
        commodity_class="high_respiration_leafy",
        state_modifiers={"cut": {"respiration_x": [3.0, 5.0]}},
    )
    verdict = fresh_cut_gate(
        profile=profile,
        o2_fraction=0.02,
        max_temperature_c=15.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_FRESH_CUT
    assert verdict.is_overridable is False


def test_fresh_cut_apple_slices_vacuum_at_10c():
    """Case 9: Peeled & sliced apples vacuum packed at 10 °C."""
    verdict = fresh_cut_gate(
        is_fresh_cut=True,
        is_rop=True,
        o2_fraction=0.005,
        max_temperature_c=10.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_FRESH_CUT
    assert verdict.is_overridable is False


# ===========================================================================
# 3. Light Exposure & Glycoalkaloid Formation Gate (2 adversarial cases)
# ===========================================================================


def test_light_potato_clear_ldpe_film():
    """Case 10: Raw potato in transparent clear LDPE film (solanine safety hazard)."""
    profile = CommodityProfile(
        commodity_id="veg.potato.solanum_tuberosum",
        names={"en": ["potato"], "hi": ["aloo"]},
        group="root_tuber",
        commodity_class="high_moisture_starchy",
        light_sensitive=True,
    )
    package = PackageCandidate(
        layer_stack=["LDPE"],
        gauge_per_layer=[40.0],
    )
    verdict = light_gate(
        profile=profile,
        package=package,
        is_opaque=False,
        uv_blocking=False,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_LIGHT_POTATO
    assert verdict.is_overridable is False


def test_light_potato_transparent_clamshell():
    """Case 11: Potato in transparent clear PET clamshell without UV absorber."""
    package = PackageCandidate(
        layer_stack=["APET"],
        gauge_per_layer=[250.0],
    )
    verdict = light_gate(
        package=package,
        commodity_id="potato",
        is_opaque=False,
        uv_blocking=False,
        light_barrier_od=0.1,  # Clear pack
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_LIGHT_POTATO
    assert verdict.is_overridable is False


# ===========================================================================
# 4. Acidified Foods Equilibrium pH Gate (3 adversarial cases)
# ===========================================================================


def test_acidified_salsa_defective_ph_at_ambient():
    """Case 12: Acidified salsa at 25 °C with pH=4.85 (> 4.60)."""
    verdict = acidified_gate(
        is_acidified=True,
        ph=4.85,
        max_temperature_c=25.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ACIDIFIED
    assert verdict.is_overridable is False


def test_acidified_pickled_cucumbers_under_acidified_at_22c():
    """Case 13: Pickled cucumbers with defective acidification pH=4.72 at 22 °C."""
    profile = CommodityProfile(
        commodity_id="processed.pickled_cucumber.acidified",
        names={"en": ["pickled cucumber"]},
        group="acidified_food",
        commodity_class="canned_acidified",
        pH=Provenance(value=4.72),
    )
    verdict = acidified_gate(
        profile=profile,
        max_temperature_c=22.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ACIDIFIED
    assert verdict.is_overridable is False


def test_acidified_peppers_ambient_abuse():
    """Case 14: Acidified peppers with pH=5.10 at 30 °C ambient."""
    verdict = acidified_gate(
        is_acidified=True,
        ph=5.10,
        max_temperature_c=30.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ACIDIFIED
    assert verdict.is_overridable is False


# ===========================================================================
# 5. Scombroid Histamine Formation Gate (3 adversarial cases)
# ===========================================================================


def test_histamine_yellowfin_tuna_at_18c():
    """Case 15: Fresh yellowfin tuna fillets held at 18 °C ambient."""
    profile = CommodityProfile(
        commodity_id="seafood.yellowfin_tuna",
        names={"en": ["yellowfin tuna"]},
        group="fish",
        commodity_class="pelagic_finfish",
    )
    verdict = histamine_gate(
        profile=profile,
        max_temperature_c=18.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_HISTAMINE
    assert verdict.is_overridable is False


def test_histamine_mackerel_in_vacuum_at_9c():
    """Case 16: Fresh Atlantic mackerel fillet vacuum packed at 9 °C."""
    verdict = histamine_gate(
        is_scombroid=True,
        max_temperature_c=9.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_HISTAMINE
    assert verdict.is_overridable is False


def test_histamine_mahi_mahi_at_25c():
    """Case 17: Fresh mahi-mahi portions at 25 °C."""
    profile = CommodityProfile(
        commodity_id="seafood.mahi_mahi",
        names={"en": ["mahi mahi", "dorado"]},
        group="fish",
        commodity_class="pelagic_finfish",
    )
    verdict = histamine_gate(
        profile=profile,
        max_temperature_c=25.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_HISTAMINE
    assert verdict.is_overridable is False


# ===========================================================================
# 6. Allergen Cross-Contact & Packaging Material Gate (3 adversarial cases)
# ===========================================================================


def test_allergen_gluten_free_snack_with_wheat_barrier():
    """Case 18: Certified gluten-free product with wheat-gluten edible barrier."""
    package = PackageCandidate(
        layer_stack=["wheat_gluten_film", "paper"],
        gauge_per_layer=[15.0, 60.0],
    )
    verdict = allergen_crosscontact_gate(
        package=package,
        allergen_free_claimed=True,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ALLERGEN
    assert verdict.is_overridable is False


def test_allergen_dairy_free_food_casein_coating():
    """Case 19: Dairy-free vegan food packed in casein-protein coated structure."""
    package = PackageCandidate(
        layer_stack=["casein_barrier", "LDPE"],
        gauge_per_layer=[10.0, 40.0],
    )
    profile = CommodityProfile(
        commodity_id="vegan.dairy_free_snack",
        names={"en": ["dairy free snack"]},
        group="prepared_food",
        commodity_class="dairy_free",
    )
    verdict = allergen_crosscontact_gate(
        profile=profile,
        package=package,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ALLERGEN
    assert verdict.is_overridable is False


def test_allergen_unsegregated_shared_line():
    """Case 20: Allergen-free baby food packaged on unsegregated shared line."""
    verdict = allergen_crosscontact_gate(
        allergen_free_claimed=True,
        shared_line_unsegregated=True,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_ALLERGEN
    assert verdict.is_overridable is False


# ===========================================================================
# 7. Non-Bypassable Policy & Isolation Invariants
# ===========================================================================


def test_expert_mode_cannot_bypass_block():
    """
    INVARIANT: A BLOCK verdict sets is_overridable to False and no caller,
    in any mode, including Expert, may bypass it.
    """
    unsafe_verdict = botulinum_gate(
        water_activity=0.98,
        ph=6.0,
        o2_fraction=0.005,
        max_temperature_c=25.0,
    )
    assert unsafe_verdict.status == SafetyStatus.BLOCK
    assert unsafe_verdict.is_overridable is False

    # Attempting to enforce or bypass in Expert mode MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        enforce_safety_interlock(unsafe_verdict, mode="Expert")
    assert "strictly non-overridable" in str(exc_info.value)
    assert "Expert" in str(exc_info.value)

    # Calling with Standard mode also raises PermissionError
    with pytest.raises(PermissionError):
        enforce_safety_interlock(unsafe_verdict, mode="Standard")


def test_safety_verdict_pydantic_validator_rejects_overridable_block():
    """
    INVARIANT: Pydantic model validator prevents instantiating any BLOCK
    with is_overridable = True.
    """
    with pytest.raises(ValueError) as exc_info:
        SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_BOTULINUM,
            message_key="test",
            is_overridable=True,  # Forbidden by SafetyVerdict validator
        )
    assert "A BLOCK safety verdict cannot be overridable" in str(exc_info.value)


def test_safety_runs_independently_before_quality_prediction():
    """
    INVARIANT: Safety runs before and independently of quality prediction.
    A favorable shelf life prediction (e.g. 50+ days in anaerobic MAP)
    must NEVER mask a lethal safety failure (botulinum hazard).
    """
    # 1. Evaluate safety gate first
    safety = safety_gate(
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.005,  # Anaerobic MAP
        max_temperature_c=22.0,  # Ambient abuse
    )
    assert safety.status == SafetyStatus.BLOCK
    assert safety.is_overridable is False

    # 2. Suppose a microbial or quality model evaluates Pseudomonas
    # (which cannot grow without O2): Under anaerobic conditions, growth is 0
    microbial_result = time_to_spoilage(
        organism="pseudomonas",
        water_activity=0.98,
        ph=6.5,
        o2_fraction=0.005,  # Anaerobic
        temperature_c=22.0,
    )
    # Pseudomonas cannot grow, so Pseudomonas shelf life is infinite
    assert microbial_result.shelf_life_days == float("inf")

    # BUT the safety verdict is still a non-negotiable BLOCK!
    assert safety.status == SafetyStatus.BLOCK
    assert safety.rule_id == RULE_BOTULINUM


# ===========================================================================
# Blueprint Section 8.1 Explicit Adversarial Invariants
# ===========================================================================

def test_adversarial_cut_melon_in_vacuum_at_ambient():
    """
    Blueprint Section 8.1: Deliberately feed cut melon in vacuum at ambient (25 °C).
    MUST BLOCK every time with is_overridable = False.
    """
    profile = CommodityProfile(
        commodity_id="fruit.melon.cantaloupe.cut",
        names={"en": ["cut melon", "cantaloupe"]},
        group="fruit",
        commodity_class="fresh_cut",
        water_activity=Provenance(value=0.99),
        pH=Provenance(value=6.4),
        state_modifiers={"cut": {"microbial_risk": "high"}},
    )
    # Vacuum pack (ROP, O2 < 0.5%) at ambient 25 °C
    verdict = fresh_cut_gate(
        profile=profile,
        is_fresh_cut=True,
        is_rop=True,
        o2_fraction=0.002,
        max_temperature_c=25.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.is_overridable is False

    # Also master safety gate must block
    master_verdict = safety_gate(
        profile=profile,
        environment=Environment(
            temperature=Provenance(value=25.0, unit="degC"),
            relative_humidity=Provenance(value=75.0, unit="%"),
            duration=Provenance(value=3.0, unit="days"),
        ),
        package=PackageCandidate(
            layer_stack=["PA", "PE"],
            gauge_per_layer=[15.0, 50.0],
            is_vacuum=True,
        ),
        is_fresh_cut=True,
        is_rop=True,
        o2_fraction=0.002,
    )
    assert master_verdict.status == SafetyStatus.BLOCK
    assert master_verdict.is_overridable is False


def test_adversarial_low_acid_vegetable_in_oil_at_room_temp():
    """
    Blueprint Section 8.1: Deliberately feed low-acid vegetable in oil at room temperature (25 °C).
    MUST BLOCK every time with is_overridable = False (Clostridium botulinum neurotoxin hazard).
    """
    # Low-acid vegetable (garlic / peppers in oil: pH = 5.8, aw = 0.98, submerged anaerobic oil layer O2 < 0.1%)
    verdict = botulinum_gate(
        water_activity=0.98,
        ph=5.8,
        o2_fraction=0.001,  # Submerged in oil creates strict anaerobiosis
        max_temperature_c=25.0,
    )
    assert verdict.status == SafetyStatus.BLOCK
    assert verdict.rule_id == RULE_BOTULINUM
    assert verdict.is_overridable is False

