from enum import Enum
from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field, field_validator, model_validator


class SourceType(str, Enum):
    MEASURED = "MEASURED"
    STANDARD = "STANDARD"
    PEER_REVIEWED = "PEER_REVIEWED"
    VENDOR_DATA = "VENDOR_DATA"
    MODEL_ESTIMATE = "MODEL_ESTIMATE"
    GROUP_DEFAULT = "GROUP_DEFAULT"
    CLASS_DEFAULT = "CLASS_DEFAULT"


class ResolutionLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class SafetyStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class Provenance(BaseModel):
    field: Optional[str] = None
    value: Any
    unit: Optional[str] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    source_id: Optional[str] = None
    source_type: Optional[SourceType] = None
    resolution_level: Optional[ResolutionLevel] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    note: Optional[str] = None


class CommodityProfile(BaseModel):
    model_config = {"populate_by_name": True}

    commodity_id: str
    names: Dict[str, List[str]] = Field(default_factory=dict)
    group: str
    commodity_class: str = Field(alias="class")  # 'class' is a reserved word
    source_id: Optional[str] = None
    
    # physical fields as Provenance
    moisture_pct: Optional[Provenance] = None
    water_activity: Optional[Provenance] = None
    fat_pct: Optional[Provenance] = None
    pH: Optional[Provenance] = None
    
    respiration_model: Optional[str] = None
    respiration_ea_kj_mol: Optional[Provenance] = None
    respiration_ref_t_c: Optional[Provenance] = None
    respiration_ref_rate: Optional[Provenance] = None
    
    storage_optimum_t_c: Optional[Provenance] = None
    storage_optimum_rh_pct: Optional[Provenance] = None
    storage_life_days: Optional[Provenance] = None
    chilling_sensitive_below_c: Optional[Provenance] = None
    
    ethylene_production: Optional[str] = None
    ethylene_sensitivity: Optional[str] = None
    ethylene_note: Optional[str] = None
    
    failure_modes: List[str] = Field(default_factory=list)
    light_sensitive: bool = False
    light_note: Optional[str] = None
    
    display_name: Optional[str] = None
    local_name: Optional[str] = None
    state_modifiers: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _parse_nested_or_flat(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        data = dict(data)
        
        # Populate display_name if missing
        if not data.get("display_name"):
            names = data.get("names", {})
            if isinstance(names, dict) and "en" in names and names["en"]:
                data["display_name"] = names["en"][0]
            elif "commodity_id" in data:
                cid = str(data["commodity_id"])
                parts = cid.split(".")
                data["display_name"] = parts[1] if len(parts) >= 2 else parts[-1]

        # Handle "class" alias if commodity_class not present
        if "commodity_class" in data and "class" not in data:
            data["class"] = data["commodity_class"]

        # Parse nested physchem block
        if "physchem" in data and isinstance(data["physchem"], dict):
            pc = data["physchem"]
            for field in ["moisture_pct", "water_activity", "fat_pct", "pH"]:
                if field in pc and field not in data:
                    item = pc[field]
                    if isinstance(item, dict):
                        rng = item.get("range") or [None, None]
                        data[field] = Provenance(
                            value=item.get("v"),
                            range_low=rng[0] if len(rng) > 0 else None,
                            range_high=rng[1] if len(rng) > 1 else None,
                            source_id=item.get("src"),
                            confidence=item.get("conf"),
                        )
                    elif isinstance(item, (int, float)):
                        data[field] = Provenance(value=item)
                    elif isinstance(item, Provenance):
                        data[field] = item

        # Parse nested respiration block
        if "respiration" in data and isinstance(data["respiration"], dict):
            resp = data["respiration"]
            if "model" in resp and "respiration_model" not in data:
                data["respiration_model"] = resp["model"]
            if "Ea_kJ_mol" in resp and "respiration_ea_kj_mol" not in data:
                data["respiration_ea_kj_mol"] = Provenance(
                    value=resp["Ea_kJ_mol"],
                    source_id=resp.get("src"),
                    confidence=resp.get("conf"),
                    unit="kJ/mol",
                )
            if "ref" in resp and isinstance(resp["ref"], dict):
                ref = resp["ref"]
                if "T_C" in ref and "respiration_ref_t_c" not in data:
                    data["respiration_ref_t_c"] = Provenance(
                        value=ref["T_C"],
                        source_id=resp.get("src"),
                        confidence=resp.get("conf"),
                        unit="degC",
                    )
                if "rCO2_mg_kg_h" in ref and "respiration_ref_rate" not in data:
                    rng = ref.get("range") or [None, None]
                    data["respiration_ref_rate"] = Provenance(
                        value=ref["rCO2_mg_kg_h"],
                        range_low=rng[0] if len(rng) > 0 else None,
                        range_high=rng[1] if len(rng) > 1 else None,
                        source_id=resp.get("src"),
                        confidence=resp.get("conf"),
                        unit="mg CO2/kg·h",
                    )

        # Parse nested storage_optimum block
        if "storage_optimum" in data and isinstance(data["storage_optimum"], dict):
            stg = data["storage_optimum"]
            src = stg.get("src")
            if "T_C" in stg and "storage_optimum_t_c" not in data:
                t_val = stg["T_C"]
                if isinstance(t_val, list):
                    data["storage_optimum_t_c"] = Provenance(
                        value=t_val,
                        range_low=t_val[0] if len(t_val) > 0 else None,
                        range_high=t_val[1] if len(t_val) > 1 else None,
                        source_id=src,
                        unit="degC",
                    )
                else:
                    data["storage_optimum_t_c"] = Provenance(value=t_val, source_id=src, unit="degC")
            if "RH_pct" in stg and "storage_optimum_rh_pct" not in data:
                rh_val = stg["RH_pct"]
                if isinstance(rh_val, list):
                    data["storage_optimum_rh_pct"] = Provenance(
                        value=rh_val,
                        range_low=rh_val[0] if len(rh_val) > 0 else None,
                        range_high=rh_val[1] if len(rh_val) > 1 else None,
                        source_id=src,
                        unit="%",
                    )
                else:
                    data["storage_optimum_rh_pct"] = Provenance(value=rh_val, source_id=src, unit="%")
            if "life_days" in stg and "storage_life_days" not in data:
                life_val = stg["life_days"]
                if isinstance(life_val, list):
                    data["storage_life_days"] = Provenance(
                        value=life_val,
                        range_low=life_val[0] if len(life_val) > 0 else None,
                        range_high=life_val[1] if len(life_val) > 1 else None,
                        source_id=src,
                        unit="days",
                    )
                else:
                    data["storage_life_days"] = Provenance(value=life_val, source_id=src, unit="days")
            if "chilling_sensitive_below_C" in stg and "chilling_sensitive_below_c" not in data:
                data["chilling_sensitive_below_c"] = Provenance(
                    value=stg["chilling_sensitive_below_C"], source_id=src, unit="degC"
                )

        # Parse nested ethylene block
        if "ethylene" in data and isinstance(data["ethylene"], dict):
            eth = data["ethylene"]
            if "production" in eth and "ethylene_production" not in data:
                data["ethylene_production"] = eth["production"]
            if "sensitivity" in eth and "ethylene_sensitivity" not in data:
                data["ethylene_sensitivity"] = eth["sensitivity"]
            if "note" in eth and "ethylene_note" not in data:
                data["ethylene_note"] = eth["note"]

        return data


class Environment(BaseModel):
    temperature: Provenance
    relative_humidity: Provenance
    duration: Provenance
    transport_mode: Optional[Provenance] = None
    storage_type: Optional[Provenance] = None

    def worst_leg(self) -> "Environment":
        """
        Returns the harshest segment of a multi-leg journey.
        For now, this returns itself as we're modelling single legs.
        When multi-leg environments are added, this will compute the worst.
        """
        return self


class PackGeometry(BaseModel):
    pack_area_m2: float = 0.055
    product_mass_kg: float = 0.10
    dry_solids_kg: Optional[float] = None
    headspace_volume_cc: float = 50.0
    headspace_o2_fraction: float = 0.01
    drop_height_m: float = 1.0
    stack_height_m: float = 2.0
    stack_height_units: Optional[int] = 10
    process: str = "ambient"  # ambient, retort, hot_fill, frozen, chilled
    filling_line: Optional[str] = None
    metal_detection_required: bool = False
    microwave_required: bool = False


class RequirementVector(BaseModel):
    max_wvtr: Optional[float] = None
    max_otr: Optional[float] = None
    min_otr: Optional[float] = None
    target_o2: Optional[float] = None
    target_co2: Optional[float] = None
    min_thickness_um: Optional[float] = None
    min_seal_strength_n_15mm: Optional[float] = None
    min_puncture: Optional[float] = None
    light_barrier_od: Optional[float] = None
    antifog_required: Optional[bool] = None
    map_required: Optional[bool] = None
    perforation_required: Optional[bool] = None
    equation_id: Optional[str] = None
    process: Optional[str] = None
    service_temp_min_c: Optional[float] = None
    service_temp_max_c: Optional[float] = None
    fat_contact: Optional[bool] = None
    regime: Optional[str] = None


class PackageCandidate(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    structure_name: Optional[str] = None
    layer_stack: List[str]
    gauge_per_layer: List[float]
    composite_thickness_um: Optional[float] = None
    sealant_layer: Optional[str] = None
    measured_otr: Optional[float] = None
    measured_wvtr: Optional[float] = None
    test_conditions: Optional[str] = None
    cost_per_pack: Optional[float] = None
    cost_inr_per_sqm: Optional[float] = None
    epr_category: Optional[str] = None
    recyclability_score: Optional[float] = None
    recyclability_notes: Optional[str] = None
    machine_compatibility: List[str] = Field(default_factory=list)
    availability: Optional[str] = None


class ShelfLifeResult(BaseModel):
    days_p10: float
    days_p50: float
    days_p90: float
    limiting_mechanism: str
    mechanism: Optional[str] = None
    confidence: float = 0.85
    distribution_samples: Optional[List[float]] = None
    all_mode_results: Dict[str, float] = Field(default_factory=dict)
    curve_points: List[Dict[str, float]] = Field(default_factory=list)
    safety_factor_applied: float
    equations_used: List[str] = Field(default_factory=list)


class SafetyVerdict(BaseModel):
    status: SafetyStatus
    rule_id: str
    message_key: str
    is_overridable: bool = True

    @field_validator("is_overridable")
    @classmethod
    def block_must_not_be_overridable(cls, v: bool, info: Any) -> bool:
        if "status" in info.data and info.data["status"] == SafetyStatus.BLOCK:
            if v is not False:
                raise ValueError("A BLOCK safety verdict cannot be overridable.")
        return v
