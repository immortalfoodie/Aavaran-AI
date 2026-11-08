"""
Respiration kinetics and post-harvest physiological state models for Aavaran.

Implements Section 5.3 and Section 4.2 of BLUEPRINT.md:
- Arrhenius temperature dependence with activation energy (Ea).
- Q10 temperature coefficient fallback with explicit assumption ledger tracking.
- Post-harvest state modifiers (cut, bruised, washed, cured, blanched) returning multiplier ranges.
- Provenance and equation tracking with IDs (RESP-01, RESP-02).
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from engine.types import CommodityProfile
from engine.units import Q_, ureg

logger = logging.getLogger(__name__)

# Universal gas constant in kJ / (mol · K)
R_G_KJ_PER_MOL_K = 8.314462618e-3

# State modifier multiplier ranges from Section 4.2 of BLUEPRINT.md and kb/state_modifiers.csv
# Format: (respiration_multiplier_min, respiration_multiplier_max)
STATE_MODIFIER_RANGES: Dict[str, Tuple[float, float]] = {
    "cut": (3.0, 7.0),
    "sliced": (3.0, 7.0),
    "peeled": (3.0, 7.0),
    "bruised": (1.3, 2.0),
    "mechanically_damaged": (1.3, 2.0),
    "washed": (1.0, 1.0),
    "hydro_cooled": (1.0, 1.0),
    "hydro-cooled": (1.0, 1.0),
    "cured": (0.6, 0.9),
    "blanched": (0.0, 0.0),
    "thermally_treated": (0.0, 0.0),
}


class RespirationRateResult(BaseModel):
    """Result of respiration rate scaling with temperature."""

    rate: float = Field(..., description="Respiration rate at target temperature")
    rate_range: Optional[Tuple[float, float]] = Field(
        None, description="Respiration rate range if uncertainty or reference range is provided"
    )
    unit: str = Field(default="mL O2/(kg·h)", description="Engineering unit of rate")
    equation_id: str = Field(..., description="RESP-01 (Arrhenius) or RESP-02 (Q10 fallback)")
    model_used: str = Field(..., description="'arrhenius' or 'q10_fallback'")
    assumptions: List[str] = Field(
        default_factory=list, description="Assumption ledger entries for any inferred defaults"
    )
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class StateModifiedRateResult(BaseModel):
    """
    Result of applying physiological state modifiers to respiration rate.
    Returns a range (rate_min, rate_max), never a single point value.
    Supports unpacking as a 2-tuple: `rate_min, rate_max = apply_state_modifiers(...)`.
    """

    rate_min: float = Field(..., description="Lower bound of modified respiration rate")
    rate_max: float = Field(..., description="Upper bound of modified respiration rate")
    unit: str = Field(default="mL O2/(kg·h)", description="Engineering unit")
    states_applied: List[str] = Field(default_factory=list)
    multipliers: Tuple[float, float] = Field(
        ..., description="Cumulative (min_multiplier, max_multiplier) applied"
    )
    notes: List[str] = Field(default_factory=list)
    inputs_used: Dict[str, Any] = Field(default_factory=dict)

    def __iter__(self):
        """Allows direct tuple unpacking: rate_min, rate_max = res."""
        yield self.rate_min
        yield self.rate_max

    def __getitem__(self, index: int) -> float:
        if index == 0:
            return self.rate_min
        elif index == 1:
            return self.rate_max
        raise IndexError("StateModifiedRateResult has only 2 elements (min, max).")

    def __len__(self) -> int:
        return 2


def rate_at_temperature(
    rate_ref: Optional[float] = None,
    temp_ref_c: Optional[float] = None,
    temp_target_c: Optional[float] = None,
    *,
    ea_kj_mol: Optional[float] = None,
    q10: Optional[float] = None,
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    unit: str = "mL O2/(kg·h)",
) -> RespirationRateResult:
    """
    Compute respiration rate at a target storage temperature.

    Uses Arrhenius kinetics (Equation RESP-01) when activation energy Ea is known:
        R(T) = R_ref * exp[ (Ea / Rg) * (1/T_ref - 1/T) ]

    Falls back to Q10 scaling (Equation RESP-02) when Ea is unknown:
        R(T) = R_ref * Q10^[ (T - T_ref) / 10 ]
        Default Q10 = 2.5, flagged as an assumption in the ledger.

    Args:
        rate_ref: Reference respiration rate at temp_ref_c (in unit).
        temp_ref_c: Reference temperature in °C.
        temp_target_c: Target storage temperature in °C.
        ea_kj_mol: Activation energy in kJ/mol (typical range 29 - 93 kJ/mol).
        q10: Optional explicit Q10 coefficient.
        profile: Optional CommodityProfile or dict from which parameters are resolved.
        unit: Rate unit string (default 'mL O2/(kg·h)').

    Returns:
        RespirationRateResult containing scaled rate and provenance.
    """
    assumptions: List[str] = []

    # 1. Resolve from CommodityProfile if provided
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if rate_ref is None and "respiration_ref_rate" in p_dict and p_dict["respiration_ref_rate"]:
            rate_ref = p_dict["respiration_ref_rate"].get("value")
        if temp_ref_c is None and "respiration_ref_t_c" in p_dict and p_dict["respiration_ref_t_c"]:
            temp_ref_c = p_dict["respiration_ref_t_c"].get("value")
        if ea_kj_mol is None and "respiration_ea_kj_mol" in p_dict and p_dict["respiration_ea_kj_mol"]:
            ea_kj_mol = p_dict["respiration_ea_kj_mol"].get("value")

    if rate_ref is None:
        raise ValueError("Reference respiration rate (rate_ref) must be provided or present in profile.")
    if temp_ref_c is None:
        raise ValueError("Reference temperature (temp_ref_c) must be provided or present in profile.")
    if temp_target_c is None:
        temp_target_c = 20.0
        assumptions.append("Default target storage temperature 20.0 °C assumed.")

    rate_ref = float(rate_ref)
    temp_ref_c = float(temp_ref_c)
    temp_target_c = float(temp_target_c)

    # Convert temperatures to Kelvin
    t_ref_k = temp_ref_c + 273.15
    t_target_k = temp_target_c + 273.15

    if t_target_k <= 0 or t_ref_k <= 0:
        raise ValueError("Temperature in Kelvin must be strictly positive.")

    # 2. Arrhenius scaling if activation energy Ea is available
    if ea_kj_mol is not None and float(ea_kj_mol) > 0:
        ea = float(ea_kj_mol)
        exponent = (ea / R_G_KJ_PER_MOL_K) * (1.0 / t_ref_k - 1.0 / t_target_k)
        scaled_rate = rate_ref * math.exp(exponent)
        equation_id = "RESP-01"
        model_used = "arrhenius"
    else:
        # 3. Q10 fallback
        if q10 is None:
            q10_val = 2.5
            assumptions.append(
                "Default Q10=2.5 assumed because activation energy Ea is unknown (flagged in assumption ledger)."
            )
        else:
            q10_val = float(q10)

        delta_t = temp_target_c - temp_ref_c
        scaled_rate = rate_ref * (q10_val ** (delta_t / 10.0))
        equation_id = "RESP-02"
        model_used = "q10_fallback"

    inputs_used = {
        "rate_ref": rate_ref,
        "temp_ref_c": temp_ref_c,
        "temp_target_c": temp_target_c,
        "ea_kj_mol": ea_kj_mol,
        "q10": q10 if q10 is not None else (2.5 if model_used == "q10_fallback" else None),
        "unit": unit,
    }

    return RespirationRateResult(
        rate=scaled_rate,
        unit=unit,
        equation_id=equation_id,
        model_used=model_used,
        assumptions=assumptions,
        inputs_used=inputs_used,
    )


def apply_state_modifiers(
    rate: Union[float, Tuple[float, float], RespirationRateResult],
    state: Union[str, List[str]],
    *,
    unit: str = "mL O2/(kg·h)",
) -> StateModifiedRateResult:
    """
    Apply physiological state modifiers to respiration rate (Section 4.2).

    Modifiers:
        - 'cut' / 'sliced' / 'peeled': x3.0 to x7.0 (wound response)
        - 'bruised' / 'mechanically_damaged': x1.3 to x2.0
        - 'washed' / 'hydro_cooled': x1.0 to x1.0
        - 'cured': x0.6 to x0.9 (suberized wound periderm)
        - 'blanched' / 'thermally_treated': x0.0 to x0.0 (enzymes inactivated, respiration ceases)

    Returns a range (rate_min, rate_max), never a single point value.
    The returned object can be unpacked directly as `rate_min, rate_max = apply_state_modifiers(...)`.
    """
    # Extract base min and max rates
    if isinstance(rate, RespirationRateResult):
        base_min = rate.rate
        base_max = rate.rate
        unit = rate.unit
    elif isinstance(rate, (tuple, list)):
        base_min = float(rate[0])
        base_max = float(rate[1])
    else:
        base_min = float(rate)
        base_max = float(rate)

    # Normalize state inputs
    states_list: List[str] = []
    if isinstance(state, str):
        # Support comma or space separated strings or single name
        cleaned = [s.strip().lower().replace("-", "_") for s in state.replace(",", " ").split() if s.strip()]
        states_list = cleaned
    elif isinstance(state, (list, tuple)):
        states_list = [str(s).strip().lower().replace("-", "_") for s in state if str(s).strip()]

    mult_min = 1.0
    mult_max = 1.0
    notes: List[str] = []

    for s in states_list:
        matched = False
        for key, (k_min, k_max) in STATE_MODIFIER_RANGES.items():
            if s == key:
                mult_min *= k_min
                mult_max *= k_max
                notes.append(f"Applied modifier '{s}': range x{k_min} to x{k_max}.")
                matched = True
                break
        if not matched:
            notes.append(f"Warning: Unknown state modifier '{s}', ignored (x1.0).")

    final_min = base_min * mult_min
    final_max = base_max * mult_max

    inputs_used = {
        "base_rate_input": rate if isinstance(rate, (float, int)) else str(rate),
        "states": states_list,
        "cumulative_multiplier_min": mult_min,
        "cumulative_multiplier_max": mult_max,
    }

    return StateModifiedRateResult(
        rate_min=final_min,
        rate_max=final_max,
        unit=unit,
        states_applied=states_list,
        multipliers=(mult_min, mult_max),
        notes=notes,
        inputs_used=inputs_used,
    )
