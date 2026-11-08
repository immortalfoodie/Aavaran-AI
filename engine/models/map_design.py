"""
Modified Atmosphere Packaging (MAP) design and gas equilibrium models for Aavaran.

Implements Section 5.3 of BLUEPRINT.md:
- Steady-state oxygen and carbon dioxide transmission rate derivation (OTR_req, CO2TR_req).
- Selectivity ratio calculation (beta_required) and three-way classification (FILM, PERFORATION, IMPOSSIBLE).
- Micro-perforation sizing via Fickian diffusion with end-correction (L_eff = L + 1.18r), rounding hole count UP.
- Coupled steady-state in-pack equilibrium atmosphere solver using scipy.optimize.brentq.
- Hard, non-negotiable safety clamps:
    * In-pack equilibrium O2 >= 2.0 % (botulinum and anaerobic fermentation floor).
    * In-pack CO2 <= commodity injury threshold from KB.
    * Structured NoSolution result returned when no physical solution exists inside clamps.
- Unit testing anchors:
    * Fresh-cut pineapple validation: OTR ~ 7,000 - 13,000 mL/(m2.day.atm), CO2TR ~ 14,000 - 24,000 mL/(m2.day.atm).
    * Perforation selectivity ~ 0.78 (diffusivity ratio D_CO2 / D_O2 = 0.160 / 0.205).
    * Polyolefin film selectivity beta in [3.0, 6.0].
"""

import enum
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field
import scipy.optimize

from engine.types import CommodityProfile, PackageCandidate
from engine.units import Q_, ureg

logger = logging.getLogger(__name__)

# Non-negotiable safety clamps
MIN_EQUILIBRIUM_O2_FLOOR = 0.02  # 2.0 % minimum internal O2 to prevent botulinum/fermentation
DEFAULT_AIR_O2_FRACTION = 0.209  # 20.9 % O2 in ambient air
DEFAULT_AIR_CO2_FRACTION = 0.0004  # 0.04 % (400 ppm) CO2 in ambient air

# Gas diffusivities in air at 20 °C and 1 atm (cm2 / s)
DIFFUSIVITY_O2_AIR_CM2_S = 0.205  # 0.205 cm2/s = 2.05e-5 m2/s
DIFFUSIVITY_CO2_AIR_CM2_S = 0.160  # 0.160 cm2/s = 1.60e-5 m2/s

# Theoretical perforation selectivity (ratio of diffusivities in air)
PERFORATION_SELECTIVITY = DIFFUSIVITY_CO2_AIR_CM2_S / DIFFUSIVITY_O2_AIR_CM2_S  # ~0.7804878

# Typical continuous polyolefin film selectivity range (P_CO2 / P_O2)
POLYOLEFIN_SELECTIVITY_RANGE = (3.0, 6.0)

# Ideal gas constant in J / (mol · K)
R_GAS_J_PER_MOL_K = 8.314462618


class SelectivityRecommendation(str, enum.Enum):
    FILM = "FILM"
    PERFORATION = "PERFORATION"
    IMPOSSIBLE = "IMPOSSIBLE"


class SelectivityResult(BaseModel):
    """Result of selectivity analysis and classification."""

    beta_required: float = Field(..., description="Required CO2TR / OTR transmission ratio")
    recommendation: SelectivityRecommendation = Field(
        ..., description="Design route: FILM (3-6), PERFORATION (~0.78-1.2), or IMPOSSIBLE"
    )
    reason: str = Field(..., description="Technical justification for the recommendation")
    is_safe: bool = Field(default=True, description="False if target gases violate safety clamps")
    equation_id: str = Field(default="MAP-03")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class OTRRequirementMAPResult(BaseModel):
    required_otr: float = Field(..., description="Target OTR in mL / (m2.day.atm)")
    equation_id: str = Field(default="MAP-01")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class CO2TRRequirementMAPResult(BaseModel):
    required_co2tr: float = Field(..., description="Target CO2TR in mL / (m2.day.atm)")
    equation_id: str = Field(default="MAP-02")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class PerforationResult(BaseModel):
    """Result of micro-perforation sizing using Fickian diffusion with end-correction."""

    hole_count: int = Field(..., description="Number of circular micro-holes (always rounded UP)")
    hole_diameter_um: float = Field(..., description="Hole diameter in micrometers")
    effective_length_um: float = Field(..., description="Effective pore length L_eff = L + 1.18r in um")
    total_pore_area_m2: float = Field(..., description="Total perforation area in m2")
    o2_permeance_ml_day_atm: float = Field(
        ..., description="Total O2 transmission contributed by perforations in mL / (day.atm)"
    )
    equation_id: str = Field(default="MAP-04")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class NoSolution(BaseModel):
    """
    Structured failure result returned when no physical solution exists inside the safety clamps.
    Aavaran never emits a clamped-and-silent answer.
    """

    is_solvable: bool = Field(default=False)
    reason: str = Field(..., description="Clear explanation of why no passive MAP solution exists")
    violation_type: str = Field(..., description="e.g. O2_FLOOR, CO2_CEILING, SELECTIVITY_MISMATCH")
    suggested_action: str = Field(
        ..., description="Alternative strategy (e.g. active N2 flush, vented packaging, cold chain)"
    )
    details: Dict[str, Any] = Field(default_factory=dict)


