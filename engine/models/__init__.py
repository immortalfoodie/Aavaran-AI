"""
Aavaran Engine Food Physics Models:
- Moisture (Linear, BET, GAB sorption isotherms, shelf-life, and required WVTR)
- Oxidation (Oxygen budget, headspace O2 tracking, shelf-life, and required OTR)
- Respiration (Arrhenius kinetics, Q10 fallback, physiological state modifiers)
- MAP Design (Required OTR/CO2TR, selectivity classification, perforation sizing,
  equilibrium atmosphere solver)
"""

from engine.models.map_design import (
    MIN_EQUILIBRIUM_O2_FLOOR,
    PERFORATION_SELECTIVITY,
    POLYOLEFIN_SELECTIVITY_RANGE,
    CO2TRRequirementMAPResult,
    EquilibriumAtmosphereResult,
    NoSolution,
    OTRRequirementMAPResult,
    PerforationResult,
    SelectivityRecommendation,
    SelectivityResult,
    equilibrium_atmosphere,
    perforation_design,
    required_co2tr,
    required_selectivity,
)
from engine.models.map_design import (
    required_otr as required_map_otr,
)
from engine.models.microbial import (
    COMBASE_ORGANISMS,
    MicrobialGrowthResult,
    MicrobialShelfLifeResult,
    OrganismParams,
    get_organism_params,
    ratkowsky_growth_rate,
    time_to_spoilage,
)
from engine.models.moisture import (
    BETIsotherm,
    GABIsotherm,
    LinearIsotherm,
    MoistureShelfLifeResult,
    WVTRRequirementResult,
    astm_f1249_test_driving_force_kpa,
    required_wvtr,
    saturation_vapor_pressure_kpa,
    shelf_life_moisture_limited,
)
from engine.models.oxidation import (
    DEFAULT_AIR_O2_FRACTION,
    DEFAULT_FLUSH_O2_FRACTION,
    O2_DENSITY_MG_PER_CC,
    OTRRequirementResult,
    OxidationShelfLifeResult,
    required_otr,
    shelf_life_oxidation_limited,
)
from engine.models.respiration import (
    STATE_MODIFIER_RANGES,
    RespirationRateResult,
    StateModifiedRateResult,
    apply_state_modifiers,
    rate_at_temperature,
)
from engine.models.safety import (
    RULE_ACIDIFIED,
    RULE_ALLERGEN,
    RULE_BOTULINUM,
    RULE_FRESH_CUT,
    RULE_HISTAMINE,
    RULE_LIGHT_GENERAL,
    RULE_LIGHT_POTATO,
    acidified_gate,
    allergen_crosscontact_gate,
    botulinum_gate,
    enforce_safety_interlock,
    fresh_cut_gate,
    histamine_gate,
    light_gate,
    safety_gate,
)

__all__ = [
    # Moisture
    "LinearIsotherm",
    "BETIsotherm",
    "GABIsotherm",
    "MoistureShelfLifeResult",
    "WVTRRequirementResult",
    "shelf_life_moisture_limited",
    "required_wvtr",
    "saturation_vapor_pressure_kpa",
    "astm_f1249_test_driving_force_kpa",
    # Oxidation
    "OxidationShelfLifeResult",
    "OTRRequirementResult",
    "shelf_life_oxidation_limited",
    "required_otr",
    "O2_DENSITY_MG_PER_CC",
    "DEFAULT_AIR_O2_FRACTION",
    "DEFAULT_FLUSH_O2_FRACTION",
    # Respiration
    "rate_at_temperature",
    "apply_state_modifiers",
    "RespirationRateResult",
    "StateModifiedRateResult",
    "STATE_MODIFIER_RANGES",
    # MAP Design
    "required_map_otr",
    "required_co2tr",
    "required_selectivity",
    "perforation_design",
    "equilibrium_atmosphere",
    "SelectivityRecommendation",
    "SelectivityResult",
    "PerforationResult",
    "EquilibriumAtmosphereResult",
    "NoSolution",
    "PERFORATION_SELECTIVITY",
    "POLYOLEFIN_SELECTIVITY_RANGE",
    "MIN_EQUILIBRIUM_O2_FLOOR",
    "OTRRequirementMAPResult",
    "CO2TRRequirementMAPResult",
    # Microbial
    "OrganismParams",
    "COMBASE_ORGANISMS",
    "get_organism_params",
    "MicrobialGrowthResult",
    "MicrobialShelfLifeResult",
    "ratkowsky_growth_rate",
    "time_to_spoilage",
    # Safety
    "botulinum_gate",
    "fresh_cut_gate",
    "light_gate",
    "acidified_gate",
    "histamine_gate",
    "allergen_crosscontact_gate",
    "safety_gate",
    "enforce_safety_interlock",
    "RULE_BOTULINUM",
    "RULE_FRESH_CUT",
    "RULE_LIGHT_POTATO",
    "RULE_LIGHT_GENERAL",
    "RULE_ACIDIFIED",
    "RULE_HISTAMINE",
    "RULE_ALLERGEN",
]

