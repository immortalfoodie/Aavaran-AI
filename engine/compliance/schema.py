"""
Pydantic schemas and models for Aavaran data-driven compliance engine.

Strictly adheres to Section 6.1 of BLUEPRINT.md. Regulations live in versioned
YAML data files with legal citations, clause references, effective dates,
predicates, and verification timestamps.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuleEffect(str, Enum):
    BLOCK = "BLOCK"
    REQUIRE = "REQUIRE"
    CONDITIONAL = "CONDITIONAL"
    WARN = "WARN"


class RuleSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Rule(BaseModel):
    """
    Schema for individual regulatory rules as defined in Section 6.1 of BLUEPRINT.md.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = Field(..., min_length=1, description="Unique rule ID, e.g. IN-FSSAI-PKG-2018-R4e")
    jurisdiction: str = Field(..., min_length=2, description="Target jurisdiction, e.g. IN, EU, US, GLOBAL")
    instrument: str = Field(..., min_length=1, description="Statutory instrument or regulation title")
    clause: str = Field(..., min_length=1, description="Specific regulation section or clause citation")
    effective_from: date = Field(..., description="Date from which the rule applies")
    effective_until: Optional[date] = Field(None, description="Date until which the rule applies, if superseded")
    applies_when: Dict[str, Any] = Field(default_factory=dict, description="JSON-path style predicate dictionary")
    effect: RuleEffect = Field(..., description="BLOCK, REQUIRE, CONDITIONAL, or WARN")
    
    # Multilingual messages
    message_en: str = Field(..., min_length=1, description="Explanation message in English")
    message_hi: Optional[str] = Field(None, description="Explanation message in Hindi")
    message_mr: Optional[str] = Field(None, description="Explanation message in Marathi")
    messages: Dict[str, str] = Field(default_factory=dict, description="Additional language messages")

    # Optional action guidance
    action_en: Optional[str] = Field(None, description="Action required in English")
    action_hi: Optional[str] = Field(None, description="Action required in Hindi")
    action_mr: Optional[str] = Field(None, description="Action required in Marathi")

    requires_document: Optional[str] = Field(None, description="Mandatory document/certificate description")
    severity: RuleSeverity = Field(default=RuleSeverity.HIGH, description="Rule severity level")
    source_url: str = Field(..., min_length=5, description="Authoritative reference or gazette notification URL")
    last_verified: date = Field(..., description="Date when this regulatory rule was last verified by legal expert")

    @field_validator("effective_from", "effective_until", "last_verified", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return date.fromisoformat(v.strip())
        return v

    def get_message(self, lang: str = "en") -> str:
        """
        Retrieves the localized message for the given language code, falling back to English.
        """
        lang = lang.lower()
        if lang == "en":
            return self.message_en
        if lang == "hi" and self.message_hi:
            return self.message_hi
        if lang == "mr" and self.message_mr:
            return self.message_mr
        if lang in self.messages:
            return self.messages[lang]
        attr = f"message_{lang}"
        if hasattr(self, attr) and getattr(self, attr):
            return str(getattr(self, attr))
        return self.message_en

    def is_stale(self, days_threshold: int = 180, as_of: Optional[date] = None) -> bool:
        """
        Returns True if the rule's last_verified date is older than days_threshold.
        """
        ref_date = as_of or date.today()
        return (ref_date - self.last_verified).days > days_threshold

    def days_since_verified(self, as_of: Optional[date] = None) -> int:
        """
        Returns number of days elapsed since the rule was last verified.
        """
        ref_date = as_of or date.today()
        return (ref_date - self.last_verified).days

    def is_active_on(self, eval_date: Optional[date] = None) -> bool:
        """
        Returns True if the rule is in effect on eval_date.
        """
        ref_date = eval_date or date.today()
        if ref_date < self.effective_from:
            return False
        if self.effective_until is not None and ref_date > self.effective_until:
            return False
        return True


class ComplianceIssue(BaseModel):
    """
    Represents a blocking or conditional issue triggered during compliance evaluation.
    """
    rule_id: str
    effect: RuleEffect
    instrument: str
    clause: str
    message: str
    severity: RuleSeverity
    source_url: str
    requires_document: Optional[str] = None


class ComplianceWarning(BaseModel):
    """
    Represents a regulatory warning triggered during compliance evaluation.
    """
    rule_id: str
    instrument: str
    clause: str
    message: str
    severity: RuleSeverity
    source_url: str
    requires_document: Optional[str] = None


class RuleTraceEntry(BaseModel):
    """
    Trace entry representing evaluation of a single rule against a candidate package.
    Recorded for Expert mode.
    """
    rule_id: str
    jurisdiction: str
    instrument: str
    clause: str
    effect: RuleEffect
    fired: bool
    passed: bool
    severity: RuleSeverity
    message: str
    requires_document: Optional[str] = None
    source_url: str
    last_verified: date
    details: Dict[str, Any] = Field(default_factory=dict)


class ComplianceReport(BaseModel):
    """
    Comprehensive compliance evaluation report.
    Provides structured views for Kisan, Business, and Expert user modes.
    """
    is_compliant: bool
    destination_market: str
    evaluated_at: datetime = Field(default_factory=datetime.now)
    rules_evaluated_count: int
    rules_fired_count: int
    rules_passed_count: int
    rules_fired: List[Rule] = Field(default_factory=list)
    rules_passed: List[Rule] = Field(default_factory=list)
    blocking_issues: List[ComplianceIssue] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    warnings: List[ComplianceWarning] = Field(default_factory=list)
    trace: List[RuleTraceEntry] = Field(default_factory=list)

    def has_blocks(self) -> bool:
        return len(self.blocking_issues) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def kisan_view(self, lang: str = "en") -> Optional[str]:
        """
        Kisan Mode: Nothing shown unless something is illegal, then one red line.
        """
        if not self.has_blocks():
            return None
        # Return the first critical/high blocking message
        first_block = self.blocking_issues[0]
        # Match rule for localized message if available
        for r in self.rules_fired:
            if r.id == first_block.rule_id:
                return r.get_message(lang)
        return first_block.message

    def business_view(self, lang: str = "en") -> Dict[str, Any]:
        """
        Business Mode: Checklist of required documents, labelling needs, and active warnings.
        """
        checklist = []
        for doc in self.required_documents:
            checklist.append({"type": "DOCUMENT", "item": doc, "status": "MANDATORY"})
        
        warns = []
        for w in self.warnings:
            warns.append({
                "rule_id": w.rule_id,
                "message": w.message,
                "clause": f"{w.instrument}, {w.clause}",
                "severity": w.severity.value,
            })

        blocks = []
        for b in self.blocking_issues:
            blocks.append({
                "rule_id": b.rule_id,
                "message": b.message,
                "clause": f"{b.instrument}, {b.clause}",
            })

        return {
            "compliant": self.is_compliant,
            "checklist": checklist,
            "required_documents": self.required_documents,
            "warnings": warns,
            "blocking_issues": blocks,
        }

    def expert_view(self) -> Dict[str, Any]:
        """
        Expert Mode: Full rule trace with citations, fired/passed states, and predicate breakdown.
        """
        return {
            "is_compliant": self.is_compliant,
            "destination_market": self.destination_market,
            "evaluated_at": self.evaluated_at.isoformat(),
            "rules_evaluated_count": self.rules_evaluated_count,
            "rules_fired_count": self.rules_fired_count,
            "rules_passed_count": self.rules_passed_count,
            "blocking_issues": [b.model_dump() for b in self.blocking_issues],
            "required_documents": self.required_documents,
            "warnings": [w.model_dump() for w in self.warnings],
            "trace": [t.model_dump() for t in self.trace],
        }


class EprCostEstimate(BaseModel):
    """
    Indicative rupee liability for plastic packaging EPR compliance under PWM Rules 2022.
    """
    epr_category: str = Field(..., description="Category I, II, III, or IV")
    annual_volume: int = Field(..., description="Number of packaging units per year")
    pack_weight_g: float = Field(..., description="Weight of plastic per pack in grams")
    total_plastic_tonnes: float = Field(..., description="Total annual plastic tonnage in metric tonnes")
    recycling_target_pct: float = Field(..., description="Statutory recycling target percentage for financial year")
    target_obligation_tonnes: float = Field(..., description="Statutory recycling obligation in metric tonnes")
    credit_rate_inr_per_tonne: float = Field(..., description="Indicative market rate for recycling credits in INR/tonne")
    total_liability_inr: float = Field(..., description="Total annual EPR certificate procurement liability in INR")
    cost_per_pack_inr: float = Field(..., description="Indicative EPR compliance liability in INR per pack")
    is_msme_exempt: bool = Field(default=False, description="Whether Producer/Brand Owner is exempt under MSME clause")
    financial_year: str = Field(default="2026-27", description="Financial year governing targets")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="Detailed computational trace")
    notes: Optional[str] = None
