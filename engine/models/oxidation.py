"""
Oxidation-limited shelf-life and OTR requirement models for Aavaran.

Implements Section 5.2 of BLUEPRINT.md:
- Oxygen budget approach: Q_budget (mg O2 / kg product).
- Explicit headspace oxygen modelling (residual O2 from air vs nitrogen flush).
- Permeation flux: OTR * A * delta_p(O2) * t * (1.43 mg/cc).
- required_otr(...) inversion emitting design OTR at standard conditions.
- Provenance and equation tracking with IDs (OX-01, OX-02).
"""

import logging
import math
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from engine.types import CommodityProfile, Environment, PackageCandidate
from engine.units import Q_, ureg

logger = logging.getLogger(__name__)

# Standard density of O2 gas at standard conditions (1 atm, 20 °C)
O2_DENSITY_MG_PER_CC = 1.43  # mg / cc (or mg / mL)
DEFAULT_AIR_O2_FRACTION = 0.209  # 20.9 % O2 in air
DEFAULT_FLUSH_O2_FRACTION = 0.010  # 1.0 % residual O2 with N2 flush


class OxidationShelfLifeResult(BaseModel):
    shelf_life_days: float = Field(..., description="Predicted shelf life in days (or inf)")
    equation_id: str = Field(default="OX-01")
    total_budget_mg: float = Field(..., description="Total allowable O2 absorption budget in mg")
    headspace_o2_mg: float = Field(..., description="Initial O2 mass present in headspace in mg")
    ingress_rate_mg_per_day: float = Field(..., description="O2 permeation rate in mg / day")
    nitrogen_flush_recommended: bool = Field(default=False)
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class OTRRequirementResult(BaseModel):
    required_otr: float = Field(..., description="Maximum allowable OTR in cc / (m2.day.atm)")
    equation_id: str = Field(default="OX-02")
    total_budget_mg: float = Field(..., description="Total allowable O2 absorption budget in mg")
    headspace_o2_mg: float = Field(..., description="Initial O2 mass present in headspace in mg")
    nitrogen_flush_recommended: bool = Field(
        default=False,
        description="True if headspace O2 alone exceeds or dominates budget, making N2 flush essential",
    )
    recommendation_note: Optional[str] = None
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


def shelf_life_oxidation_limited(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    package: Optional[Union[PackageCandidate, Dict[str, Any]]] = None,
    *,
    q_budget_mg_per_kg: Optional[float] = None,
    product_mass_kg: Optional[float] = None,
    headspace_volume_cc: Optional[float] = None,
    headspace_o2_fraction: Optional[float] = None,
    otr: Optional[float] = None,
    pack_area_m2: Optional[float] = None,
    delta_p_atm: Optional[float] = None,
    temperature_c: Optional[float] = None,
) -> OxidationShelfLifeResult:
    """
    Predict oxidation-limited shelf life using the oxygen-budget approach (Equation OX-01).

    O2 available = residual headspace O2 + ingress through film
    ingress(t) = OTR * A * delta_p(O2) * t * (1.43 mg/cc)
    t = (Q_budget * M_product - O2_headspace) / (1.43 * OTR * A * delta_p)
    """
    # 1. Resolve Profile inputs
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if q_budget_mg_per_kg is None:
            # Baseline from fat class in BLUEPRINT.md (typical 5-30 mg/kg)
            q_budget_mg_per_kg = p_dict.get("q_budget_mg_per_kg")
        if product_mass_kg is None:
            product_mass_kg = p_dict.get("product_mass_kg")

    q_budget_mg_per_kg = float(q_budget_mg_per_kg if q_budget_mg_per_kg is not None else 15.0)
    product_mass_kg = float(product_mass_kg if product_mass_kg is not None else 0.10)

    # 2. Resolve Environment inputs
    if environment is not None:
        e_dict = environment if isinstance(environment, dict) else environment.model_dump()
        if temperature_c is None and "temperature" in e_dict and e_dict["temperature"]:
            temperature_c = e_dict["temperature"].get("value")

    temperature_c = float(temperature_c if temperature_c is not None else 25.0)

    # 3. Resolve Package inputs
    if package is not None:
        pkg_dict = package if isinstance(package, dict) else package.model_dump()
        if otr is None:
            otr = pkg_dict.get("measured_otr")
        if pack_area_m2 is None:
            pack_area_m2 = pkg_dict.get("pack_area_m2", 0.055)
        if headspace_volume_cc is None:
            headspace_volume_cc = pkg_dict.get("headspace_volume_cc", 50.0)
        if headspace_o2_fraction is None:
            headspace_o2_fraction = pkg_dict.get("headspace_o2_fraction")

    otr = float(otr if otr is not None else 1.0)
    pack_area_m2 = float(pack_area_m2 if pack_area_m2 is not None else 0.055)
    headspace_volume_cc = float(headspace_volume_cc if headspace_volume_cc is not None else 50.0)
    headspace_o2_fraction = float(
        headspace_o2_fraction if headspace_o2_fraction is not None else DEFAULT_AIR_O2_FRACTION
    )
    delta_p_atm = float(delta_p_atm if delta_p_atm is not None else DEFAULT_AIR_O2_FRACTION)

    inputs_used = {
        "q_budget_mg_per_kg": q_budget_mg_per_kg,
        "product_mass_kg": product_mass_kg,
        "headspace_volume_cc": headspace_volume_cc,
        "headspace_o2_fraction": headspace_o2_fraction,
        "otr": otr,
        "pack_area_m2": pack_area_m2,
        "delta_p_atm": delta_p_atm,
        "temperature_c": temperature_c,
    }

    # Total allowable oxygen absorption budget
    total_budget_mg = q_budget_mg_per_kg * product_mass_kg

    # Headspace oxygen mass
    headspace_o2_vol_cc = headspace_volume_cc * headspace_o2_fraction
    headspace_o2_mg = headspace_o2_vol_cc * O2_DENSITY_MG_PER_CC

    # Ingress rate through film (mg / day)
    ingress_rate_cc_day = otr * pack_area_m2 * delta_p_atm
    ingress_rate_mg_day = ingress_rate_cc_day * O2_DENSITY_MG_PER_CC

    # Check if headspace O2 already consumes or exceeds budget
    remaining_budget_mg = total_budget_mg - headspace_o2_mg
    flush_recommended = headspace_o2_mg > (0.5 * total_budget_mg)

    if remaining_budget_mg <= 0.0:
        return OxidationShelfLifeResult(
            shelf_life_days=0.0,
            equation_id="OX-01",
            total_budget_mg=float(total_budget_mg),
            headspace_o2_mg=float(headspace_o2_mg),
            ingress_rate_mg_per_day=float(ingress_rate_mg_day),
            nitrogen_flush_recommended=True,
            inputs_used=inputs_used,
        )

    # Perfect barrier (OTR = 0)
    if otr <= 0.0 or ingress_rate_mg_day <= 0.0:
        return OxidationShelfLifeResult(
            shelf_life_days=float("inf"),
            equation_id="OX-01",
            total_budget_mg=float(total_budget_mg),
            headspace_o2_mg=float(headspace_o2_mg),
            ingress_rate_mg_per_day=0.0,
            nitrogen_flush_recommended=flush_recommended,
            inputs_used=inputs_used,
        )

    # Predicted days
    t_days = remaining_budget_mg / ingress_rate_mg_day

    return OxidationShelfLifeResult(
        shelf_life_days=float(t_days),
        equation_id="OX-01",
        total_budget_mg=float(total_budget_mg),
        headspace_o2_mg=float(headspace_o2_mg),
        ingress_rate_mg_per_day=float(ingress_rate_mg_day),
        nitrogen_flush_recommended=flush_recommended,
        inputs_used=inputs_used,
    )