class EquilibriumAtmosphereResult(BaseModel):
    """Predicted in-pack steady-state atmosphere solved via coupled mass balance."""

    is_solvable: bool = Field(default=True)
    equilibrium_o2: float = Field(..., description="Steady-state internal O2 mole fraction (e.g. 0.04)")
    equilibrium_co2: float = Field(..., description="Steady-state internal CO2 mole fraction (e.g. 0.08)")
    equilibrium_o2_pct: float = Field(..., description="Steady-state internal O2 in %")
    equilibrium_co2_pct: float = Field(..., description="Steady-state internal CO2 in %")
    respiration_rate_o2_ml_kg_h: float = Field(..., description="O2 consumption at equilibrium in mL/(kg.h)")
    respiration_rate_co2_ml_kg_h: float = Field(..., description="CO2 generation at equilibrium in mL/(kg.h)")
    is_safe: bool = Field(default=True)
    safety_notes: List[str] = Field(default_factory=list)
    equation_id: str = Field(default="MAP-05")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Required Gas Transmission Rates (Equations MAP-01 and MAP-02)
# ---------------------------------------------------------------------------

def required_otr(
    respiration_o2: float,
    mass: float,
    area: float,
    y_out: float = DEFAULT_AIR_O2_FRACTION,
    y_in: float = 0.03,
) -> OTRRequirementMAPResult:
    """
    Compute the required film Oxygen Transmission Rate (Equation MAP-01).

        OTR_req * A * (y_out - y_in) = R_O2 * M * 24
        => OTR_req = (R_O2 * M * 24) / [ A * (y_out - y_in) ]

    Args:
        respiration_o2: Produce O2 respiration rate in mL O2 / (kg · h).
        mass: Produce mass in kg.
        area: Package surface area in m2.
        y_out: External O2 mole fraction (default 0.209 atm).
        y_in: Target internal O2 mole fraction (e.g. 0.03 atm). Must be >= 0.02.

    Returns:
        OTRRequirementMAPResult in mL / (m2 · day · atm).
    """
    if y_in < MIN_EQUILIBRIUM_O2_FLOOR:
        raise ValueError(
            f"Safety clamp violation: Target internal O2 fraction ({y_in:.3f}) is below the "
            f"non-negotiable safety floor of {MIN_EQUILIBRIUM_O2_FLOOR:.2f} (2.0 %). "
            "Severe risk of anaerobic fermentation and Clostridium botulinum."
        )

    delta_y = y_out - y_in
    if delta_y <= 0:
        raise ValueError(f"External O2 ({y_out}) must exceed internal O2 ({y_in}) for ingress.")
    if area <= 0 or mass <= 0:
        raise ValueError("Pack area and produce mass must be positive.")

    otr_req = (float(respiration_o2) * float(mass) * 24.0) / (float(area) * delta_y)

    return OTRRequirementMAPResult(
        required_otr=otr_req,
        equation_id="MAP-01",
        inputs_used={
            "respiration_o2_ml_kg_h": respiration_o2,
            "mass_kg": mass,
            "area_m2": area,
            "y_out": y_out,
            "y_in": y_in,
        },
    )


