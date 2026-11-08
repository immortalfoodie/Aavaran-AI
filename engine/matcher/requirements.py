"""
Requirement vector derivation for Aavaran.

Implements Section 4.4, Section 5, and Section 6 of BLUEPRINT.md:
- Immediate regime branch: respiring produce (passive MAP) vs non-respiring barrier.
  These two design regimes are physically and mathematically distinct and do not share a code path.
- Non-respiring: runs moisture and oxidation models, taking the stricter requirement independently on each axis.
- Respiring: runs MAP designer, solving for steady-state OTR/CO2TR and micro-perforation sizing.
- Mechanical requirements derived from pack mass, drop height, and stack height.
- Thermal requirements derived from process (retort, hot-fill, frozen, ambient).
- Optical requirements derived from light sensitivity.
"""

import logging
from typing import Any, Dict, Optional, Union

from engine.models.map_design import (
    SelectivityRecommendation,
    required_co2tr,
    required_selectivity,
)
from engine.models.map_design import (
    required_otr as required_map_otr,
)
from engine.models.moisture import (
    GABIsotherm,
    LinearIsotherm,
    required_wvtr,
)
from engine.models.oxidation import (
    DEFAULT_AIR_O2_FRACTION,
    DEFAULT_FLUSH_O2_FRACTION,
    required_otr as required_barrier_otr,
)
from engine.models.respiration import (
    apply_state_modifiers,
    rate_at_temperature,
)
from engine.types import (
    CommodityProfile,
    Environment,
    PackGeometry,
    RequirementVector,
)

logger = logging.getLogger(__name__)


def is_respiring_produce(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]],
) -> bool:
    """
    Determine if a commodity is an active respiring produce item.
    Thermally treated, blanched, dried, or processed products do not respire.
    """
    if profile is None:
        return False

    p_dict = profile if isinstance(profile, dict) else profile.model_dump()

    # Check state modifiers: blanching / thermal treatment destroys respiration
    state_mods = p_dict.get("state_modifiers") or {}
    if any(mod in state_mods for mod in ["blanched", "thermally_treated"]):
        return False

    # Check group and class
    group = str(p_dict.get("group") or "").lower()
    c_class = str(p_dict.get("class") or p_dict.get("commodity_class") or "").lower()

    if group in ["fruit", "vegetable", "root_tuber", "fresh_cut", "greens", "fungi"]:
        return True
    if "fresh" in c_class or "produce" in c_class or "respiring" in c_class:
        return True

    # Check respiration model fields
    if p_dict.get("respiration_model") is not None or p_dict.get("respiration_ref_rate") is not None:
        return True

    return False


def _derive_respiring(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]],
    environment: Optional[Union[Environment, Dict[str, Any]]],
    target_shelf_life_days: float,
    geom: PackGeometry,
) -> RequirementVector:
    """
    Isolated design path for respiring produce (passive MAP).
    Films typically require OTR in the 1,085 to 7,000+ mL/(m2.day.atm) range.
    """
    p_dict = profile if isinstance(profile, dict) else (profile.model_dump() if profile else {})
    e_dict = environment if isinstance(environment, dict) else (environment.model_dump() if environment else {})

    # Storage temperature
    temp_c = 10.0
    if "temperature" in e_dict and e_dict["temperature"]:
        temp_c = float(e_dict["temperature"].get("value") or 10.0)

    # 1. Respiration kinetics scaled to temperature
    resp_rate_result = rate_at_temperature(profile=profile, temp_target_c=temp_c)
    base_rate = resp_rate_result.rate

    # 2. State modifiers (cut, bruised, washed, etc.)
    state_mods = p_dict.get("state_modifiers") or {}
    applied_states = [k for k, v in state_mods.items() if v]
    if applied_states:
        mod_result = apply_state_modifiers(base_rate, applied_states)
        r_o2 = mod_result.rate_max  # Design conservatively to the upper bound
    else:
        r_o2 = base_rate

    r_co2 = r_o2  # RQ ~ 1.0 baseline

    # Target in-pack gas concentrations (conservative safety clamps)
    y_in_o2 = 0.03  # 3 % target O2 (clamp >= 2 %)
    y_in_co2 = 0.08  # 8 % target CO2
    y_out_o2 = DEFAULT_AIR_O2_FRACTION
    y_out_co2 = 0.0004

    # Transmission calculations
    otr_map = required_map_otr(
        respiration_o2=r_o2,
        mass=geom.product_mass_kg,
        area=geom.pack_area_m2,
        y_out=y_out_o2,
        y_in=y_in_o2,
    )

    co2tr_map = required_co2tr(
        respiration_co2=r_co2,
        mass=geom.product_mass_kg,
        area=geom.pack_area_m2,
        y_in_co2=y_in_co2,
        y_out_co2=y_out_co2,
    )

    sel_res = required_selectivity(
        y_out_o2=y_out_o2,
        y_in_o2=y_in_o2,
        y_in_co2=y_in_co2,
        y_out_co2=y_out_co2,
        rq=1.0,
    )

    perforation_needed = (
        sel_res.recommendation == SelectivityRecommendation.PERFORATION
        or otr_map.required_otr > 7000.0
    )

    # Produce packages need breathable moisture management (WVTR 15-30 g/m2.day to avoid condensation)
    # and anti-fog film if washed or cut
    antifog = bool(
        "washed" in applied_states
        or "cut" in applied_states
        or p_dict.get("water_activity", {}).get("value", 0.0) > 0.90
    )

    return RequirementVector(
        regime="respiring_produce",
        min_otr=float(otr_map.required_otr * 0.7),  # Floor to prevent suffocation / botulinum
        max_otr=float(otr_map.required_otr * 1.4),  # Ceiling to maintain MA benefits
        max_wvtr=25.0,  # Breathable moisture window
        target_o2=y_in_o2,
        target_co2=y_in_co2,
        map_required=True,
        perforation_required=perforation_needed,
        antifog_required=antifog,
        equation_id="MAP-01/02/03",
    )


