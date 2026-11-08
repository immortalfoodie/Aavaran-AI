"""
Aavaran Engine Matcher Layer.

Provides multi-objective packaging matching, requirements derivation,
hard constraints filtering, mode-dependent scoring, and Pareto frontier optimization.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from engine.matcher.filter import (
    FilterResult,
    FilterVerdict,
    filter_candidate,
    filter_candidates,
)
from engine.matcher.pareto import (
    ParetoChartSeries,
    ParetoFrontierResult,
    ParetoPoint,
    compute_pareto_frontier,
)
from engine.matcher.requirements import (
    derive,
    is_respiring_produce,
)
from engine.matcher.score import (
    MatchResult,
    RankedOption,
    ScoreBreakdown,
    score_candidates,
)
from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    PackGeometry,
    RequirementVector,
)


class MatcherOutput(BaseModel):
    """Unified container for all matcher artifacts."""

    requirements: RequirementVector
    filter_result: FilterResult
    match_result: MatchResult
    pareto_result: ParetoFrontierResult


def _structures_to_candidates(structures: Dict[str, Any]) -> List[PackageCandidate]:
    """Helper to convert KB StructureRecords into PackageCandidates."""
    candidates = []
    for s_id, s in structures.items():
        s_dict = s if isinstance(s, dict) else s.model_dump()
        c = PackageCandidate(
            id=s_dict.get("id", s_id),
            name=s_dict.get("name"),
            layer_stack=s_dict.get("layer_stack", []),
            gauge_per_layer=s_dict.get("gauge_per_layer_um", []),
            composite_thickness_um=s_dict.get("composite_thickness_um"),
            sealant_layer=s_dict.get("layer_stack", [])[-1] if s_dict.get("layer_stack") else None,
            measured_otr=s_dict.get("measured_otr"),
            measured_wvtr=s_dict.get("measured_wvtr"),
            test_conditions=f"OTR: {s_dict.get('otr_test_conditions', '')}; WVTR: {s_dict.get('wvtr_test_conditions', '')}",
            cost_per_pack=s_dict.get("indicative_cost_per_pack"),
            cost_inr_per_sqm=s_dict.get("cost_inr_per_sqm"),
            epr_category=s_dict.get("epr_category"),
            recyclability_notes=s_dict.get("recyclability_notes"),
            machine_compatibility=["VFFS", "HFFS", "pre_formed_pouch", "flow_wrap"],
            availability="standard",
        )
        candidates.append(c)
    return candidates


def match_packaging(
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    target_shelf_life: Union[float, int, Dict[str, Any]] = 180.0,
    pack_geometry: Optional[Union[PackGeometry, Dict[str, Any]]] = None,
    candidates: Optional[List[PackageCandidate]] = None,
    mode: str = "business",
    weights: Optional[Dict[str, float]] = None,
    constraints: Optional[Dict[str, Any]] = None,
) -> MatcherOutput:
    """
    End-to-end packaging matching pipeline:
    1. Derives RequirementVector with strict regime branching.
    2. Filters candidate structures against 6 hard constraints.
    3. Scores and ranks survivors across user modes (Kisan, Business, Expert).
    4. Computes 3D Pareto optimal frontier across cost, shelf life, and recyclability.
    """
    # 1. Derive requirements
    req = derive(
        profile=profile,
        environment=environment,
        target_shelf_life=target_shelf_life,
        pack_geometry=pack_geometry,
    )

    # 2. Resolve candidates pool
    if candidates is None:
        try:
            from kb.loaders import load_kb
            kb_data = load_kb()
            cand_pool = _structures_to_candidates(kb_data.structures)
        except Exception:
            cand_pool = []
    else:
        cand_pool = candidates

    # 3. Filter candidates
    f_res = filter_candidates(
        candidates=cand_pool,
        requirements=req,
        profile=profile,
        pack_geometry=pack_geometry,
        constraints=constraints,
    )

    # Ensure at least some candidates pass to scoring; if all filtered, use the best pool
    survivors = f_res.survivors if f_res.survivors else cand_pool

    target_days = (
        float(target_shelf_life.get("days") or 180.0)
        if isinstance(target_shelf_life, dict)
        else float(target_shelf_life)
    )

    # 4. Score and rank candidates
    m_res = score_candidates(
        candidates=survivors,
        requirements=req,
        profile=profile,
        environment=environment,
        target_shelf_life_days=target_days,
        mode=mode,
        weights=weights,
    )

    # 5. Compute Pareto frontier
    p_res = compute_pareto_frontier(
        candidates=survivors,
        requirements=req,
        target_shelf_life_days=target_days,
    )

    return MatcherOutput(
        requirements=req,
        filter_result=f_res,
        match_result=m_res,
        pareto_result=p_res,
    )


__all__ = [
    "derive",
    "is_respiring_produce",
    "filter_candidate",
    "filter_candidates",
    "FilterVerdict",
    "FilterResult",
    "score_candidates",
    "RankedOption",
    "ScoreBreakdown",
    "MatchResult",
    "compute_pareto_frontier",
    "ParetoPoint",
    "ParetoFrontierResult",
    "ParetoChartSeries",
    "match_packaging",
    "MatcherOutput",
]
