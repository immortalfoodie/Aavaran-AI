"""
Moisture-limited shelf-life and WVTR requirement models for Aavaran.

Implements Section 5.1 of BLUEPRINT.md:
- Three moisture sorption isotherm implementations: Linear, BET, and GAB.
- Closed-form shelf life prediction coupling film permeance with linear and GAB isotherms.
- Design-stage WVTR requirement derivation inverted at the ASTM F1249 reference condition (38 °C, 90 % RH).
- Explicit selection logging and provenance tracking with equation IDs (M-01 .. M-04).
"""

import logging
import math
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field

from engine.types import CommodityProfile, Environment, PackageCandidate
from engine.units import Q_, ureg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sorption Isotherms
# ---------------------------------------------------------------------------

class LinearIsotherm:
    """
    Linear moisture sorption isotherm: m(a_w) = b * a_w + c.
    Valid for low water activities (typically a_w <= 0.5).
    """

    def __init__(self, b: float, c: float = 0.0) -> None:
        if b <= 0:
            raise ValueError(f"Linear isotherm slope b must be positive, got {b}")
        self.b = float(b)
        self.c = float(c)

    def moisture_at_aw(self, aw: float) -> float:
        """Moisture content (kg H2O / kg dry solids or g/100g) at water activity aw."""
        if aw < 0.0:
            raise ValueError(f"Water activity cannot be negative, got {aw}")
        return self.b * aw + self.c

    def aw_at_moisture(self, m: float) -> float:
        """Water activity at moisture content m."""
        aw = (m - self.c) / self.b
        if aw < 0.0:
            return 0.0
        return aw


class BETIsotherm:
    """
    Brunauer-Emmett-Teller (BET) moisture sorption isotherm:
    m(a_w) = (m0 * C * a_w) / [ (1 - a_w) * (1 + (C - 1) * a_w) ]
    Valid typically up to a_w ≈ 0.45.
    """

    def __init__(self, m0: float, c: float) -> None:
        if m0 <= 0:
            raise ValueError(f"BET monolayer moisture m0 must be positive, got {m0}")
        if c <= 0:
            raise ValueError(f"BET constant C must be positive, got {c}")
        self.m0 = float(m0)
        self.c = float(c)

    def moisture_at_aw(self, aw: float) -> float:
        if not (0.0 <= aw < 1.0):
            raise ValueError(f"Water activity must be in [0, 1) for BET, got {aw}")
        if aw == 0.0:
            return 0.0
        denom = (1.0 - aw) * (1.0 + (self.c - 1.0) * aw)
        if denom <= 0:
            return float("inf")
        return (self.m0 * self.c * aw) / denom

    def aw_at_moisture(self, m: float) -> float:
        if m <= 0.0:
            return 0.0
        # Quadratic formula for aw:
        # m*(1 - aw)*(1 + (C - 1)*aw) = m0*C*aw
        # => (C - 1)*aw^2 + [m0*C/m + (2 - C)]*aw - 1 = 0 (scaled by m)
        a_quad = (self.c - 1.0) * m
        b_quad = self.m0 * self.c + (2.0 - self.c) * m
        c_quad = -m

        if abs(a_quad) < 1e-12:
            return m / (m + self.m0)

        disc = b_quad**2 - 4.0 * a_quad * c_quad
        if disc < 0:
            raise ValueError(f"No real solution for BET water activity at moisture {m}")
        aw = (-b_quad + math.sqrt(disc)) / (2.0 * a_quad)
        return max(0.0, min(1.0, aw))