def required_co2tr(
    respiration_co2: float,
    mass: float,
    area: float,
    y_in_co2: float,
    y_out_co2: float = DEFAULT_AIR_CO2_FRACTION,
) -> CO2TRRequirementMAPResult:
    """
    Compute the required film Carbon Dioxide Transmission Rate (Equation MAP-02).

        CO2TR_req * A * (y_in_co2 - y_out_co2) = R_CO2 * M * 24
        => CO2TR_req = (R_CO2 * M * 24) / [ A * (y_in_co2 - y_out_co2) ]

    Args:
        respiration_co2: Produce CO2 respiration rate in mL CO2 / (kg · h).
        mass: Produce mass in kg.
        area: Package surface area in m2.
        y_in_co2: Target internal CO2 mole fraction (e.g. 0.08 atm).
        y_out_co2: External CO2 mole fraction (default 0.0004 atm).

    Returns:
        CO2TRRequirementMAPResult in mL / (m2 · day · atm).
    """
    delta_y = y_in_co2 - y_out_co2
    if delta_y <= 0:
        raise ValueError(f"Internal CO2 ({y_in_co2}) must exceed external CO2 ({y_out_co2}) for egress.")
    if area <= 0 or mass <= 0:
        raise ValueError("Pack area and produce mass must be positive.")

    co2tr_req = (float(respiration_co2) * float(mass) * 24.0) / (float(area) * delta_y)

    return CO2TRRequirementMAPResult(
        required_co2tr=co2tr_req,
        equation_id="MAP-02",
        inputs_used={
            "respiration_co2_ml_kg_h": respiration_co2,
            "mass_kg": mass,
            "area_m2": area,
            "y_in_co2": y_in_co2,
            "y_out_co2": y_out_co2,
        },
    )


# ---------------------------------------------------------------------------
# Selectivity Ratio & Classifier (Equation MAP-03)
# ---------------------------------------------------------------------------

def required_selectivity(
    y_out_o2: float = DEFAULT_AIR_O2_FRACTION,
    y_in_o2: float = 0.03,
    y_in_co2: float = 0.08,
    y_out_co2: float = DEFAULT_AIR_CO2_FRACTION,
    rq: float = 1.0,
    *,
    co2_injury_ceiling: Optional[float] = None,
) -> SelectivityResult:
    """
    Compute required selectivity beta_required = CO2TR_req / OTR_req and classify
    the recommendation into FILM, PERFORATION, or IMPOSSIBLE (Equation MAP-03).

        beta_required = RQ * (y_out_o2 - y_in_o2) / (y_in_co2 - y_out_co2)

    Classification rules:
        - If y_in_o2 < 0.02 or y_in_co2 > co2_injury_ceiling: IMPOSSIBLE (violates safety clamps).
        - If beta_required in [2.8, 6.2]: FILM (continuous polyolefin films with beta ~ 3 to 6).
        - If beta_required in [0.65, 1.4]: PERFORATION (micro-perforations with beta ~ 0.78).
        - Otherwise: IMPOSSIBLE (no passive film or perforation can reconcile gas targets).
    """
    inputs_used = {
        "y_out_o2": y_out_o2,
        "y_in_o2": y_in_o2,
        "y_in_co2": y_in_co2,
        "y_out_co2": y_out_co2,
        "rq": rq,
        "co2_injury_ceiling": co2_injury_ceiling,
    }

    # Safety Clamp 1: O2 floor
    if y_in_o2 < MIN_EQUILIBRIUM_O2_FLOOR:
        return SelectivityResult(
            beta_required=float("nan"),
            recommendation=SelectivityRecommendation.IMPOSSIBLE,
            reason=(
                f"Target O2 ({y_in_o2:.1%}) is below the non-negotiable 2.0% safety floor. "
                "Passive MAP cannot be designed below 2% due to botulinum and fermentation risks."
            ),
            is_safe=False,
            inputs_used=inputs_used,
        )

    # Safety Clamp 2: CO2 injury ceiling
    if co2_injury_ceiling is not None and y_in_co2 > co2_injury_ceiling:
        return SelectivityResult(
            beta_required=float("nan"),
            recommendation=SelectivityRecommendation.IMPOSSIBLE,
            reason=(
                f"Target CO2 ({y_in_co2:.1%}) exceeds the commodity injury threshold ({co2_injury_ceiling:.1%})."
            ),
            is_safe=False,
            inputs_used=inputs_used,
        )

    delta_o2 = y_out_o2 - y_in_o2
    delta_co2 = y_in_co2 - y_out_co2

    if delta_o2 <= 0 or delta_co2 <= 0:
        return SelectivityResult(
            beta_required=float("nan"),
            recommendation=SelectivityRecommendation.IMPOSSIBLE,
            reason="Non-positive driving force for O2 ingress or CO2 egress.",
            is_safe=False,
            inputs_used=inputs_used,
        )

    beta = rq * (delta_o2 / delta_co2)

    # Classification
    if 2.8 <= beta <= 6.2:
        rec = SelectivityRecommendation.FILM
        reason = (
            f"Required selectivity beta={beta:.2f} falls within the typical range for continuous "
            "polyolefin films (beta 3 to 6). A continuous breathable film can satisfy both gas targets."
        )
    elif 0.65 <= beta <= 1.4:
        rec = SelectivityRecommendation.PERFORATION
        reason = (
            f"Required selectivity beta={beta:.2f} is near 1 (perforation gas diffusion selectivity "
            f"D_CO2/D_O2 ~ {PERFORATION_SELECTIVITY:.2f}). Micro-perforation is required."
        )
    else:
        rec = SelectivityRecommendation.IMPOSSIBLE
        reason = (
            f"Required selectivity beta={beta:.2f} cannot be achieved by either standard continuous films "
            "(beta 3-6) or micro-perforations (beta ~0.78). Passive MAP cannot hit both gas targets; "
            "use active N2 flushing or ventilated packaging."
        )

    return SelectivityResult(
        beta_required=beta,
        recommendation=rec,
        reason=reason,
        is_safe=True,
        inputs_used=inputs_used,
    )


