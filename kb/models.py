"""
Pydantic schemas and validation records for Aavaran Knowledge Base entries.

All records enforce non-negative physical bounds, mandatory test conditions,
and source attribution constraints.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class SourceRecord(BaseModel):
    id: str = Field(..., min_length=1, description="Unique source citation identifier, e.g. USDA-AH66")
    source_type: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    citation: str = Field(..., min_length=1)
    url: Optional[str] = None
    doi: Optional[str] = None
    publication_year: Optional[int] = Field(None, ge=1800, le=2100)
    notes: Optional[str] = None


class FilmRecord(BaseModel):
    id: str = Field(..., min_length=1)
    film_name: str = Field(..., min_length=1)
    thickness_um: float = Field(..., gt=0, le=2000, description="Normalized thickness in micrometres (~25 um)")
    
    # Oxygen Transmission Rate (cc / m² · day)
    otr_value: float = Field(..., ge=0, le=500000, description="OTR at specified test conditions")
    otr_min: Optional[float] = Field(None, ge=0, le=500000)
    otr_max: Optional[float] = Field(None, ge=0, le=500000)
    otr_test_temperature_c: float = Field(..., ge=-20, le=100)
    otr_test_rh_pct: float = Field(..., ge=0, le=100)
    otr_test_method: str = Field(..., min_length=2, description="e.g. ASTM D3985")
    
    # Water Vapour Transmission Rate (g / m² · day)
    wvtr_value: float = Field(..., ge=0, le=5000, description="WVTR at specified test conditions")
    wvtr_min: Optional[float] = Field(None, ge=0, le=5000)
    wvtr_max: Optional[float] = Field(None, ge=0, le=5000)
    wvtr_test_temperature_c: float = Field(..., ge=-20, le=100)
    wvtr_test_rh_pct: float = Field(..., ge=0, le=100)
    wvtr_test_method: str = Field(..., min_length=2, description="e.g. ASTM F1249")
    
    barrier_class: str = Field(..., min_length=1)
    typical_use: str = Field(..., min_length=1)
    epr_category: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_bounds_and_conditions(self) -> "FilmRecord":
        if self.otr_min is not None and self.otr_max is not None and self.otr_min > self.otr_max:
            raise ValueError(f"Film {self.id}: otr_min ({self.otr_min}) cannot exceed otr_max ({self.otr_max})")
        if self.wvtr_min is not None and self.wvtr_max is not None and self.wvtr_min > self.wvtr_max:
            raise ValueError(f"Film {self.id}: wvtr_min ({self.wvtr_min}) cannot exceed wvtr_max ({self.wvtr_max})")
        if not self.otr_test_method.strip():
            raise ValueError(f"Film {self.id}: OTR test method must not be empty.")
        if not self.wvtr_test_method.strip():
            raise ValueError(f"Film {self.id}: WVTR test method must not be empty.")
        return self


class StructureRecord(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    layer_stack: List[str] = Field(..., min_length=1)
    gauge_per_layer_um: List[float] = Field(..., min_length=1)
    composite_thickness_um: float = Field(..., gt=0)
    measured_otr: float = Field(..., ge=0, le=500000)
    measured_wvtr: float = Field(..., ge=0, le=5000)
    otr_test_conditions: str = Field(..., min_length=2)
    wvtr_test_conditions: str = Field(..., min_length=2)
    cost_inr_per_sqm: float = Field(..., gt=0, description="Indicative Indian rupee cost per square metre")
    indicative_cost_per_pack: Optional[float] = Field(None, ge=0)
    epr_category: str = Field(..., min_length=1)
    recyclability_notes: Optional[str] = None
    typical_applications: Optional[str] = None
    source_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_layers(self) -> "StructureRecord":
        if len(self.layer_stack) != len(self.gauge_per_layer_um):
            raise ValueError(
                f"Structure {self.id}: layer_stack count ({len(self.layer_stack)}) "
                f"does not match gauge_per_layer_um count ({len(self.gauge_per_layer_um)})"
            )
        for g in self.gauge_per_layer_um:
            if g <= 0:
                raise ValueError(f"Structure {self.id}: gauge per layer must be positive, got {g}")
        return self


class IsothermRecord(BaseModel):
    id: str = Field(..., min_length=1)
    food_class_or_commodity: str = Field(..., min_length=1)
    model_type: str = Field(..., description="GAB, BET, or LINEAR")
    temperature_c: float = Field(..., ge=-20, le=80)
    m0: Optional[float] = Field(None, gt=0, description="Monolayer moisture content (g water/100g dry solids)")
    c_g: Optional[float] = Field(None, gt=0, description="Guggenheim constant")
    k: Optional[float] = Field(None, gt=0, le=1.5, description="GAB multilayer factor")
    linear_slope_b: Optional[float] = None
    linear_intercept_c: Optional[float] = None
    aw_min: Optional[float] = Field(None, ge=0, le=1.0)
    aw_max: Optional[float] = Field(None, ge=0, le=1.0)
    aw_crit: Optional[float] = Field(None, ge=0, le=1.0, description="Critical water activity threshold")
    source_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_isotherm_params(self) -> "IsothermRecord":
        if self.model_type.upper() == "GAB":
            if self.m0 is None or self.c_g is None or self.k is None:
                raise ValueError(f"Isotherm {self.id}: GAB model requires m0, c_g, and k to be specified.")
        elif self.model_type.upper() == "LINEAR":
            if self.linear_slope_b is None or self.linear_intercept_c is None:
                raise ValueError(f"Isotherm {self.id}: LINEAR model requires linear_slope_b and linear_intercept_c.")
        return self


class MapTargetRecord(BaseModel):
    id: str = Field(..., min_length=1)
    product_group: str = Field(..., min_length=1)
    target_o2_min: float = Field(..., ge=0, le=100)
    target_o2_max: float = Field(..., ge=0, le=100)
    target_co2_min: float = Field(..., ge=0, le=100)
    target_co2_max: float = Field(..., ge=0, le=100)
    o2_floor: float = Field(..., ge=0, le=100, description="Minimum safe equilibrium O2 floor (e.g. 2.0% for produce)")
    co2_injury_ceiling: float = Field(..., ge=0, le=100, description="Maximum CO2 tolerated before physiological injury")
    balance_gas: str = Field(default="N2")
    optimum_temp_c_min: Optional[float] = None
    optimum_temp_c_max: Optional[float] = None
    notes: Optional[str] = None
    source_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_map_envelopes(self) -> "MapTargetRecord":
        if self.target_o2_min > self.target_o2_max:
            raise ValueError(f"MAP target {self.id}: target_o2_min ({self.target_o2_min}) > target_o2_max ({self.target_o2_max})")
        if self.target_co2_min > self.target_co2_max:
            raise ValueError(f"MAP target {self.id}: target_co2_min ({self.target_co2_min}) > target_co2_max ({self.target_co2_max})")
        if self.target_o2_min < self.o2_floor:
            # target minimum should not be below safety floor unless intentional anaerobic regime (e.g. meat/dairy)
            pass
        return self


class StateModifierRecord(BaseModel):
    id: str = Field(..., min_length=1)
    modifier_name: str = Field(..., min_length=1)
    commodity_group: str = Field(..., min_length=1)
    respiration_factor_min: Optional[float] = Field(None, ge=0)
    respiration_factor_max: Optional[float] = Field(None, ge=0)
    ethylene_factor_min: Optional[float] = Field(None, ge=0)
    ethylene_factor_max: Optional[float] = Field(None, ge=0)
    aw_delta: Optional[float] = None
    microbial_risk_level: Optional[str] = None
    new_failure_mode: Optional[str] = None
    max_ambient_hours: Optional[float] = Field(None, ge=0)
    life_factor_min: Optional[float] = Field(None, ge=0)
    life_factor_max: Optional[float] = Field(None, ge=0)
    requires_antifog: bool = False
    description: Optional[str] = None
    source_id: str = Field(..., min_length=1)


class CommodityAliasRecord(BaseModel):
    id: Optional[int] = None
    commodity_id: str = Field(..., min_length=1)
    alias: str = Field(..., min_length=1)
    language: str = Field(..., min_length=2, max_length=10)
    embedding: Optional[List[float]] = None
    source_id: str = Field(..., min_length=1)


class KnowledgeBaseData(BaseModel):
    version: str
    sources: Dict[str, SourceRecord]
    commodities: Dict[str, BaseModel]
    films: Dict[str, FilmRecord]
    structures: Dict[str, StructureRecord]
    isotherms: Dict[str, IsothermRecord]
    map_targets: Dict[str, MapTargetRecord]
    state_modifiers: Dict[str, StateModifierRecord]
    aliases: List[CommodityAliasRecord]