def _derive_non_respiring(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]],
    environment: Optional[Union[Environment, Dict[str, Any]]],
    target_shelf_life_days: float,
    geom: PackGeometry,
) -> RequirementVector:
    """
    Isolated design path for non-respiring barrier packaging.
    Films typically require OTR < 70 cc/(m2.day.atm).
    Runs moisture and oxidation models and takes the stricter requirement on each axis independently.
    """
    p_dict = profile if isinstance(profile, dict) else (profile.model_dump() if profile else {})
    e_dict = environment if isinstance(environment, dict) else (environment.model_dump() if environment else {})

    # Moisture axis parameters
    aw_initial = 0.22
    if "water_activity" in p_dict and p_dict["water_activity"]:
        aw_initial = float(p_dict["water_activity"].get("value") or 0.22)

    # Critical aw for crispness/stability (typically 0.45 for namkeen/biscuits/powders)
    aw_crit = float(p_dict.get("aw_crit") or 0.45)

    # Look up specific isotherm from KB if available
    comm_id = str(p_dict.get("commodity_id") or "")
    comm_class = str(p_dict.get("commodity_class") or p_dict.get("class") or "")
    matched_iso = None
    try:
        from kb.loaders import load_kb
        kb_data = load_kb()
        for iso_rec in kb_data.isotherms.values():
            iso_comm = iso_rec.food_class_or_commodity
            if (iso_comm in comm_id) or (comm_id and comm_id in iso_comm):
                matched_iso = iso_rec
                break
            if comm_class and ((iso_comm in comm_class) or (comm_class in iso_comm)):
                matched_iso = iso_rec
                break
    except Exception:
        matched_iso = None

    if matched_iso:
        if matched_iso.aw_crit is not None:
            aw_crit = float(matched_iso.aw_crit)
        if matched_iso.model_type.upper() == "GAB" and matched_iso.m0 is not None:
            gab_isotherm = GABIsotherm(
                m0=float(matched_iso.m0) / 100.0,
                c_g=float(matched_iso.c_g or 14.5),
                k=float(matched_iso.k or 0.78),
            )
        else:
            gab_isotherm = GABIsotherm(m0=0.032, c_g=14.5, k=0.78)
    else:
        gab_isotherm = GABIsotherm(m0=0.032, c_g=14.5, k=0.78)

    # Ensure aw_initial is strictly less than aw_crit so moisture shelf life / WVTR is positive
    if aw_initial >= aw_crit:
        aw_initial = max(0.10, round(aw_crit - 0.15, 3))

    temp_c = 30.0
    if "temperature" in e_dict and e_dict["temperature"]:
        temp_c = float(e_dict["temperature"].get("value") or 30.0)

    rh_pct = 75.0
    if "relative_humidity" in e_dict and e_dict["relative_humidity"]:
        rh_pct = float(e_dict["relative_humidity"].get("value") or 75.0)

    dry_solids = geom.dry_solids_kg
    if dry_solids is None or dry_solids <= 0:
        moist_pct = 3.0
        if "moisture_pct" in p_dict and p_dict["moisture_pct"]:
            moist_pct = float(p_dict["moisture_pct"].get("value") or 3.0)
        dry_solids = geom.product_mass_kg * (1.0 - moist_pct / 100.0)

    # Run moisture model
    wvtr_res = required_wvtr(
        target_days=target_shelf_life_days,
        pack_area=geom.pack_area_m2,
        dry_solids=dry_solids,
        aw_initial=aw_initial,
        aw_crit=aw_crit,
        temperature_c=temp_c,
        relative_humidity_pct=rh_pct,
        isotherm=gab_isotherm,
        model_override="GAB",
    )
    req_wvtr = max(0.01, float(wvtr_res.required_wvtr))

    # Oxidation axis parameters
    fat_pct = 0.0
    if "fat_pct" in p_dict and p_dict["fat_pct"]:
        fat_pct = float(p_dict["fat_pct"].get("value") or 0.0)

    is_ox_sensitive = bool(
        p_dict.get("light_sensitive", False)
        or fat_pct > 2.0
        or any(m in str(p_dict.get("failure_modes", [])) for m in ["oxidation", "rancidity"])
    )

    req_otr = None
    if is_ox_sensitive:
        # Peroxide-value absorption budget (typical 15-30 mg O2 / kg product)
        q_budget = float(p_dict.get("q_budget_mg_per_kg") or (25.0 if fat_pct > 15 else 15.0))
        otr_res = required_barrier_otr(
            target_days=target_shelf_life_days,
            pack_area_m2=geom.pack_area_m2,
            product_mass_kg=geom.product_mass_kg,
            q_budget_mg_per_kg=q_budget,
            headspace_volume_cc=geom.headspace_volume_cc,
            headspace_o2_fraction=geom.headspace_o2_fraction,
        )
        req_otr = float(otr_res.required_otr)
    else:
        # Default non-respiring barrier ceiling
        req_otr = 70.0

    return RequirementVector(
        regime="non_respiring_barrier",
        max_wvtr=req_wvtr,
        max_otr=req_otr,
        map_required=False,
        perforation_required=False,
        antifog_required=False,
        equation_id=f"{wvtr_res.equation_id} + OX-02",
    )


