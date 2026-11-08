from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from engine.types import (
    CommodityProfile,
    Environment,
    RequirementVector,
    PackageCandidate,
    ShelfLifeResult,
    SafetyVerdict,
    Provenance,
)

class ResolvedInputs(BaseModel):
    commodity: Optional[CommodityProfile] = None
    environment: Optional[Environment] = None
    state_modifiers: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)

class ValueOfInformation(BaseModel):
    field: str
    variance_reduction: float
    description: str

class EquationInput(BaseModel):
    value: Any
    unit: str = ""
    source: str = ""

class EquationOutput(BaseModel):
    value: Any
    unit: str = ""

class EquationItem(BaseModel):
    equation_id: str
    name: str
    formula_template: str
    inputs: Dict[str, EquationInput] = Field(default_factory=dict)
    output: EquationOutput
    citation: Optional[str] = None

class SensitivityItem(BaseModel):
    parameter: str
    variance_reduction_pct: float
    direction: str = "negative"

class EvaluatedRule(BaseModel):
    rule_id: str
    instrument: str
    clause: str
    status: str  # PASS, WARN, BLOCK
    effect: str  # REQUIRE, CONDITIONAL, WARN, BLOCK, ALLOW
    message: Optional[str] = None

class ComplianceSummary(BaseModel):
    is_compliant: bool = True
    destination_market: str = "IN"
    rules_evaluated: List[EvaluatedRule] = Field(default_factory=list)

class RecommendationDetail(BaseModel):
    packaging_name: str
    packaging_description: Optional[str] = None
    kisan_instruction: Optional[str] = None
    key_action: Optional[str] = None

class SealedResult(BaseModel):
    result_id: str
    engine_version: str
    kb_version: str
    ruleset_version: str
    
    resolved: ResolvedInputs
    assumptions: List[Provenance] = Field(default_factory=list)
    requirements: Optional[RequirementVector] = None
    candidates: List[PackageCandidate] = Field(default_factory=list)
    recommendation: Optional[RecommendationDetail] = None
    
    shelf_life: Optional[ShelfLifeResult] = None
    safety: Optional[SafetyVerdict] = None
    verdict: str
    guidance: List[Dict[str, Any]] = Field(default_factory=list)
    
    value_of_information: Optional[ValueOfInformation] = None
    equations: List[EquationItem] = Field(default_factory=list)
    sensitivity: List[SensitivityItem] = Field(default_factory=list)
    compliance: Optional[ComplianceSummary] = None
    citations: List[str] = Field(default_factory=list)
    computed_at: datetime
    
    def to_audit_log(self) -> str:
        """
        Emits a flat, human-readable trace of the decision process.
        """
        log = []
        log.append(f"--- AAVARAN AUDIT LOG: {self.result_id} ---")
        log.append(f"Computed at: {self.computed_at.isoformat()}")
        log.append(f"Engine: {self.engine_version} | KB: {self.kb_version} | Ruleset: {self.ruleset_version}")
        log.append(f"Verdict: {self.verdict}")
        
        if self.safety:
            log.append(f"Safety: {self.safety.status.value} (Rule: {self.safety.rule_id}) - {self.safety.message_key}")
            
        log.append("\nRESOLVED INPUTS:")
        if self.resolved.commodity:
            log.append(f"- Commodity: {self.resolved.commodity.commodity_id}")
            log.append(f"- Class: {self.resolved.commodity.commodity_class}")
        if self.resolved.environment:
            env = self.resolved.environment
            log.append(f"- Environment: T={env.temperature.value}{env.temperature.unit}, RH={env.relative_humidity.value}{env.relative_humidity.unit}")
            
        log.append("\nASSUMPTIONS LEDGER:")
        for asm in self.assumptions:
            conf_str = f"{asm.confidence:.2f}" if asm.confidence is not None else "N/A"
            log.append(f"- {asm.note} | Value: {asm.value} {asm.unit} | Source: {asm.source_type} ({asm.source_id}) | Conf: {conf_str}")
            
        if self.requirements:
            log.append("\nREQUIREMENTS VECTOR:")
            for k, v in self.requirements.model_dump(exclude_none=True).items():
                log.append(f"- {k}: {v}")
                
        if self.shelf_life:
            log.append("\nSHELF LIFE PREDICITON:")
            log.append(f"- P50: {self.shelf_life.days_p50} days")
            log.append(f"- Mechanism: {self.shelf_life.limiting_mechanism}")
            log.append(f"- Equations: {', '.join(self.shelf_life.equations_used)}")
            
        if self.candidates:
            log.append("\nPACKAGE CANDIDATES:")
            for i, cand in enumerate(self.candidates, 1):
                log.append(f"  {i}. {'/'.join(cand.layer_stack)}")
                log.append(f"     Cost: {cand.cost_per_pack} | EPR: {cand.epr_category}")
                
        if self.citations:
            log.append("\nCITATIONS:")
            for c in self.citations:
                log.append(f"- {c}")
                
        log.append("--- END OF LOG ---")
        return "\n".join(log)