class GABIsotherm:
    """
    Guggenheim-Anderson-de Boer (GAB) moisture sorption isotherm:
    m(a_w) = (m0 * C_g * K * a_w) / [ (1 - K * a_w) * (1 + (C_g - 1) * K * a_w) ]
    Valid across the full range (a_w up to 0.9+).
    """

    def __init__(self, m0: float, c_g: float, k: float) -> None:
        if m0 <= 0:
            raise ValueError(f"GAB monolayer moisture m0 must be positive, got {m0}")
        if c_g <= 0:
            raise ValueError(f"GAB constant C_g must be positive, got {c_g}")
        if not (0 < k <= 1.5):
            raise ValueError(f"GAB multilayer factor K must be in (0, 1.5], got {k}")
        self.m0 = float(m0)
        self.c_g = float(c_g)
        self.k = float(k)

    def moisture_at_aw(self, aw: float) -> float:
        if aw < 0.0:
            raise ValueError(f"Water activity cannot be negative, got {aw}")
        if aw == 0.0:
            return 0.0
        x = self.k * aw
        if x >= 1.0:
            return float("inf")
        denom = (1.0 - x) * (1.0 + (self.c_g - 1.0) * x)
        if denom <= 0:
            return float("inf")
        return (self.m0 * self.c_g * x) / denom

    def aw_at_moisture(self, m: float) -> float:
        if m <= 0.0:
            return 0.0
        # Solve quadratic for x = K * aw
        a_quad = (self.c_g - 1.0) * m
        b_quad = self.m0 * self.c_g + (2.0 - self.c_g) * m
        c_quad = -m

        if abs(a_quad) < 1e-12:
            x = m / (m + self.m0)
        else:
            disc = b_quad**2 - 4.0 * a_quad * c_quad
            if disc < 0:
                raise ValueError(f"No real solution for GAB water activity at moisture {m}")
            x = (-b_quad + math.sqrt(disc)) / (2.0 * a_quad)

        aw = x / self.k
        return max(0.0, min(1.0, aw))

    def closed_form_integral_term(self, aw_start: float, aw_end: float, aw_out: float) -> float:
        """
        Evaluates the analytical integral:
        int_{aw_start}^{aw_end} [ 1 / (aw_out - u) * (dm/du) ] du
        used in the GAB shelf life equation.
        """
        def _f(u: float) -> float:
            # First term from 1 / (1 - K*u)
            d1 = 1.0 - self.k * aw_out
            if abs(d1) < 1e-12:
                d1 = 1e-12
            diff_u = aw_out - u
            if abs(diff_u) < 1e-12:
                diff_u = 1e-12

            f1 = (self.m0 * self.k / (d1**2)) * math.log(abs((1.0 - self.k * u) / diff_u)) - (
                self.m0 * self.k / (d1 * (1.0 - self.k * u))
            )

            # Second term from 1 / (1 + beta*K*u)
            beta = self.c_g - 1.0
            if abs(beta) < 1e-12:
                f2 = 0.0
            else:
                d2 = 1.0 + beta * self.k * aw_out
                if abs(d2) < 1e-12:
                    d2 = 1e-12
                f2 = (self.m0 * beta * self.k / (d2**2)) * math.log(
                    abs((1.0 + beta * self.k * u) / diff_u)
                ) - (self.m0 * beta * self.k / (d2 * (1.0 + beta * self.k * u)))

            return f1 + f2

        return _f(aw_end) - _f(aw_start)


# ---------------------------------------------------------------------------
# Pure Physics Helpers
# ---------------------------------------------------------------------------

def saturation_vapor_pressure_kpa(temperature_c: float) -> float:
    """
    Saturation vapor pressure of water at temperature T in degrees Celsius,
    using the Magnus-Tetens relationship. Returns pressure in kPa.
    """
    t_q = Q_(temperature_c, "degC")
    t_c = t_q.to("degC").magnitude
    # Tetens equation: p_sat = 0.61078 * exp(17.27 * T / (T + 237.3)) kPa
    p_kpa = 0.61078 * math.exp((17.27 * t_c) / (t_c + 237.3))
    return float(Q_(p_kpa, "kPa").magnitude)


def astm_f1249_test_driving_force_kpa() -> float:
    """
    Driving force (delta p) across the film during standard ASTM F1249 testing
    at 38 deg C and 90 % RH against a dry carrier gas (0 % RH).
    """
    p_sat_38 = saturation_vapor_pressure_kpa(38.0)
    return 0.90 * p_sat_38  # ~5.9616 kPa