# ---------------------------------------------------------------------------
# Micro-Perforation Sizing (Equation MAP-04)
# ---------------------------------------------------------------------------

def perforation_design(
    respiration_o2: float,
    mass: float,
    film_thickness_um: float,
    *,
    hole_diameter_um: Optional[float] = None,
    hole_count: Optional[int] = None,
    y_out: float = DEFAULT_AIR_O2_FRACTION,
    y_in: float = 0.03,
    temperature_c: float = 20.0,
    pressure_atm: float = 1.0,
) -> PerforationResult:
    """
    Size micro-perforations for passive MAP using Fickian diffusion with end-correction (Equation MAP-04).

        N = (R_O2 * M * L_eff) / (D_O2 * A_hole * delta_c_O2)
        A_hole = pi * d^2 / 4
        L_eff = L + 1.18 * r = L + 0.59 * d
        delta_c_O2 = (y_out - y_in) * P / (Rg * T)

    Always rounds hole count UP (math.ceil).
    When hole_count is given, solves the exact quadratic equation for hole_diameter_um.

    Args:
        respiration_o2: Produce O2 consumption in mL O2 / (kg · h).
        mass: Produce mass in kg.
        film_thickness_um: Film thickness L in micrometers (e.g. 25 um).
        hole_diameter_um: Pore diameter d in micrometers (optional if hole_count given).
        hole_count: Number of holes N (optional if hole_diameter_um given).
        y_out: External O2 fraction (0.209).
        y_in: Internal target O2 fraction (>= 0.02).
        temperature_c: Temperature in °C.
        pressure_atm: Total pressure in atm.

    Returns:
        PerforationResult containing hole_count, hole_diameter_um, and pore permeance.
    """
    if y_in < MIN_EQUILIBRIUM_O2_FLOOR:
        raise ValueError(f"Target internal O2 ({y_in:.3f}) cannot be below 2.0% safety floor.")
    if hole_diameter_um is None and hole_count is None:
        raise ValueError("Must provide either hole_diameter_um or hole_count.")

    # Convert units to SI
    t_k = temperature_c + 273.15
    p_pa = pressure_atm * 101325.0
    l_film_m = film_thickness_um * 1e-6
    d_o2_m2_s = DIFFUSIVITY_O2_AIR_CM2_S * 1e-4  # 2.05e-5 m2/s

    # Molar concentration driving force [mol / m3]
    delta_y = y_out - y_in
    delta_c = delta_y * p_pa / (R_GAS_J_PER_MOL_K * t_k)

    # Required O2 flux in mol / s
    # 1 mol of ideal gas occupies V_mol = Rg * T / P [m3 / mol] = (Rg*T/P)*1e6 mL / mol
    v_mol_ml = (R_GAS_J_PER_MOL_K * t_k / p_pa) * 1e6
    r_total_ml_h = respiration_o2 * mass  # mL O2 / h
    r_total_mol_s = (r_total_ml_h / 3600.0) / v_mol_ml

    # Equivalently, in volumetric terms (m3 / s):
    q_vol_total_m3_s = (r_total_ml_h / 3600.0) * 1e-6

    if hole_diameter_um is not None:
        d_m = hole_diameter_um * 1e-6
        r_m = d_m / 2.0
        a_hole_m2 = math.pi * (d_m**2) / 4.0
        # End correction: L_eff = L + 1.18 * r = L + 0.59 * d
        l_eff_m = l_film_m + 1.18 * r_m

        # Flux per hole [mol / s]
        j_hole_mol_s = (d_o2_m2_s * a_hole_m2 * delta_c) / l_eff_m
        if j_hole_mol_s <= 0:
            raise ValueError("Per-hole flux is non-positive.")

        n_float = r_total_mol_s / j_hole_mol_s
        n_holes = math.ceil(n_float)  # Always round UP per BLUEPRINT.md
        final_d_um = float(hole_diameter_um)
    else:
        # Given hole_count N, solve for diameter d
        n_holes = int(hole_count)
        if n_holes <= 0:
            raise ValueError("Hole count must be >= 1.")

        # Total pore resistance relation:
        # r_total_mol_s = N * [ D_O2 * (pi * d^2 / 4) * delta_c ] / (L + 0.59 * d)
        # Let K = r_total_mol_s / (N * D_O2 * delta_c)
        # (pi / 4) * d^2 - 0.59 * K * d - K * L = 0
        # pi * d^2 - 2.36 * K * d - 4 * K * L = 0
        k_val = r_total_mol_s / (n_holes * d_o2_m2_s * delta_c)
        a_quad = math.pi
        b_quad = -2.36 * k_val
        c_quad = -4.0 * k_val * l_film_m

        disc = b_quad**2 - 4.0 * a_quad * c_quad
        if disc < 0:
            raise ValueError("No physical diameter solution for given hole count.")
        d_m = (-b_quad + math.sqrt(disc)) / (2.0 * a_quad)
        final_d_um = d_m * 1e6
        r_m = d_m / 2.0
        a_hole_m2 = math.pi * (d_m**2) / 4.0
        l_eff_m = l_film_m + 1.18 * r_m

    total_pore_area_m2 = n_holes * a_hole_m2
    eff_length_um = l_eff_m * 1e6

    # Total O2 transmission contributed by all perforations in mL / (day · atm)
    # Permeance = (N * D_O2 * A_hole / L_eff) * (P / (Rg*T)) * V_mol * 24 * 3600
    # Note (P / Rg T) * V_mol = 10^6 mL/m3
    rate_ml_s_per_atm = (n_holes * d_o2_m2_s * a_hole_m2 / l_eff_m) * 1e6
    o2_permeance_ml_day_atm = rate_ml_s_per_atm * 86400.0

    return PerforationResult(
        hole_count=n_holes,
        hole_diameter_um=final_d_um,
        effective_length_um=eff_length_um,
        total_pore_area_m2=total_pore_area_m2,
        o2_permeance_ml_day_atm=o2_permeance_ml_day_atm,
        equation_id="MAP-04",
        inputs_used={
            "respiration_o2": respiration_o2,
            "mass_kg": mass,
            "film_thickness_um": film_thickness_um,
            "hole_diameter_um": hole_diameter_um,
            "hole_count": hole_count,
            "y_out": y_out,
            "y_in": y_in,
            "temperature_c": temperature_c,
            "pressure_atm": pressure_atm,
        },
    )