def required_otr(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    target_days: float = 180.0,
    pack_area_m2: float = 0.055,
    product_mass_kg: float = 0.10,
    q_budget_mg_per_kg: float = 15.0,
    headspace_volume_cc: float = 50.0,
    headspace_o2_fraction: float = DEFAULT_AIR_O2_FRACTION,
    delta_p_atm: float = DEFAULT_AIR_O2_FRACTION,
) -> OTRRequirementResult:
    """
    Inverts the oxygen-budget shelf-life model to emit a required film OTR (Equation OX-02).

    OTR_max = (Q_budget * M_product - O2_headspace) / (1.43 * A * delta_p * t)
    """
    if target_days <= 0:
        raise ValueError(f"Target days must be positive, got {target_days}")
    if pack_area_m2 <= 0:
        raise ValueError(f"Pack area must be positive, got {pack_area_m2}")
    if product_mass_kg <= 0:
        raise ValueError(f"Product mass must be positive, got {product_mass_kg}")
    if q_budget_mg_per_kg <= 0:
        raise ValueError(f"Q_budget must be positive, got {q_budget_mg_per_kg}")

    total_budget_mg = q_budget_mg_per_kg * product_mass_kg
    headspace_o2_vol_cc = headspace_volume_cc * headspace_o2_fraction
    headspace_o2_mg = headspace_o2_vol_cc * O2_DENSITY_MG_PER_CC

    remaining_budget_mg = total_budget_mg - headspace_o2_mg

    inputs_used = {
        "target_days": target_days,
        "pack_area_m2": pack_area_m2,
        "product_mass_kg": product_mass_kg,
        "q_budget_mg_per_kg": q_budget_mg_per_kg,
        "headspace_volume_cc": headspace_volume_cc,
        "headspace_o2_fraction": headspace_o2_fraction,
        "delta_p_atm": delta_p_atm,
    }

    # If headspace alone consumes the budget, no film can achieve the target without flushing
    if remaining_budget_mg <= 0.0:
        note = (
            f"Headspace oxygen ({headspace_o2_mg:.2f} mg) exceeds or equals total budget "
            f"({total_budget_mg:.2f} mg). Nitrogen flush (<1 % O2) is mandatory."
        )
        logger.warning(note)
        return OTRRequirementResult(
            required_otr=0.0,
            equation_id="OX-02",
            total_budget_mg=float(total_budget_mg),
            headspace_o2_mg=float(headspace_o2_mg),
            nitrogen_flush_recommended=True,
            recommendation_note=note,
            inputs_used=inputs_used,
        )

    # Invert: OTR_max = remaining / (1.43 * A * delta_p * target_days)
    denom = O2_DENSITY_MG_PER_CC * pack_area_m2 * delta_p_atm * target_days
    otr_max = remaining_budget_mg / denom

    flush_recommended = headspace_o2_mg > (0.4 * total_budget_mg)
    if flush_recommended:
        note = (
            f"Headspace oxygen ({headspace_o2_mg:.2f} mg) accounts for >40 % of budget. "
            f"A nitrogen flush will relax required film OTR from {otr_max:.2f} cc/m2.day to a more economical spec."
        )
    else:
        note = f"Allowable OTR spec: <= {otr_max:.2f} cc/(m2.day.atm)."

    return OTRRequirementResult(
        required_otr=float(otr_max),
        equation_id="OX-02",
        total_budget_mg=float(total_budget_mg),
        headspace_o2_mg=float(headspace_o2_mg),
        nitrogen_flush_recommended=flush_recommended,
        recommendation_note=note,
        inputs_used=inputs_used,
    )