# ---------------------------------------------------------------------------
# Result Schemas
# ---------------------------------------------------------------------------

class MoistureShelfLifeResult(BaseModel):
    shelf_life_days: float = Field(..., description="Predicted shelf life in days (or inf)")
    isotherm_used: str = Field(..., description="linear, GAB, or BET")
    equation_id: str = Field(..., description="M-01 (linear) or M-02 (GAB)")
    selection_reason: str = Field(..., description="Rationale for isotherm choice")
    allowable_permeance_g_m2_day_kpa: Optional[float] = None
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


class WVTRRequirementResult(BaseModel):
    required_wvtr: float = Field(..., description="Quotable WVTR at ASTM F1249 (38 C, 90 % RH) in g/(m2.day)")
    allowable_permeance: float = Field(..., description="Film permeance k/x in g / (m2.day.kPa)")
    equation_id: str = Field(..., description="M-03 (linear design) or M-04 (GAB design)")
    isotherm_used: str = Field(..., description="linear or GAB")
    selection_reason: str = Field(..., description="Rationale for isotherm choice")
    inputs_used: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shelf Life Model (Equation M-01 & M-02)
# ---------------------------------------------------------------------------

def shelf_life_moisture_limited(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    package: Optional[Union[PackageCandidate, Dict[str, Any]]] = None,
    *,
    aw_initial: Optional[float] = None,
    aw_crit: Optional[float] = None,
    dry_solids_kg: Optional[float] = None,
    wvtr: Optional[float] = None,
    pack_area_m2: Optional[float] = None,
    temperature_c: Optional[float] = None,
    relative_humidity_pct: Optional[float] = None,
    isotherm: Optional[Union[LinearIsotherm, GABIsotherm, BETIsotherm]] = None,
    model_override: Optional[str] = None,
) -> MoistureShelfLifeResult:
    """
    Predict moisture-limited shelf life using the Labuza packaging equation.
    Uses closed-form solutions:
    - Linear isotherm (Equation M-01) for aw_crit <= 0.5
    - GAB isotherm (Equation M-02) for aw_crit > 0.5 or when GAB is specified
    """
    # 1. Resolve Profile inputs
    if profile is not None:
        if isinstance(profile, dict):
            p_dict = profile
        else:
            p_dict = profile.model_dump()
        if aw_initial is None and "water_activity" in p_dict and p_dict["water_activity"]:
            aw_initial = p_dict["water_activity"].get("value")
        if dry_solids_kg is None:
            dry_solids_kg = p_dict.get("dry_solids_kg", 0.10)
        if aw_crit is None:
            comm_id = str(p_dict.get("commodity_id") or "")
            comm_class = str(p_dict.get("commodity_class") or p_dict.get("class") or "")
            try:
                from kb.loaders import load_kb
                kb_data = load_kb()
                for iso_rec in kb_data.isotherms.values():
                    iso_comm = iso_rec.food_class_or_commodity
                    if (iso_comm in comm_id) or (comm_id and comm_id in iso_comm):
                        if iso_rec.aw_crit is not None:
                            aw_crit = float(iso_rec.aw_crit)
                        if isotherm is None and iso_rec.model_type.upper() == "GAB" and iso_rec.m0 is not None:
                            isotherm = GABIsotherm(m0=float(iso_rec.m0)/100.0, c_g=float(iso_rec.c_g or 14.5), k=float(iso_rec.k or 0.78))
                        break
                    if comm_class and ((iso_comm in comm_class) or (comm_class in iso_comm)):
                        if iso_rec.aw_crit is not None:
                            aw_crit = float(iso_rec.aw_crit)
                        if isotherm is None and iso_rec.model_type.upper() == "GAB" and iso_rec.m0 is not None:
                            isotherm = GABIsotherm(m0=float(iso_rec.m0)/100.0, c_g=float(iso_rec.c_g or 14.5), k=float(iso_rec.k or 0.78))
                        break
            except Exception:
                pass
            if aw_crit is None:
                aw_crit = p_dict.get("aw_crit", 0.45)
    
    # Defaults if still unassigned
    aw_initial = float(aw_initial if aw_initial is not None else 0.22)
    aw_crit = float(aw_crit if aw_crit is not None else 0.45)
    dry_solids_kg = float(dry_solids_kg if dry_solids_kg is not None else 0.10)
    if aw_initial >= aw_crit:
        aw_initial = max(0.10, round(aw_crit - 0.15, 3))

    # 2. Resolve Environment inputs
    if environment is not None:
        if isinstance(environment, dict):
            e_dict = environment
        else:
            e_dict = environment.model_dump()
        if temperature_c is None and "temperature" in e_dict and e_dict["temperature"]:
            temperature_c = e_dict["temperature"].get("value")
        if relative_humidity_pct is None and "relative_humidity" in e_dict and e_dict["relative_humidity"]:
            relative_humidity_pct = e_dict["relative_humidity"].get("value")
    
    temperature_c = float(temperature_c if temperature_c is not None else 30.0)
    relative_humidity_pct = float(relative_humidity_pct if relative_humidity_pct is not None else 75.0)
    aw_out = relative_humidity_pct / 100.0

    # 3. Resolve Package inputs
    if package is not None:
        if isinstance(package, dict):
            pkg_dict = package
        else:
            pkg_dict = package.model_dump()
        if wvtr is None:
            wvtr = pkg_dict.get("measured_wvtr")
        if pack_area_m2 is None:
            pack_area_m2 = pkg_dict.get("pack_area_m2", 0.055)

    wvtr = float(wvtr if wvtr is not None else 1.0)
    pack_area_m2 = float(pack_area_m2 if pack_area_m2 is not None else 0.055)

    inputs_used = {
        "aw_initial": aw_initial,
        "aw_crit": aw_crit,
        "dry_solids_kg": dry_solids_kg,
        "wvtr": wvtr,
        "pack_area_m2": pack_area_m2,
        "temperature_c": temperature_c,
        "relative_humidity_pct": relative_humidity_pct,
    }

    # Physical boundary conditions
    if aw_initial >= aw_crit:
        # Already at or above critical threshold
        return MoistureShelfLifeResult(
            shelf_life_days=0.0,
            isotherm_used="none",
            equation_id="M-01",
            selection_reason="Initial water activity already exceeds or equals critical water activity.",
            inputs_used=inputs_used,
        )

    if aw_out <= aw_crit:
        # External RH is drier than critical threshold; moisture ingress will never cause failure
        return MoistureShelfLifeResult(
            shelf_life_days=float("inf"),
            isotherm_used="none",
            equation_id="M-01",
            selection_reason="External relative humidity is lower than critical moisture threshold (no spoilage possible).",
            inputs_used=inputs_used,
        )

    if wvtr <= 0.0:
        # Zero permeance yields infinite shelf life
        return MoistureShelfLifeResult(
            shelf_life_days=float("inf"),
            isotherm_used="none",
            equation_id="M-01",
            selection_reason="Zero film permeance (WVTR = 0) prevents all moisture ingress.",
            inputs_used=inputs_used,
        )

    # Calculate permeance k/x from WVTR (at ASTM F1249: 38 C, 90 % RH)
    # Using Pint quantities
    wvtr_q = Q_(wvtr, "g / (m**2 * day)")
    delta_p_test_kpa = astm_f1249_test_driving_force_kpa()
    permeance_mag = wvtr / delta_p_test_kpa  # in g / (m² · day · kPa)

    # Storage saturation vapor pressure
    p0_kpa = saturation_vapor_pressure_kpa(temperature_c)

    # Unit scaling: dry solids in kg, permeance in g / (m² · day · kPa)
    # 1 kg dry solids = 1000 g dry solids.
    # W_s_g = dry_solids_kg * 1000
    w_s_g = dry_solids_kg * 1000.0

    # 4. Determine Isotherm Selection
    use_linear = False
    if model_override:
        use_linear = (model_override.lower() == "linear")
        reason = f"Explicit override requested isotherm: {model_override}"
    elif isotherm is not None:
        if isinstance(isotherm, LinearIsotherm):
            use_linear = True
            reason = f"Supplied LinearIsotherm (slope b={isotherm.b:.3f})"
        elif isinstance(isotherm, GABIsotherm):
            use_linear = False
            reason = f"Supplied GABIsotherm (m0={isotherm.m0:.2f}, Cg={isotherm.c_g:.2f}, K={isotherm.k:.2f})"
        else:
            use_linear = False
            reason = "Supplied custom isotherm"
    else:
        # Section 5.1 rule:
        # "Use the linear model only when a_w,crit <= 0.5, and have the engine log which isotherm it used."
        if aw_crit <= 0.50:
            use_linear = True
            reason = f"Selected linear isotherm: critical water activity aw_crit={aw_crit:.3f} <= 0.5 (linear regime valid)"
        else:
            use_linear = False
            reason = f"Selected GAB isotherm: critical water activity aw_crit={aw_crit:.3f} > 0.5 requires GAB multilayer curvature"

    logger.info(reason)

    if use_linear:
        # Linear isotherm closed form (Equation M-01)
        # b in g water / g dry solids per aw, or default slope if not provided
        if isotherm is not None and isinstance(isotherm, LinearIsotherm):
            b_slope = isotherm.b
        else:
            # Default slope for typical dry starch/protein food class (~7.0 - 12.0)
            b_slope = 7.0

        # Integral term: b * ln[ (aw_out - aw_initial) / (aw_out - aw_crit) ]
        ratio = (aw_out - aw_initial) / (aw_out - aw_crit)
        ln_term = math.log(ratio)
        
        # t = (W_s * b) / (permeance * A * p0) * ln[...]
        # Note: permeance is in g/(m²·day·kPa), w_s_g is in g, A is in m², p0 is in kPa
        time_days = (w_s_g * b_slope) / (permeance_mag * pack_area_m2 * p0_kpa) * ln_term

        return MoistureShelfLifeResult(
            shelf_life_days=float(time_days),
            isotherm_used="linear",
            equation_id="M-01",
            selection_reason=reason,
            allowable_permeance_g_m2_day_kpa=permeance_mag,
            inputs_used=inputs_used,
        )
    else:
        # GAB isotherm closed form (Equation M-02)
        if isotherm is not None and isinstance(isotherm, GABIsotherm):
            gab = isotherm
        else:
            # Baseline dry snack GAB parameters from KB
            gab = GABIsotherm(m0=3.2, c_g=14.5, k=0.78)

        i_term = gab.closed_form_integral_term(aw_initial, aw_crit, aw_out)
        time_days = (w_s_g) / (permeance_mag * pack_area_m2 * p0_kpa) * i_term

        return MoistureShelfLifeResult(
            shelf_life_days=float(time_days),
            isotherm_used="GAB",
            equation_id="M-02",
            selection_reason=reason,
            allowable_permeance_g_m2_day_kpa=permeance_mag,
            inputs_used=inputs_used,
        )