def derive(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    target_shelf_life: Union[float, int, Dict[str, Any]] = 180.0,
    pack_geometry: Optional[Union[PackGeometry, Dict[str, Any]]] = None,
) -> RequirementVector:
    """
    Derive the multi-axis RequirementVector for packaging selection.

    Args:
        profile: CommodityProfile or dictionary.
        environment: Storage environment or dictionary.
        target_shelf_life: Target shelf life in days (float/int).
        pack_geometry: PackGeometry or dictionary containing pack dimensions,
                       mass, drop height, stack height, and process.

    Returns:
        RequirementVector with barrier, mechanical, thermal, and optical specs.
    """
    # 1. Parse target shelf life
    if isinstance(target_shelf_life, dict):
        target_days = float(target_shelf_life.get("days") or target_shelf_life.get("target_days") or 180.0)
    else:
        target_days = float(target_shelf_life)

    if target_days <= 0:
        raise ValueError(f"Target shelf life must be positive, got {target_days}")

    # 2. Parse pack geometry
    if pack_geometry is None:
        geom = PackGeometry()
    elif isinstance(pack_geometry, dict):
        geom = PackGeometry(**pack_geometry)
    else:
        geom = pack_geometry

    # 3. Branch on regime first (respiring produce vs non-respiring barrier)
    if is_respiring_produce(profile):
        vec = _derive_respiring(profile, environment, target_days, geom)
    else:
        vec = _derive_non_respiring(profile, environment, target_days, geom)

    # 4. Add mechanical requirements from pack mass, drop height and stack height
    # Minimum composite thickness
    base_thickness = 30.0
    if geom.product_mass_kg >= 5.0:
        base_thickness = 100.0
    elif geom.product_mass_kg >= 1.0:
        base_thickness = 70.0
    elif geom.product_mass_kg >= 0.25:
        base_thickness = 55.0

    if geom.drop_height_m > 1.2:
        base_thickness += 10.0
    if geom.stack_height_m > 2.0:
        base_thickness += 10.0

    vec.min_thickness_um = base_thickness

    # Minimum seal strength (ASTM F88, N / 15mm)
    base_seal = 15.0
    if geom.process.lower() == "retort":
        base_seal = 35.0
    elif geom.drop_height_m >= 1.2 or geom.product_mass_kg >= 0.5:
        base_seal = 25.0
    if geom.product_mass_kg >= 1.0:
        base_seal = max(base_seal, 30.0)

    vec.min_seal_strength_n_15mm = base_seal

    # Minimum puncture resistance (ASTM D1709, N)
    base_puncture = 2.0
    if geom.product_mass_kg >= 0.5 or geom.drop_height_m >= 1.0:
        base_puncture = 4.0
    p_dict = profile if isinstance(profile, dict) else (profile.model_dump() if profile else {})
    comm_id = str(p_dict.get("commodity_id") or "").lower()
    if any(sharp in comm_id for sharp in ["namkeen", "chips", "pasta", "bone"]):
        base_puncture = max(base_puncture, 5.0)

    vec.min_puncture = base_puncture

    # 5. Add thermal requirements from process
    proc = geom.process.lower()
    vec.process = proc
    if proc == "retort":
        vec.service_temp_min_c = 0.0
        vec.service_temp_max_c = 121.0
    elif proc == "hot_fill":
        vec.service_temp_min_c = 10.0
        vec.service_temp_max_c = 95.0
    elif proc == "frozen":
        vec.service_temp_min_c = -20.0
        vec.service_temp_max_c = 30.0
    else:
        vec.service_temp_min_c = 0.0
        vec.service_temp_max_c = 45.0

    # 6. Add optical requirements from light sensitivity (dry/processed foods only)
    is_light_sens = bool(p_dict.get("light_sensitive", False))
    if is_light_sens and vec.regime == "non_respiring_barrier":
        vec.light_barrier_od = 2.5  # Requires metallised or foil barrier

    # Fat contact flag
    fat_val = 0.0
    if "fat_pct" in p_dict and p_dict["fat_pct"]:
        fat_val = float(p_dict["fat_pct"].get("value") or 0.0)
    vec.fat_contact = fat_val > 5.0

    return vec
