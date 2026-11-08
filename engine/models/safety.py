"""
Food Safety Gates and Hazard Interlocks for Aavaran.

Implements Section 5.4 of BLUEPRINT.md:
- Hard safety gates running independently of, and before, quality prediction:
    1. botulinum_gate(): BLOCK when aw > 0.92 AND pH > 4.6 AND O2 < 2%
       AND T_max > 5 °C. Classic hazard combination for low-acid foods.
    2. fresh_cut_gate(): BLOCK when fresh-cut produce is packaged in
       reduced-oxygen packaging (ROP/vacuum/MAP) without cold chain <= 5 °C.
    3. light_gate(): BLOCK when potato (Solanum tuberosum) lacks an opaque
       or UV-blocking pack (solanine toxic glycoalkaloids safety hazard).
       WARN for other light-sensitive commodities lacking barrier.
    4. acidified_gate(): BLOCK when acidified foods stored at ambient
       exceed equilibrium pH 4.60 (21 CFR 114 / FSSAI).
    5. histamine_gate(): BLOCK when scombroid-prone fish species (tuna,
       mackerel, mahi-mahi) are exposed to T > 5 °C (histamine accumulation).
    6. allergen_crosscontact_gate(): BLOCK when packaging materials contain
       allergens or unsegregated lines present cross-contact risks.

NON-NEGOTIABLE SAFETY POLICY:
- Safety runs before quality prediction. Quality never masks safety.
- A BLOCK verdict sets is_overridable = False. No caller in any mode
  (including Expert) may bypass, override, or downgrade it.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    SafetyStatus,
    SafetyVerdict,
)

logger = logging.getLogger(__name__)

# Rule IDs
RULE_BOTULINUM = "SAFE-BOT-01"
RULE_FRESH_CUT = "SAFE-FRESHCUT-01"
RULE_LIGHT_POTATO = "SAFE-LIGHT-POTATO-01"
RULE_LIGHT_GENERAL = "SAFE-LIGHT-01"
RULE_ACIDIFIED = "SAFE-ACIDIFIED-01"
RULE_HISTAMINE = "SAFE-HISTAMINE-01"
RULE_ALLERGEN = "SAFE-ALLERGEN-01"

# Known scombroid-prone species tokens (FDA Guidance Chapter 7)
SCOMBROID_SPECIES_TOKENS = [
    "tuna",
    "mackerel",
    "mahi_mahi",
    "mahimahi",
    "bonito",
    "sardine",
    "anchovy",
    "bluefish",
    "swordfish",
    "marlin",
    "amberjack",
    "herring",
    "scombridae",
]

# Known opaque / UV barrier material tokens
OPAQUE_BARRIER_TOKENS = [
    "alu",
    "aluminum",
    "aluminium",
    "foil",
    "vmpet",
    "vmcpp",
    "metallized",
    "metalized",
    "black_pe",
    "opaque",
    "paper",
    "uv_blocking",
]

# Known allergen material tokens in packaging
ALLERGEN_MATERIAL_TOKENS = [
    "wheat_gluten",
    "wheat_starch",
    "casein",
    "milk_protein",
    "soy_protein",
    "peanut",
    "sesame",
    "crustacean_chitosan",
]


# ---------------------------------------------------------------------------
# Input Extraction Helpers
# ---------------------------------------------------------------------------


def _extract_water_activity(
    profile: CommodityProfile | dict[str, Any] | None,
    aw_override: float | None,
) -> float:
    if aw_override is not None:
        return float(aw_override)
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        entry = p_dict.get("water_activity")
        if isinstance(entry, dict):
            val = entry.get("value")
            if val is not None:
                return float(val)
        elif isinstance(entry, (int, float)):
            return float(entry)
    return 0.95


def _extract_ph(
    profile: CommodityProfile | dict[str, Any] | None,
    ph_override: float | None,
) -> float:
    if ph_override is not None:
        return float(ph_override)
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        entry = p_dict.get("pH")
        if isinstance(entry, dict):
            val = entry.get("value")
            if val is not None:
                return float(val)
        elif isinstance(entry, (int, float)):
            return float(entry)
    return 6.0


def _extract_max_temperature(
    environment: Environment | dict[str, Any] | None,
    temp_override: float | None,
) -> float:
    if temp_override is not None:
        return float(temp_override)
    if environment is not None:
        e_dict = (
            environment if isinstance(environment, dict) else environment.model_dump()
        )
        entry = e_dict.get("temperature")
        if isinstance(entry, dict):
            val = entry.get("range_high") or entry.get("value")
            if val is not None:
                return float(val)
        elif isinstance(entry, (int, float)):
            return float(entry)
    return 20.0


def _extract_o2_fraction(
    package: PackageCandidate | dict[str, Any] | None,
    o2_override: float | None,
) -> float:
    if o2_override is not None:
        return float(o2_override)
    if package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        for k in ["headspace_o2_fraction", "target_o2", "measured_o2", "o2_fraction"]:
            if k in pkg_dict and pkg_dict[k] is not None:
                return float(pkg_dict[k])
    return 0.209


def _is_fresh_cut_commodity(
    profile: CommodityProfile | dict[str, Any] | None,
    state_modifiers: dict[str, Any] | None = None,
    is_fresh_cut_override: bool | None = None,
) -> bool:
    if is_fresh_cut_override is not None:
        return is_fresh_cut_override
    if state_modifiers:
        for mod in ["cut", "sliced", "peeled", "diced", "chopped"]:
            if mod in state_modifiers:
                return True
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        mods = p_dict.get("state_modifiers", {})
        for mod in ["cut", "sliced", "peeled", "diced", "chopped"]:
            if mod in mods:
                return True
        cid = str(p_dict.get("commodity_id", "")).lower()
        if "fresh_cut" in cid or "cut_" in cid:
            return True
        cclass = str(p_dict.get("commodity_class", "")).lower()
        if "fresh_cut" in cclass:
            return True
    return False


def _is_reduced_oxygen_packaging(
    package: PackageCandidate | dict[str, Any] | None,
    o2_fraction: float,
    is_rop_override: bool | None = None,
) -> bool:
    if is_rop_override is not None:
        return is_rop_override
    if o2_fraction < 0.200:
        return True
    if package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        if (
            pkg_dict.get("map_required")
            or pkg_dict.get("is_vacuum")
            or pkg_dict.get("is_rop")
        ):
            return True
        layers = [str(layer).lower() for layer in pkg_dict.get("layer_stack", [])]
        for l_name in layers:
            if any(
                term in l_name
                for term in ["evoh", "pvdc", "alu", "barrier", "vacuum"]
            ):
                return True
    return False


def _is_potato_commodity(
    profile: CommodityProfile | dict[str, Any] | None,
    commodity_id_override: str | None = None,
) -> bool:
    cid = commodity_id_override or ""
    names_list: list[str] = []
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        cid = cid or str(p_dict.get("commodity_id", ""))
        for lang_names in p_dict.get("names", {}).values():
            if isinstance(lang_names, list):
                names_list.extend([str(n).lower() for n in lang_names])
    cid_lower = cid.lower()
    if any(term in cid_lower for term in ["potato", "solanum_tuberosum", "solanum"]):
        return True
    if any(term in names_list for term in ["potato", "aloo", "batata", "alu"]):
        return True
    return False


def _has_opaque_or_uv_protection(
    package: PackageCandidate | dict[str, Any] | None,
    is_opaque_override: bool | None = None,
    uv_blocking_override: bool | None = None,
    light_barrier_od_override: float | None = None,
) -> bool:
    if is_opaque_override is True or uv_blocking_override is True:
        return True
    if light_barrier_od_override is not None and light_barrier_od_override >= 1.5:
        return True
    if package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        if pkg_dict.get("is_opaque") or pkg_dict.get("uv_blocking"):
            return True
        od = pkg_dict.get("light_barrier_od")
        if od is not None and float(od) >= 1.5:
            return True
        layers = [str(layer).lower() for layer in pkg_dict.get("layer_stack", [])]
        for layer in layers:
            if any(tok in layer for tok in OPAQUE_BARRIER_TOKENS):
                return True
    return False


def _is_scombroid_fish(
    profile: CommodityProfile | dict[str, Any] | None,
    is_scombroid_override: bool | None = None,
) -> bool:
    if is_scombroid_override is not None:
        return is_scombroid_override
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if p_dict.get("scombroid_risk") is True:
            return True
        cid = str(p_dict.get("commodity_id", "")).lower()
        group = str(p_dict.get("group", "")).lower()
        if any(tok in cid for tok in SCOMBROID_SPECIES_TOKENS):
            return True
        names_list: list[str] = []
        for lang_names in p_dict.get("names", {}).values():
            if isinstance(lang_names, list):
                names_list.extend([str(n).lower() for n in lang_names])
        if any(tok in name for tok in SCOMBROID_SPECIES_TOKENS for name in names_list):
            return True
        if "fish" in group and any(tok in cid for tok in SCOMBROID_SPECIES_TOKENS):
            return True
    return False


# ---------------------------------------------------------------------------
# Individual Safety Gates
# ---------------------------------------------------------------------------


def botulinum_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    water_activity: float | None = None,
    ph: float | None = None,
    o2_fraction: float | None = None,
    max_temperature_c: float | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """
    Evaluates Clostridium botulinum neurotoxin hazard in reduced oxygen packaging.

    Per Section 5.4 of BLUEPRINT.md:
    BLOCK when:
        aw > 0.92 AND pH > 4.6 AND O2 < 2% (0.02) AND T_max > 5 °C.

    This is the classic, lethal hazard combination for low-acid foods.
    A BLOCK verdict is strictly non-overridable.
    """
    aw = _extract_water_activity(profile, water_activity)
    ph_val = _extract_ph(profile, ph)
    o2 = _extract_o2_fraction(package, o2_fraction)
    temp = _extract_max_temperature(environment, max_temperature_c)

    if aw > 0.92 and ph_val > 4.6 and o2 < 0.02 and temp > 5.0:
        logger.critical(
            "SAFETY INTERLOCK: C. botulinum hazard (aw=%.3f, pH=%.2f, O2=%.3f, T=%.1f)",
            aw,
            ph_val,
            o2,
            temp,
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_BOTULINUM,
            message_key=(
                "This combination is unsafe. Either guarantee <=5 °C throughout, "
                "or do not remove oxygen. (aw > 0.92, pH > 4.6, O2 < 2%, T > 5 °C "
                "presents a lethal Clostridium botulinum hazard)."
            ),
            is_overridable=False,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_BOTULINUM,
        message_key="botulinum_gate_passed",
        is_overridable=True,
    )


def fresh_cut_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    is_fresh_cut: bool | None = None,
    is_rop: bool | None = None,
    o2_fraction: float | None = None,
    max_temperature_c: float | None = None,
    state_modifiers: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """
    Enforces cold chain requirements for fresh-cut produce in reduced O2 packaging.

    Fresh-cut produce packaged in reduced-oxygen packaging requires cold chain <= 5 °C.
    """
    is_cut = _is_fresh_cut_commodity(profile, state_modifiers, is_fresh_cut)
    o2 = _extract_o2_fraction(package, o2_fraction)
    rop = _is_reduced_oxygen_packaging(package, o2, is_rop)
    temp = _extract_max_temperature(environment, max_temperature_c)

    if is_cut and rop and temp > 5.0:
        logger.critical(
            "SAFETY INTERLOCK: Fresh-cut in ROP above 5 C (T=%.1fC, O2=%.3f)",
            temp,
            o2,
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_FRESH_CUT,
            message_key=(
                f"Fresh-cut produce in reduced-oxygen packaging requires an "
                f"enforced cold chain <= 5 °C. Journey temperature of {temp:.1f} °C "
                f"violates psychrotrophic pathogen safety thresholds."
            ),
            is_overridable=False,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_FRESH_CUT,
        message_key="fresh_cut_gate_passed",
        is_overridable=True,
    )


def light_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    light_sensitive: bool | None = None,
    is_opaque: bool | None = None,
    uv_blocking: bool | None = None,
    light_barrier_od: float | None = None,
    commodity_id: str | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """
    Evaluates light exposure safety and quality barriers.

    For potato specifically (Solanum tuberosum), light exposure drives toxic
    glycoalkaloid (solanine/chaconine) formation, resulting in a mandatory BLOCK.
    """
    is_potato = _is_potato_commodity(profile, commodity_id)
    is_protected = _has_opaque_or_uv_protection(
        package, is_opaque, uv_blocking, light_barrier_od
    )

    sensitive = light_sensitive
    if sensitive is None and profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        sensitive = bool(p_dict.get("light_sensitive", False))

    if is_potato and not is_protected:
        if package is None and is_opaque is None and uv_blocking is None and light_barrier_od is None:
            return SafetyVerdict(
                status=SafetyStatus.WARN,
                rule_id=RULE_LIGHT_POTATO,
                message_key="{commodity_name} requires opaque or UV-blocking packaging to prevent solanine formation.",
                is_overridable=True,
            )
        logger.critical(
            "SAFETY INTERLOCK: Potato in transparent pack (solanine hazard)"
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_LIGHT_POTATO,
            message_key=(
                "{commodity_name} exposed to light develops toxic steroidal glycoalkaloids "
                "(alpha-solanine and alpha-chaconine) causing gastrointestinal and "
                "neurological poisoning. Packaging MUST be fully opaque (OD >= 1.5) "
                "or contain an approved UV-absorber (blocking 290-400 nm)."
            ),
            is_overridable=False,
        )

    if sensitive and not is_protected:
        return SafetyVerdict(
            status=SafetyStatus.WARN,
            rule_id=RULE_LIGHT_GENERAL,
            message_key=(
                "Commodity is flagged light-sensitive. Light exposure induces rapid "
                "degradation. An opaque or UV-blocking barrier is recommended."
            ),
            is_overridable=True,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_LIGHT_GENERAL,
        message_key="light_gate_passed",
        is_overridable=True,
    )


def acidified_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    is_acidified: bool | None = None,
    ph: float | None = None,
    max_temperature_c: float | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """Enforces equilibrium pH regulations for acidified foods (21 CFR 114 / FSSAI)."""
    acidified = is_acidified
    if acidified is None and profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if p_dict.get("is_acidified") is True:
            acidified = True
        cid = str(p_dict.get("commodity_id", "")).lower()
        group = str(p_dict.get("group", "")).lower()
        if "acidified" in cid or "acidified" in group:
            acidified = True
        elif any(
            k in cid for k in ["pickled", "pickle", "salsa", "relish", "sauerkraut"]
        ):
            acidified = True

    ph_val = _extract_ph(profile, ph)
    temp = _extract_max_temperature(environment, max_temperature_c)

    if acidified and ph_val > 4.60 and temp > 5.0:
        logger.critical(
            "SAFETY INTERLOCK: Acidified food with pH=%.2f > 4.60 at T=%.1fC",
            ph_val,
            temp,
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_ACIDIFIED,
            message_key=(
                f"Acidified food equilibrium pH ({ph_val:.2f}) exceeds 4.60 under "
                f"ambient distribution ({temp:.1f} °C). Violates 21 CFR 114 / FSSAI "
                f"safety limits and permits Clostridium botulinum spore outgrowth."
            ),
            is_overridable=False,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_ACIDIFIED,
        message_key="acidified_gate_passed",
        is_overridable=True,
    )


def histamine_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    is_scombroid: bool | None = None,
    max_temperature_c: float | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """Enforces strict cold chain to prevent histamine formation in scombroid fish."""
    scombroid = _is_scombroid_fish(profile, is_scombroid)
    temp = _extract_max_temperature(environment, max_temperature_c)

    if scombroid and temp > 5.0:
        logger.critical(
            "SAFETY INTERLOCK: Scombroid fish exposed to abuse temperature (T=%.1fC)",
            temp,
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_HISTAMINE,
            message_key=(
                f"Scombroid-prone fish exposed to journey temperature > 5 °C "
                f"(got {temp:.1f} °C). Permits rapid bacterial histidine "
                f"decarboxylation and toxic histamine (scombrotoxin) formation, "
                f"which cannot be cured by packaging or cooking."
            ),
            is_overridable=False,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_HISTAMINE,
        message_key="histamine_gate_passed",
        is_overridable=True,
    )


def allergen_crosscontact_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    *,
    allergen_free_claimed: bool | None = None,
    package_has_allergen_material: bool | None = None,
    shared_line_unsegregated: bool | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """Evaluates packaging allergen cross-contact and direct-contact hazards."""
    is_allergen_free = allergen_free_claimed
    if is_allergen_free is None and profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        cclass = str(p_dict.get("commodity_class", "")).lower()
        if any(
            term in cclass
            for term in ["allergen_free", "gluten_free", "dairy_free", "peanut_free"]
        ):
            is_allergen_free = True

    has_allergen_mat = package_has_allergen_material
    if has_allergen_mat is None and package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        layers = [str(l_name).lower() for l_name in pkg_dict.get("layer_stack", [])]
        for l_name in layers:
            if any(tok in l_name for tok in ALLERGEN_MATERIAL_TOKENS):
                has_allergen_mat = True
                break

    has_unsegregated_line = bool(shared_line_unsegregated)

    if (is_allergen_free and has_allergen_mat) or (
        is_allergen_free and has_unsegregated_line
    ):
        logger.critical(
            "SAFETY INTERLOCK: Allergen cross-contact hazard for allergen-free product"
        )
        return SafetyVerdict(
            status=SafetyStatus.BLOCK,
            rule_id=RULE_ALLERGEN,
            message_key=(
                "Allergen cross-contact hazard detected: Direct contact with "
                "allergen-derived packaging materials or shared unsegregated line "
                "violates food safety claims."
            ),
            is_overridable=False,
        )

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id=RULE_ALLERGEN,
        message_key="allergen_crosscontact_gate_passed",
        is_overridable=True,
    )


# ---------------------------------------------------------------------------
# Master Safety Interlock (Runs Before & Independently of Quality)
# ---------------------------------------------------------------------------


def safety_gate(
    profile: CommodityProfile | dict[str, Any] | None = None,
    environment: Environment | dict[str, Any] | None = None,
    package: PackageCandidate | dict[str, Any] | None = None,
    **kwargs: Any,
) -> SafetyVerdict:
    """
    Executes master safety interlock suite before quality prediction per Section 5.4.

    Evaluates all 6 independent gates:
    1. botulinum_gate
    2. fresh_cut_gate
    3. light_gate
    4. acidified_gate
    5. histamine_gate
    6. allergen_crosscontact_gate

    If ANY gate returns a BLOCK verdict, safety_gate immediately returns that BLOCK
    with is_overridable = False. A quality model must NEVER mask a safety failure.
    """
    gate_evals: list[SafetyVerdict] = [
        botulinum_gate(profile, environment, package, **kwargs),
        fresh_cut_gate(profile, environment, package, **kwargs),
        light_gate(profile, environment, package, **kwargs),
        acidified_gate(profile, environment, package, **kwargs),
        histamine_gate(profile, environment, package, **kwargs),
        allergen_crosscontact_gate(profile, environment, package, **kwargs),
    ]

    warn_verdict: SafetyVerdict | None = None

    for verdict in gate_evals:
        if verdict.status == SafetyStatus.BLOCK:
            return verdict
        if verdict.status == SafetyStatus.WARN and warn_verdict is None:
            warn_verdict = verdict

    if warn_verdict is not None:
        return warn_verdict

    return SafetyVerdict(
        status=SafetyStatus.PASS,
        rule_id="SAFE-ALL-PASS",
        message_key="all_safety_gates_passed",
        is_overridable=True,
    )


def enforce_safety_interlock(
    verdict: SafetyVerdict,
    mode: str = "Standard",
) -> None:
    """
    Enforces non-negotiable rejection of any safety BLOCK.

    Raises PermissionError if a caller attempts to bypass a BLOCK verdict in any
    mode, including 'Expert' mode.
    """
    if verdict.status == SafetyStatus.BLOCK:
        raise PermissionError(
            f"Safety interlock violation: {verdict.rule_id} ({verdict.message_key}). "
            f"A BLOCK safety verdict is strictly non-overridable and cannot be "
            f"bypassed in any mode, including '{mode}' mode."
        )