# ---------------------------------------------------------------------------
# Design Specification: Required WVTR (Equation M-03 & M-04)
# ---------------------------------------------------------------------------

def required_wvtr(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    target_days: float = 180.0,
    pack_area: float = 0.055,
    dry_solids: float = 0.10,
    *,
    aw_initial: Optional[float] = None,
    aw_crit: Optional[float] = None,
    temperature_c: Optional[float] = None,
    relative_humidity_pct: Optional[float] = None,
    isotherm: Optional[Union[LinearIsotherm, GABIsotherm, BETIsotherm]] = None,
    model_override: Optional[str] = None,
) -> WVTRRequirementResult:
    """
    Inverts the moisture sorption relationship to emit an allowable permeance
    and quotable WVTR at ASTM F1249 reference conditions (38 C, 90 % RH).

    Equations:
    - M-03 for linear design: permeance_max = (W_s * b) / (A * p0 * t) * ln[(aw_out - aw_i)/(aw_out - aw_c)]
    - M-04 for GAB design:    permeance_max = W_s / (A * p0 * t) * [F(aw_c) - F(aw_i)]
    """
    if target_days <= 0:
        raise ValueError(f"Target shelf-life days must be positive, got {target_days}")
    if pack_area <= 0:
        raise ValueError(f"Pack area must be positive, got {pack_area}")
    if dry_solids <= 0:
        raise ValueError(f"Dry solids mass must be positive, got {dry_solids}")

    # Extract water activity and environment
    if profile is not None:
        p_dict = profile if isinstance(profile, dict) else profile.model_dump()
        if aw_initial is None and "water_activity" in p_dict and p_dict["water_activity"]:
            aw_initial = p_dict["water_activity"].get("value")
        if aw_crit is None:
            aw_crit = p_dict.get("aw_crit", 0.45)

    aw_initial = float(aw_initial if aw_initial is not None else 0.22)
    aw_crit = float(aw_crit if aw_crit is not None else 0.45)

    if environment is not None:
        e_dict = environment if isinstance(environment, dict) else environment.model_dump()
        if temperature_c is None and "temperature" in e_dict and e_dict["temperature"]:
            temperature_c = e_dict["temperature"].get("value")
        if relative_humidity_pct is None and "relative_humidity" in e_dict and e_dict["relative_humidity"]:
            relative_humidity_pct = e_dict["relative_humidity"].get("value")

    temperature_c = float(temperature_c if temperature_c is not None else 30.0)
    relative_humidity_pct = float(relative_humidity_pct if relative_humidity_pct is not None else 75.0)
    aw_out = relative_humidity_pct / 100.0

    p0_kpa = saturation_vapor_pressure_kpa(temperature_c)
    w_s_g = dry_solids * 1000.0

    inputs_used = {
        "target_days": target_days,
        "pack_area_m2": pack_area,
        "dry_solids_kg": dry_solids,
        "aw_initial": aw_initial,
        "aw_crit": aw_crit,
        "temperature_c": temperature_c,
        "relative_humidity_pct": relative_humidity_pct,
    }

    # Isotherm selection
    use_linear = False
    if model_override:
        use_linear = (model_override.lower() == "linear")
        reason = f"Explicit override requested isotherm: {model_override}"
    elif isotherm is not None:
        if isinstance(isotherm, LinearIsotherm):
            use_linear = True
            reason = f"Supplied LinearIsotherm (slope b={isotherm.b:.3f})"
        else:
            use_linear = False
            reason = "Supplied GAB/BET isotherm"
    else:
        if aw_crit <= 0.50:
            use_linear = True
            reason = f"Selected linear isotherm: critical water activity aw_crit={aw_crit:.3f} <= 0.5"
        else:
            use_linear = False
            reason = f"Selected GAB isotherm: critical water activity aw_crit={aw_crit:.3f} > 0.5"

    logger.info(reason)

    if use_linear:
        equation_id = "M-03"
        b_slope = isotherm.b if (isotherm and isinstance(isotherm, LinearIsotherm)) else 7.0
        ratio = (aw_out - aw_initial) / (aw_out - aw_crit)
        ln_term = math.log(ratio)
        permeance_max = (w_s_g * b_slope) / (pack_area * p0_kpa * target_days) * ln_term
    else:
        equation_id = "M-04"
        gab = isotherm if (isotherm and isinstance(isotherm, GABIsotherm)) else GABIsotherm(m0=3.2, c_g=14.5, k=0.78)
        i_term = gab.closed_form_integral_term(aw_initial, aw_crit, aw_out)
        permeance_max = (w_s_g) / (pack_area * p0_kpa * target_days) * i_term

    # Convert allowable permeance to WVTR at ASTM F1249 test conditions
    delta_p_test_kpa = astm_f1249_test_driving_force_kpa()
    req_wvtr = permeance_max * delta_p_test_kpa

    return WVTRRequirementResult(
        required_wvtr=float(req_wvtr),
        allowable_permeance=float(permeance_max),
        equation_id=equation_id,
        isotherm_used="linear" if use_linear else "GAB",
        selection_reason=reason,
        inputs_used=inputs_used,
    )
