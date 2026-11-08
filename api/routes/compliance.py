"""
Compliance API routes for Aavaran.

Provides endpoints for:
- Evaluating packaging compliance across jurisdictions (IN, EU, US).
- Estimating Plastic Waste Management (PWM) EPR liability in Indian Rupees.
- Admin dashboard endpoint for regulatory staleness monitoring (>180 days).
"""

from datetime import date
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from engine.compliance import (
    ComplianceReport,
    EprCostEstimate,
    Rule,
    epr_cost_estimate,
    evaluate,
    get_rule_engine,
)

router = APIRouter(prefix="", tags=["Compliance"])


class EvaluateRequest(BaseModel):
    package: Dict[str, Any] = Field(default_factory=dict, description="Candidate packaging structure details")
    product: Dict[str, Any] = Field(default_factory=dict, description="Commodity/product profile details")
    destination_market: str = Field(default="IN", description="Target market code: IN, EU, US, or GLOBAL")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional contextual flags")
    eval_date: Optional[date] = Field(default=None, description="Evaluation reference date (default: today)")


class EprEstimateRequest(BaseModel):
    structure: Union[Dict[str, Any], str] = Field(..., description="Package structure or EPR category name")
    annual_volume: int = Field(..., gt=0, description="Annual packaging volume (units)")
    pack_area_m2: float = Field(default=0.055, gt=0, description="Pack surface area in m²")
    pack_weight_g: Optional[float] = Field(default=None, gt=0, description="Direct pack weight in grams")
    is_msme: bool = Field(default=False, description="Micro/Small enterprise exemption flag")
    financial_year: str = Field(default="2026-27", description="Target financial year ('2024-25' to '2027-28')")
    custom_credit_rates: Optional[Dict[str, float]] = Field(default=None, description="Custom EPR credit rates (INR/tonne)")


class StaleRuleItem(BaseModel):
    id: str
    jurisdiction: str
    instrument: str
    clause: str
    effect: str
    severity: str
    last_verified: date
    days_since_verified: int
    source_url: str


class StaleRulesResponse(BaseModel):
    total_rules_count: int
    stale_rules_count: int
    fresh_rules_count: int
    days_threshold: int
    as_of_date: date
    stale_rules: List[StaleRuleItem]


# ---------------------------------------------------------------------------
# Evaluation & EPR Endpoints
# ---------------------------------------------------------------------------

@router.post("/compliance/evaluate", response_model=ComplianceReport)
@router.post("/api/v1/compliance/check", response_model=ComplianceReport)
def evaluate_compliance(request: EvaluateRequest) -> ComplianceReport:
    """
    Evaluates a candidate package plus product against all active regulations
    for the destination market.
    """
    try:
        report = evaluate(
            package=request.package,
            product=request.product,
            destination_market=request.destination_market,
            context=request.context,
            eval_date=request.eval_date,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance evaluation failed: {str(e)}")


@router.post("/compliance/epr-estimate", response_model=EprCostEstimate)
def estimate_epr_cost(request: EprEstimateRequest) -> EprCostEstimate:
    """
    Calculates the indicative annual rupee liability and per-pack EPR cost
    under India's Plastic Waste Management (PWM) Rules 2022.
    """
    try:
        return epr_cost_estimate(
            structure=request.structure,
            annual_volume=request.annual_volume,
            pack_area_m2=request.pack_area_m2,
            pack_weight_g=request.pack_weight_g,
            is_msme=request.is_msme,
            financial_year=request.financial_year,
            custom_credit_rates=request.custom_credit_rates,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EPR estimation failed: {str(e)}")


@router.get("/compliance/rules", response_model=List[Rule])
def list_rules(
    jurisdiction: Optional[str] = Query(None, description="Filter rules by jurisdiction (IN, EU, US)"),
    effect: Optional[str] = Query(None, description="Filter rules by effect (BLOCK, REQUIRE, CONDITIONAL, WARN)"),
) -> List[Rule]:
    """Lists all loaded regulatory rules with optional filters."""
    eng = get_rule_engine()
    rules = eng.rules
    if jurisdiction:
        jur = jurisdiction.upper()
        rules = [r for r in rules if r.jurisdiction.upper() == jur]
    if effect:
        eff = effect.upper()
        rules = [r for r in rules if r.effect.value == eff]
    return rules


# ---------------------------------------------------------------------------
# Admin Regulatory Staleness Dashboard Endpoint
# ---------------------------------------------------------------------------

def _get_stale_rules_response(days_threshold: int, as_of: Optional[date]) -> StaleRulesResponse:
    eng = get_rule_engine()
    ref_date = as_of or date.today()
    all_rules = eng.rules
    stale_rules = eng.get_stale_rules(days_threshold=days_threshold, as_of=ref_date)

    stale_items = [
        StaleRuleItem(
            id=r.id,
            jurisdiction=r.jurisdiction,
            instrument=r.instrument,
            clause=r.clause,
            effect=r.effect.value,
            severity=r.severity.value,
            last_verified=r.last_verified,
            days_since_verified=r.days_since_verified(ref_date),
            source_url=r.source_url,
        )
        for r in stale_rules
    ]

    return StaleRulesResponse(
        total_rules_count=len(all_rules),
        stale_rules_count=len(stale_items),
        fresh_rules_count=len(all_rules) - len(stale_items),
        days_threshold=days_threshold,
        as_of_date=ref_date,
        stale_rules=stale_items,
    )


@router.get("/admin/compliance/stale-rules", response_model=StaleRulesResponse)
def admin_compliance_stale_rules(
    days_threshold: int = Query(180, description="Staleness threshold in days"),
    as_of: Optional[date] = Query(None, description="Reference date (defaults to today)"),
) -> StaleRulesResponse:
    """
    Admin Dashboard: Identifies regulations whose last_verified date is older
    than days_threshold (default 180 days) to prevent regulatory staleness.
    """
    return _get_stale_rules_response(days_threshold, as_of)


@router.get("/compliance/stale-rules", response_model=StaleRulesResponse)
def compliance_stale_rules(
    days_threshold: int = Query(180, description="Staleness threshold in days"),
    as_of: Optional[date] = Query(None, description="Reference date (defaults to today)"),
) -> StaleRulesResponse:
    """Alias for admin stale rules endpoint."""
    return _get_stale_rules_response(days_threshold, as_of)
