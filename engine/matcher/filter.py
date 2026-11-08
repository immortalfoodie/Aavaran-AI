"""
Hard filtering constraints for candidate packaging structures.

Implements Section 6.2, 7.0, and Matcher specifications of BLUEPRINT.md:
- Barrier requirement not met (insufficient shelf life / permeation).
- Service temperature out of range (e.g. standard LLDPE sealant in a retort process).
- Fat contact incompatibility (contact layer swelling or cracking with oils/fats).
- Machine incompatibility with user's filling line (VFFS, HFFS, thermoformer, pouch sealer).
- Metal detection required but structure contains foil or metallisation.
- Microwave required but structure contains aluminium foil.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from engine.types import (
    CommodityProfile,
    PackageCandidate,
    PackGeometry,
    RequirementVector,
)

logger = logging.getLogger(__name__)

# Keywords for aluminium foil layers
FOIL_LAYER_KEYWORDS: Set[str] = {
    "alufoil",
    "al foil",
    "foil",
    "aluminum",
    "aluminium",
    "al_foil",
}

# Keywords for metallised layers (vacuum deposited aluminium)
METALLISED_LAYER_KEYWORDS: Set[str] = {
    "vmbet",
    "vmpet",
    "vmbopp",
    "vmcpp",
    "metpet",
    "metbopp",
    "metallised",
    "metallized",
}

# Materials unsuitable for retort direct contact (melts or delaminates at 121 °C)
RETORT_INCOMPATIBLE_SEALANTS: Set[str] = {
    "lldpe",
    "ldpe",
    "pe",
    "eva",
    "plb",
    "pla",
    "pbat",
}


class FilterVerdict(BaseModel):
    """Result of hard filtering for an individual candidate."""

    candidate_id: str
    passed: bool
    reasons: List[str] = Field(default_factory=list)
    failed_constraints: List[str] = Field(default_factory=list)


class FilterResult(BaseModel):
    """Aggregated output of candidate filtering."""

    survivors: List[PackageCandidate]
    rejected: List[PackageCandidate]
    verdicts: List[FilterVerdict]


def _get_sealant_layer(candidate: PackageCandidate) -> str:
    """Identify the inner food contact layer (sealant), typically the last layer."""
    if candidate.sealant_layer:
        return candidate.sealant_layer.strip().lower()
    if candidate.layer_stack:
        return candidate.layer_stack[-1].strip().lower()
    return ""


def _contains_foil(candidate: PackageCandidate) -> bool:
    """Check if structure contains solid aluminium foil."""
    for layer in candidate.layer_stack:
        l_clean = re.sub(r"[^a-zA-Z0-9]", "", layer.lower())
        if any(fk in l_clean for fk in ["alufoil", "foil", "aluminum", "aluminium"]) and "alox" not in l_clean:
            return True
    return False


def _contains_metallisation(candidate: PackageCandidate) -> bool:
    """Check if structure contains vacuum metallised layer."""
    for layer in candidate.layer_stack:
        l_clean = re.sub(r"[^a-zA-Z0-9]", "", layer.lower())
        if any(mk in l_clean for mk in ["vmpet", "vmbopp", "vmcpp", "metallised", "metallized"]):
            return True
    return False


def filter_candidate(
    candidate: PackageCandidate,
    requirements: RequirementVector,
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    pack_geometry: Optional[Union[PackGeometry, Dict[str, Any]]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> FilterVerdict:
    """
    Evaluate all hard constraints against a single candidate structure.
    Returns FilterVerdict indicating pass/fail with explicit reasons.
    """
    cand_id = candidate.id or "/".join(candidate.layer_stack)
    reasons: List[str] = []
    failed_constraints: List[str] = []

    # Parse pack geometry and constraints
    if isinstance(pack_geometry, dict):
        geom = PackGeometry(**pack_geometry)
    elif isinstance(pack_geometry, PackGeometry):
        geom = pack_geometry
    else:
        geom = PackGeometry()

    c_dict = constraints or {}
    filling_line = c_dict.get("filling_line") or geom.filling_line
    metal_detection_req = c_dict.get("metal_detection_required", geom.metal_detection_required)
    microwave_req = c_dict.get("microwave_required", geom.microwave_required)
    process = (requirements.process or geom.process or c_dict.get("process") or "ambient").lower()

    # -----------------------------------------------------------------------
    # Constraint 1: Barrier requirement not met
    # -----------------------------------------------------------------------
    if requirements.regime == "respiring_produce":
        # Respiring produce MAP: films must allow minimum gas exchange to prevent suffocation / botulinum
        if requirements.min_otr is not None:
            cand_otr = candidate.measured_otr if candidate.measured_otr is not None else 0.0
            # Continuous non-perforated film with OTR < 100 cc cannot sustain respiring produce
            if cand_otr < 50.0 and not requirements.perforation_required:
                reasons.append(
                    f"Barrier constraint: Candidate OTR ({cand_otr} cc/m2.day) is a hermetic barrier, "
                    "which suffocates respiring produce and creates an anaerobic botulinum hazard."
                )
                failed_constraints.append("BARRIER_UNSUITABLE_HERMETIC")
    else:
        # Non-respiring barrier: candidate must provide sufficient moisture and oxygen barrier
        if requirements.max_wvtr is not None and candidate.measured_wvtr is not None:
            # If candidate WVTR is more than 3.5x higher than required, it drastically fails
            # e.g. for namkeen requiring ~0.6, films with WVTR > 2.5 fail (like unmetallised PP/PE with WVTR 3.5 - 16)
            wvtr_limit = max(requirements.max_wvtr * 3.5, 2.0)
            if candidate.measured_wvtr > wvtr_limit:
                reasons.append(
                    f"Barrier constraint: Candidate WVTR ({candidate.measured_wvtr:.2f} g/m2.day) "
                    f"exceeds allowable design ceiling ({wvtr_limit:.2f} g/m2.day), failing moisture shelf life."
                )
                failed_constraints.append("BARRIER_WVTR_EXCEEDED")

        if requirements.max_otr is not None and candidate.measured_otr is not None:
            # If candidate OTR exceeds allowable ceiling for an oxidation-sensitive product
            otr_limit = max(requirements.max_otr * 3.5, 30.0) if requirements.max_otr < 10.0 else 100.0
            if candidate.measured_otr > otr_limit:
                reasons.append(
                    f"Barrier constraint: Candidate OTR ({candidate.measured_otr:.2f} cc/m2.day) "
                    f"exceeds allowable oxygen limit ({otr_limit:.2f} cc/m2.day) for an oxidation-sensitive product."
                )
                failed_constraints.append("BARRIER_OTR_EXCEEDED")

    # Light barrier constraint for photo-sensitive goods
    if requirements.light_barrier_od and requirements.light_barrier_od >= 2.0:
        has_light_barrier = _contains_foil(candidate) or _contains_metallisation(candidate)
        if not has_light_barrier:
            reasons.append(
                "Light barrier constraint: Product is photo-sensitive. "
                "Structure is transparent and lacks required light barrier (metallisation or foil)."
            )
            failed_constraints.append("LIGHT_BARRIER_UNMET")

    # -----------------------------------------------------------------------
    # Constraint 2: Service temperature out of range
    # -----------------------------------------------------------------------
    sealant = _get_sealant_layer(candidate)
    if process == "retort":
        # Retort sterilization runs at 121 °C (250 °F)
        # Standard LLDPE/LDPE melts at 105-115 °C; retort requires cast PP (CPP) or retort nylon
        if any(pe in sealant for pe in RETORT_INCOMPATIBLE_SEALANTS) and "cpp" not in sealant:
            reasons.append(
                f"Service temperature out of range: Standard '{sealant.upper()}' sealant layer cannot withstand "
                "121 °C retort processing without delamination/rupture. Requires retort-grade CPP."
            )
            failed_constraints.append("SERVICE_TEMP_RETORT_INCOMPATIBLE")

    elif process == "hot_fill":
        # Hot-fill runs at 85-95 °C; unoriented LDPE may soften excessively
        if "ldpe" in sealant and "lldpe" not in sealant and "hdpe" not in sealant and "cpp" not in sealant:
            reasons.append(
                "Service temperature out of range: LDPE sealant softens below 85 °C hot-fill temperature."
            )
            failed_constraints.append("SERVICE_TEMP_HOTFILL_INCOMPATIBLE")

    elif process == "frozen":
        # Standard PP homopolymer becomes brittle around 0 °C to -10 °C
        if sealant == "cpp" and "pe" not in candidate.layer_stack and "lldpe" not in candidate.layer_stack:
            # Pure homopolymer without impact modifier
            pass  # Note: copolymer CPP is often fine, so WARN rather than hard block unless specified

    # -----------------------------------------------------------------------
    # Constraint 3: Fat contact incompatibility
    # -----------------------------------------------------------------------
    if requirements.fat_contact:
        # High fat commodities (fried snacks, ghee, butter, meat)
        # Direct contact layer must not swell or stress-crack with oils
        # Incompatible: unoriented polystyrene, plasticized PVC without barrier
        if any(bad in sealant for bad in ["pvc", "ps", "polystyrene"]):
            reasons.append(
                f"Fat contact incompatibility: Food contact layer '{sealant.upper()}' swells or stress-cracks "
                "in direct contact with fatty/oily food products."
            )
            failed_constraints.append("FAT_CONTACT_INCOMPATIBLE")

    # -----------------------------------------------------------------------
    # Constraint 4: Machine incompatibility with filling line
    # -----------------------------------------------------------------------
    if filling_line:
        line_clean = str(filling_line).strip().lower().replace("-", "").replace("_", "").replace(" ", "")
        # Manual impulse sealer can seal all standard thermoplastic sealants
        if line_clean in ["manual", "manualsealer", "impulse", "hand"]:
            is_compat = True
        elif candidate.machine_compatibility:
            compat_clean = [
                m.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
                for m in candidate.machine_compatibility
            ]
            # Match if line_clean matches any compatible tag (e.g. "vffs" in "vffs", "pouch" in "preformedpouch")
            is_compat = any(
                line_clean in tag or tag in line_clean
                for tag in compat_clean
            )
        else:
            is_compat = True

        if not is_compat:
            reasons.append(
                f"Machine incompatibility: Candidate is certified for {candidate.machine_compatibility}, "
                f"which does not support the user's '{filling_line}' filling line."
            )
            failed_constraints.append("MACHINE_LINE_INCOMPATIBLE")

    # -----------------------------------------------------------------------
    # Constraint 5: Metal detection required but structure contains foil or metallisation
    # -----------------------------------------------------------------------
    if metal_detection_req:
        has_foil = _contains_foil(candidate)
        has_metal = _contains_metallisation(candidate)
        if has_foil or has_metal:
            metal_type = "aluminium foil" if has_foil else "vacuum metallisation (VMPET/VMBOPP)"
            reasons.append(
                f"Metal detection required: Structure contains {metal_type}, which trips "
                "inline metal detectors after packaging. Use transparent barrier (AlOx, EVOH) instead."
            )
            failed_constraints.append("METAL_DETECTION_INCOMPATIBLE")

    # -----------------------------------------------------------------------
    # Constraint 6: Microwave required but structure contains foil
    # -----------------------------------------------------------------------
    if microwave_req:
        if _contains_foil(candidate):
            reasons.append(
                "Microwave required: Structure contains solid aluminium foil which causes electrical arcing "
                "and fire hazard during microwave heating. Use microwave-safe barrier (AlOx-PET, SiOx, EVOH)."
            )
            failed_constraints.append("MICROWAVE_FOIL_INCOMPATIBLE")

    passed = len(failed_constraints) == 0
    return FilterVerdict(
        candidate_id=cand_id,
        passed=passed,
        reasons=reasons,
        failed_constraints=failed_constraints,
    )


def filter_candidates(
    candidates: List[PackageCandidate],
    requirements: RequirementVector,
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    pack_geometry: Optional[Union[PackGeometry, Dict[str, Any]]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> FilterResult:
    """
    Run all hard constraints across the candidate pool.
    Separates surviving candidates from rejected candidates with full diagnostic audit logs.
    """
    survivors: List[PackageCandidate] = []
    rejected: List[PackageCandidate] = []
    verdicts: List[FilterVerdict] = []

    for cand in candidates:
        verdict = filter_candidate(
            candidate=cand,
            requirements=requirements,
            profile=profile,
            pack_geometry=pack_geometry,
            constraints=constraints,
        )
        verdicts.append(verdict)
        if verdict.passed:
            survivors.append(cand)
        else:
            rejected.append(cand)

    logger.info(
        f"Candidate filtering complete: {len(survivors)} passed, {len(rejected)} rejected "
        f"out of {len(candidates)} total candidates."
    )
    return FilterResult(
        survivors=survivors,
        rejected=rejected,
        verdicts=verdicts,
    )
