"""
Post-Harvest State Modifiers and Elapsed Shelf-Life Accounting for Aavaran.

Implements Section 4.2 of BLUEPRINT.md:
- Applies physiological state modifiers (cut, washed, bruised, cured,
  ripeness, blanched) producing ranges rather than single point values.
- consume_elapsed_life(profile, hours_elapsed, temperature): converts elapsed
  real time into equivalent days at reference temperature using Q10, then
  subtracts it from potential shelf life.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from engine.types import CommodityProfile, Provenance, SourceType

logger = logging.getLogger(__name__)

# State modifier multiplier and parameter ranges from Section 4.2 of BLUEPRINT.md
MODIFIER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "cut": {
        "respiration_mult": (3.0, 7.0),
        "aw_delta": 0.01,
        "microbial_risk": "high",
        "new_failure": "enzymatic_browning",
        "max_ambient_hours": 4.0,
        "requires_antifog": True,
        "forces_chilled": True,
        "description": "Wound response multiplies respiration 3-7x",
    },
    "sliced": {
        "respiration_mult": (3.0, 7.0),
        "aw_delta": 0.01,
        "microbial_risk": "high",
        "new_failure": "enzymatic_browning",
        "max_ambient_hours": 4.0,
        "requires_antifog": True,
        "forces_chilled": True,
        "description": "Slicing damage multiplies respiration 3-7x",
    },
    "peeled": {
        "respiration_mult": (3.0, 7.0),
        "aw_delta": 0.01,
        "microbial_risk": "high",
        "new_failure": "enzymatic_browning",
        "max_ambient_hours": 4.0,
        "requires_antifog": True,
        "forces_chilled": True,
        "description": "Peeling removes protective epidermis barrier",
    },
    "bruised": {
        "respiration_mult": (1.3, 2.0),
        "ethylene_mult": (2.0, 4.0),
        "life_mult": (0.5, 0.8),
        "new_failure": "rot_entry_point",
        "requires_antifog": False,
        "description": "Mechanical damage accelerates respiration and ethylene",
    },
    "mechanically_damaged": {
        "respiration_mult": (1.3, 2.0),
        "ethylene_mult": (2.0, 4.0),
        "life_mult": (0.5, 0.8),
        "new_failure": "rot_entry_point",
        "requires_antifog": False,
        "description": "Mechanical damage accelerates senescence and rot risk",
    },
    "washed": {
        "respiration_mult": (1.0, 1.0),
        "free_surface_moisture": True,
        "requires_antifog": True,
        "description": "Free surface moisture creates condensation risk",
    },
    "hydro_cooled": {
        "respiration_mult": (1.0, 1.0),
        "free_surface_moisture": True,
        "requires_antifog": True,
        "description": "Hydro-cooling leaves residual moisture on surface",
    },
    "cured": {
        "respiration_mult": (0.6, 0.9),
        "life_mult": (1.5, 3.0),
        "unlocks_mesh": True,
        "description": "Suberised wound periderm extends life 1.5-3x",
    },
    "ripeness": {
        "respiration_mult": (2.0, 3.0),
        "ethylene_autocatalysis": True,
        "scavenger_recommended": "KMnO4",
        "description": "Climacteric peak increases respiration 2-3x",
    },
    "ripe": {
        "respiration_mult": (2.0, 3.0),
        "ethylene_autocatalysis": True,
        "scavenger_recommended": "KMnO4",
        "description": "Ripe state increases respiration 2-3x",
    },
    "blanched": {
        "respiration_mult": (0.0, 0.0),
        "inactivates_enzymes": True,
        "switches_to_barrier": True,
        "description": "Thermal treatment stops respiration completely",
    },
    "thermally_treated": {
        "respiration_mult": (0.0, 0.0),
        "inactivates_enzymes": True,
        "switches_to_barrier": True,
        "description": "Enzymes inactivated; product becomes non-respiring",
    },
}


class StateModifierResult(BaseModel):
    """Result of applying state modifiers to a commodity profile."""

    original_commodity_id: str
    states_applied: list[str] = Field(default_factory=list)
    respiration_multiplier_range: tuple[float, float] = (1.0, 1.0)
    aw_delta: float = 0.0
    new_failure_modes: list[str] = Field(default_factory=list)
    requires_antifog: bool = False
    forces_chilled_chain: bool = False
    notes: list[str] = Field(default_factory=list)


class ElapsedLifeResult(BaseModel):
    """Result of consuming shelf life elapsed at a given temperature."""

    hours_elapsed: float
    temperature_c: float
    ref_temperature_c: float
    q10: float
    acceleration_factor: float
    consumed_equivalent_days: float
    potential_life_days: float
    remaining_life_days: float
    is_expired: bool
    note: str


def apply_modifiers(
    profile: CommodityProfile,
    modifiers: list[str] | dict[str, Any] | None = None,
) -> tuple[CommodityProfile, StateModifierResult]:
    """
    Applies post-harvest state modifiers to a CommodityProfile.
    Updates respiration rate bounds, water activity, failure modes, and flags.
    """
    if not modifiers:
        mod_result = StateModifierResult(
            original_commodity_id=profile.commodity_id,
            states_applied=[],
            respiration_multiplier_range=(1.0, 1.0),
        )
        return profile, mod_result

    mod_names: list[str] = []
    if isinstance(modifiers, list):
        mod_names = [str(m).strip().lower() for m in modifiers]
    elif isinstance(modifiers, dict):
        mod_names = [str(m).strip().lower() for m in modifiers.keys()]

    resp_min_mult = 1.0
    resp_max_mult = 1.0
    aw_delta_total = 0.0
    new_failures: list[str] = []
    requires_antifog = False
    forces_chilled = False
    notes: list[str] = []

    for name in mod_names:
        matched_def = MODIFIER_DEFINITIONS.get(name)
        if not matched_def:
            if profile.state_modifiers and name in profile.state_modifiers:
                spec = profile.state_modifiers[name]
                if isinstance(spec, dict):
                    rx = spec.get("respiration_x", [1.0, 1.0])
                    if isinstance(rx, list) and len(rx) == 2:
                        resp_min_mult *= float(rx[0])
                        resp_max_mult *= float(rx[1])
                    if "aw_delta" in spec:
                        aw_delta_total += float(spec["aw_delta"])
                    if "new_failure" in spec:
                        new_failures.append(str(spec["new_failure"]))
                    if spec.get("requires_antifog"):
                        requires_antifog = True
                    notes.append(f"Applied profile-specific modifier '{name}'")
                    continue

        if matched_def:
            r_min, r_max = matched_def.get("respiration_mult", (1.0, 1.0))
            resp_min_mult *= r_min
            resp_max_mult *= r_max
            aw_delta_total += matched_def.get("aw_delta", 0.0)
            if matched_def.get("new_failure"):
                new_failures.append(matched_def["new_failure"])
            if matched_def.get("requires_antifog"):
                requires_antifog = True
            if matched_def.get("forces_chilled"):
                forces_chilled = True
            notes.append(f"Applied modifier '{name}': {matched_def['description']}")

    p_data = profile.model_dump()

    if profile.respiration_ref_rate and profile.respiration_ref_rate.value is not None:
        base_rate = float(profile.respiration_ref_rate.value)
        orig_low = profile.respiration_ref_rate.range_low or base_rate
        orig_high = profile.respiration_ref_rate.range_high or base_rate
        new_low = round(orig_low * resp_min_mult, 2)
        new_high = round(orig_high * resp_max_mult, 2)
        p_data["respiration_ref_rate"] = Provenance(
            value=new_high,
            range_low=new_low,
            range_high=new_high,
            unit=profile.respiration_ref_rate.unit or "mg CO2/kg·h",
            source_id=profile.respiration_ref_rate.source_id,
            source_type=SourceType.MODEL_ESTIMATE,
            resolution_level=profile.respiration_ref_rate.resolution_level,
            confidence=max(
                0.1, (profile.respiration_ref_rate.confidence or 0.8) * 0.75
            ),
            note=(
                f"Respiration modified by {resp_min_mult:.1f}-{resp_max_mult:.1f}x "
                f"due to states: {', '.join(mod_names)}"
            ),
        )

    if (
        profile.water_activity
        and profile.water_activity.value is not None
        and aw_delta_total > 0
    ):
        base_aw = float(profile.water_activity.value)
        new_aw = min(1.0, round(base_aw + aw_delta_total, 3))
        p_data["water_activity"] = Provenance(
            value=new_aw,
            range_low=profile.water_activity.range_low,
            range_high=new_aw,
            source_id=profile.water_activity.source_id,
            source_type=SourceType.MODEL_ESTIMATE,
            resolution_level=profile.water_activity.resolution_level,
            confidence=profile.water_activity.confidence,
            note=f"Water activity adjusted by +{aw_delta_total:.3f} from modifiers",
        )

    existing_failures = list(profile.failure_modes)
    for nf in new_failures:
        if nf not in existing_failures:
            existing_failures.append(nf)
    p_data["failure_modes"] = existing_failures

    curr_mods = dict(p_data.get("state_modifiers", {}))
    for m in mod_names:
        curr_mods[m] = MODIFIER_DEFINITIONS.get(m, {})
    p_data["state_modifiers"] = curr_mods

    modified_profile = CommodityProfile.model_validate(p_data)

    result = StateModifierResult(
        original_commodity_id=profile.commodity_id,
        states_applied=mod_names,
        respiration_multiplier_range=(round(resp_min_mult, 2), round(resp_max_mult, 2)),
        aw_delta=round(aw_delta_total, 3),
        new_failure_modes=new_failures,
        requires_antifog=requires_antifog,
        forces_chilled_chain=forces_chilled,
        notes=notes,
    )
    return modified_profile, result


def consume_elapsed_life(
    profile: CommodityProfile,
    hours_elapsed: float,
    temperature_c: float,
    *,
    ref_temperature_c: float | None = None,
    q10: float = 2.0,
) -> ElapsedLifeResult:
    """
    Converts elapsed real time into equivalent days at reference temperature using Q10.
    """
    hours_elapsed = max(0.0, float(hours_elapsed))
    temperature_c = float(temperature_c)

    if ref_temperature_c is not None:
        t_ref = float(ref_temperature_c)
    elif profile.storage_optimum_t_c and profile.storage_optimum_t_c.value is not None:
        opt_val = profile.storage_optimum_t_c.value
        if isinstance(opt_val, list):
            t_ref = float(opt_val[0])
        else:
            t_ref = float(opt_val)
    elif profile.respiration_ref_t_c and profile.respiration_ref_t_c.value is not None:
        t_ref = float(profile.respiration_ref_t_c.value)
    else:
        t_ref = 5.0

    temp_diff = temperature_c - t_ref
    acceleration = q10 ** (temp_diff / 10.0)
    equiv_hours = hours_elapsed * acceleration
    consumed_days = equiv_hours / 24.0

    potential_days = 30.0
    if profile.storage_life_days and profile.storage_life_days.value is not None:
        life_val = profile.storage_life_days.value
        if isinstance(life_val, list):
            potential_days = float(life_val[0])
        else:
            potential_days = float(life_val)
    elif "cut" in profile.state_modifiers:
        potential_days = 5.0

    remaining_days = max(0.0, potential_days - consumed_days)
    is_expired = remaining_days <= 0.0

    note = (
        f"{hours_elapsed:.1f}h at {temperature_c:.1f}°C (accel {acceleration:.2f}x, "
        f"Q10={q10:.1f}, T_ref={t_ref:.1f}°C) consumed {consumed_days:.2f} eq-days. "
        f"Remaining: {remaining_days:.2f} days."
    )
    if is_expired:
        note += " Expired: all potential shelf life has been consumed."

    return ElapsedLifeResult(
        hours_elapsed=round(hours_elapsed, 2),
        temperature_c=round(temperature_c, 2),
        ref_temperature_c=round(t_ref, 2),
        q10=round(q10, 2),
        acceleration_factor=round(acceleration, 3),
        consumed_equivalent_days=round(consumed_days, 2),
        potential_life_days=round(potential_days, 2),
        remaining_life_days=round(remaining_days, 2),
        is_expired=is_expired,
        note=note,
    )