# ---------------------------------------------------------------------------
# Coupled In-Pack Atmosphere Equilibrium Solver (Equation MAP-05)
# ---------------------------------------------------------------------------

def equilibrium_atmosphere(
    film: Optional[Union[PackageCandidate, Dict[str, Any]]] = None,
    produce: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    pack: Optional[Dict[str, Any]] = None,
    *,
    total_otr_ml_day_atm: Optional[float] = None,
    total_co2tr_ml_day_atm: Optional[float] = None,
    film_otr: Optional[float] = None,
    film_co2tr: Optional[float] = None,
    pack_area_m2: Optional[float] = None,
    mass_kg: Optional[float] = None,
    respiration_o2_ml_kg_h: Optional[float] = None,
    rq: float = 1.0,
    km_o2: float = 0.015,
    co2_injury_ceiling: Optional[float] = None,
    y_out_o2: float = DEFAULT_AIR_O2_FRACTION,
    y_out_co2: float = DEFAULT_AIR_CO2_FRACTION,
) -> Union[EquilibriumAtmosphereResult, NoSolution]:
    """
    Solve the coupled steady-state in-pack equilibrium atmosphere using scipy.optimize.brentq.

    At steady state:
        Ingress(O2) = Consumption(O2)
        (OTR_total / 24) * (y_out - y_in) = M * R_O2(y_in)

    Respiration dependence on O2 follows Michaelis-Menten kinetics:
        R_O2(y) = R_max * y / (Km + y)
        where R_max is normalized so R_O2(0.209) matches reference respiration.

    Enforces non-negotiable safety clamps:
        - If equilibrium O2 drops below 2.0% -> returns NoSolution (O2_FLOOR).
        - If equilibrium CO2 exceeds commodity injury ceiling -> returns NoSolution (CO2_CEILING).
        - Aavaran never emits a clamped-and-silent answer!
    """
    inputs_used: Dict[str, Any] = {}

    # 1. Resolve Produce properties
    if produce is not None:
        p_dict = produce if isinstance(produce, dict) else produce.model_dump()
        if respiration_o2_ml_kg_h is None:
            ref_rate = p_dict.get("respiration_ref_rate")
            if ref_rate:
                respiration_o2_ml_kg_h = ref_rate.get("value")
        if mass_kg is None:
            mass_kg = p_dict.get("product_mass_kg")
        if co2_injury_ceiling is None:
            co2_injury_ceiling = p_dict.get("co2_injury_ceiling")

    respiration_o2_ml_kg_h = float(respiration_o2_ml_kg_h if respiration_o2_ml_kg_h is not None else 8.5)
    mass_kg = float(mass_kg if mass_kg is not None else 0.40)

    # 2. Resolve Pack properties
    if pack is not None:
        if pack_area_m2 is None:
            pack_area_m2 = pack.get("area_m2") or pack.get("pack_area_m2")
        if mass_kg is None:
            mass_kg = pack.get("product_mass_kg")
        if co2_injury_ceiling is None:
            co2_injury_ceiling = pack.get("co2_injury_ceiling")

    pack_area_m2 = float(pack_area_m2 if pack_area_m2 is not None else 0.045)

    # 3. Resolve Film transmission properties
    if film is not None:
        f_dict = film if isinstance(film, dict) else film.model_dump()
        if film_otr is None:
            film_otr = f_dict.get("measured_otr")
        if film_co2tr is None:
            film_co2tr = f_dict.get("measured_co2tr")

    # If explicit total transmission per pack is provided (e.g. from perforations + film)
    if total_otr_ml_day_atm is None:
        if film_otr is not None:
            total_otr_ml_day_atm = film_otr * pack_area_m2
        else:
            total_otr_ml_day_atm = 10000.0 * pack_area_m2  # Default ~10,000 mL/m2.day.atm

    if total_co2tr_ml_day_atm is None:
        if film_co2tr is not None:
            total_co2tr_ml_day_atm = film_co2tr * pack_area_m2
        elif film_otr is not None:
            # Assume polyolefin film beta ~ 4.0 if CO2TR not specified
            total_co2tr_ml_day_atm = total_otr_ml_day_atm * 4.0
        else:
            total_co2tr_ml_day_atm = 20000.0 * pack_area_m2

    inputs_used.update({
        "respiration_o2_ml_kg_h": respiration_o2_ml_kg_h,
        "mass_kg": mass_kg,
        "pack_area_m2": pack_area_m2,
        "total_otr_ml_day_atm": total_otr_ml_day_atm,
        "total_co2tr_ml_day_atm": total_co2tr_ml_day_atm,
        "rq": rq,
        "km_o2": km_o2,
        "co2_injury_ceiling": co2_injury_ceiling,
    })

    # Michaelis-Menten normalization
    # R_ref = R_max * y_out / (Km + y_out)
    # => R_max = R_ref * (Km + y_out) / y_out
    r_max = respiration_o2_ml_kg_h * (km_o2 + y_out_o2) / y_out_o2

    def r_o2(y: float) -> float:
        if y <= 0:
            return 0.0
        return r_max * y / (km_o2 + y)

    # Steady-state O2 objective function: Ingress(y) - Consumption(y) = 0
    # Ingress [mL/h] = (total_otr / 24) * (y_out - y)
    # Consumption [mL/h] = mass * r_o2(y)
    def f_o2(y: float) -> float:
        ingress = (total_otr_ml_day_atm / 24.0) * (y_out_o2 - y)
        consumption = mass_kg * r_o2(y)
        return ingress - consumption

    # Bracket validation:
    # At y = 0: ingress > 0, consumption = 0 => f(0) > 0
    # At y = y_out: ingress = 0, consumption > 0 => f(y_out) < 0
    f_0 = f_o2(0.0)
    f_out = f_o2(y_out_o2)

    if f_0 <= 0:
        # Even at 0% O2, consumption exceeds max permeance -> severe hypoxia
        eq_o2 = 0.0
    elif f_out >= 0:
        eq_o2 = y_out_o2
    else:
        # Guaranteed unique root by Intermediate Value Theorem
        eq_o2 = scipy.optimize.brentq(f_o2, 0.0, y_out_o2)

    # Calculate equilibrium CO2:
    # Egress(CO2) = Generation(CO2)
    # (total_co2tr / 24) * (y_eq_co2 - y_out_co2) = mass * rq * r_o2(eq_o2)
    # => y_eq_co2 = y_out_co2 + (mass * rq * r_o2(eq_o2) * 24) / total_co2tr
    r_co2_eq = rq * r_o2(eq_o2)
    delta_co2_eq = (mass_kg * r_co2_eq * 24.0) / total_co2tr_ml_day_atm
    eq_co2 = y_out_co2 + delta_co2_eq

    # -----------------------------------------------------------------------
    # Non-Negotiable Hard Safety Clamps
    # -----------------------------------------------------------------------
    # Clamp 1: O2 floor check
    if eq_o2 < MIN_EQUILIBRIUM_O2_FLOOR:
        return NoSolution(
            is_solvable=False,
            reason=(
                f"Equilibrium in-pack O2 is predicted to reach {eq_o2:.2%}, which drops strictly below "
                f"the non-negotiable food safety floor of {MIN_EQUILIBRIUM_O2_FLOOR:.1%}. "
                "Severe risk of anaerobic fermentation, off-flavours, and Clostridium botulinum toxin synthesis."
            ),
            violation_type="O2_FLOOR",
            suggested_action=(
                "Increase film breathability via laser micro-perforations, switch to a higher OTR film, "
                "or reduce storage temperature to lower produce respiration."
            ),
            details={
                "equilibrium_o2": eq_o2,
                "equilibrium_co2": eq_co2,
                "o2_floor": MIN_EQUILIBRIUM_O2_FLOOR,
                "inputs": inputs_used,
            },
        )

    # Clamp 2: CO2 injury ceiling check
    if co2_injury_ceiling is not None and eq_co2 > co2_injury_ceiling:
        return NoSolution(
            is_solvable=False,
            reason=(
                f"Equilibrium in-pack CO2 is predicted to reach {eq_co2:.2%}, which exceeds the commodity "
                f"injury ceiling of {co2_injury_ceiling:.2%}. Risk of tissue breakdown, internal browning, "
                "and physiological injury."
            ),
            violation_type="CO2_CEILING",
            suggested_action=(
                "Increase CO2 transmission rate via micro-perforations, add a CO2 scavenger sachet, "
                "or lower pack density."
            ),
            details={
                "equilibrium_o2": eq_o2,
                "equilibrium_co2": eq_co2,
                "co2_injury_ceiling": co2_injury_ceiling,
                "inputs": inputs_used,
            },
        )

    return EquilibriumAtmosphereResult(
        is_solvable=True,
        equilibrium_o2=eq_o2,
        equilibrium_co2=eq_co2,
        equilibrium_o2_pct=eq_o2 * 100.0,
        equilibrium_co2_pct=eq_co2 * 100.0,
        respiration_rate_o2_ml_kg_h=r_o2(eq_o2),
        respiration_rate_co2_ml_kg_h=r_co2_eq,
        is_safe=True,
        safety_notes=["In-pack atmosphere is within safe physiological bounds."],
        equation_id="MAP-05",
        inputs_used=inputs_used,
    )
