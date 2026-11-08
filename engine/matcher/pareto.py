"""
Pareto non-dominated frontier computation for Aavaran packaging candidates.

Implements Section 4.4 and Section 7 of BLUEPRINT.md:
- Computes the 3D non-dominated frontier across:
    1. Cost (minimize)
    2. Shelf life (maximize)
    3. Recyclability / Sustainability (maximize)
- Formats and structures the frontier and dominated sets in a clean schema
  that the web UI (Recharts / neo-brutalist canvas / 3D scatter) can chart directly.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from engine.matcher.score import compute_sustainability_score, estimate_shelf_life_days
from engine.types import PackageCandidate, RequirementVector

logger = logging.getLogger(__name__)


class ParetoPoint(BaseModel):
    """A single candidate evaluated in 3D multi-objective space."""

    id: str
    name: str
    layer_stack: List[str]
    cost: float = Field(..., description="Cost in INR per pack (objective to minimize)")
    shelf_life_days: float = Field(..., description="Predicted shelf life in days (objective to maximize)")
    recyclability_score: float = Field(
        ..., description="Sustainability / recyclability score in [0, 1] (objective to maximize)"
    )
    epr_category: str
    is_pareto_optimal: bool = Field(default=False)
    dominates: List[str] = Field(default_factory=list, description="IDs of candidates dominated by this point")
    dominated_by: List[str] = Field(default_factory=list, description="IDs of candidates that dominate this point")


class ParetoChartSeries(BaseModel):
    """Data structures ready for UI charting (Recharts, Chart.js, or Plotly)."""

    axes: Dict[str, str] = Field(
        default_factory=lambda: {
            "x": "Cost (₹/pack)",
            "y": "Shelf Life (days)",
            "z": "Recyclability Score (0-1)",
        }
    )
    frontier_series: List[Dict[str, Any]] = Field(default_factory=list)
    dominated_series: List[Dict[str, Any]] = Field(default_factory=list)


class ParetoFrontierResult(BaseModel):
    """Complete Pareto analysis output for the candidate pool."""

    frontier: List[ParetoPoint] = Field(..., description="The non-dominated optimal frontier")
    dominated: List[ParetoPoint] = Field(..., description="Sub-optimal dominated candidates")
    all_points: List[ParetoPoint] = Field(..., description="All evaluated points")
    chart_series: ParetoChartSeries = Field(..., description="Chart-ready series formatted for the UI")
    trade_off_notes: List[str] = Field(default_factory=list)


def dominates(a: ParetoPoint, b: ParetoPoint, eps: float = 1e-5) -> bool:
    """
    Check if point A dominates point B.
    A dominates B if:
    - Cost: A <= B
    - Shelf life: A >= B
    - Recyclability: A >= B
    AND strictly better in at least one dimension.
    """
    not_worse = (
        (a.cost <= b.cost + eps)
        and (a.shelf_life_days >= b.shelf_life_days - eps)
        and (a.recyclability_score >= b.recyclability_score - eps)
    )
    strictly_better = (
        (a.cost < b.cost - eps)
        or (a.shelf_life_days > b.shelf_life_days + eps)
        or (a.recyclability_score > b.recyclability_score + eps)
    )
    return not_worse and strictly_better


def compute_pareto_frontier(
    candidates: List[PackageCandidate],
    requirements: Optional[RequirementVector] = None,
    target_shelf_life_days: float = 180.0,
    shelf_life_map: Optional[Dict[str, float]] = None,
) -> ParetoFrontierResult:
    """
    Compute the non-dominated Pareto frontier across Cost, Shelf Life, and Recyclability.

    Args:
        candidates: List of package candidates to analyze.
        requirements: RequirementVector used to estimate shelf life if not pre-computed.
        target_shelf_life_days: Target shelf life in days.
        shelf_life_map: Optional pre-computed mapping from candidate_id to shelf_life_days.

    Returns:
        ParetoFrontierResult with non-dominated frontier and UI chart series.
    """
    req = requirements or RequirementVector(regime="non_respiring_barrier", max_wvtr=0.6, max_otr=1.2)
    sl_map = shelf_life_map or {}

    points: List[ParetoPoint] = []

    for c in candidates:
        cid = c.id or "/".join(c.layer_stack)
        cname = c.name or cid

        # Cost
        if c.cost_per_pack is not None:
            cost_val = float(c.cost_per_pack)
        elif c.cost_inr_per_sqm is not None:
            cost_val = float(c.cost_inr_per_sqm * 0.055)
        else:
            cost_val = 2.0

        # Shelf life
        if cid in sl_map:
            sl_days = float(sl_map[cid])
        else:
            sl_days, _ = estimate_shelf_life_days(c, req, target_shelf_life_days)

        # Sustainability
        sust_score = compute_sustainability_score(c)

        points.append(
            ParetoPoint(
                id=cid,
                name=cname,
                layer_stack=c.layer_stack,
                cost=round(cost_val, 2),
                shelf_life_days=round(sl_days, 1),
                recyclability_score=round(sust_score, 2),
                epr_category=c.epr_category or "Cat III",
                is_pareto_optimal=False,
            )
        )

    # Compute pairwise dominance
    n = len(points)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if dominates(points[i], points[j]):
                points[i].dominates.append(points[j].id)
                points[j].dominated_by.append(points[i].id)

    # Classify into frontier and dominated sets
    frontier: List[ParetoPoint] = []
    dominated_points: List[ParetoPoint] = []

    for p in points:
        if len(p.dominated_by) == 0:
            p.is_pareto_optimal = True
            frontier.append(p)
        else:
            p.is_pareto_optimal = False
            dominated_points.append(p)

    # Sort frontier by cost ascending
    frontier.sort(key=lambda p: p.cost)

    # Generate chart series for UI consumption
    frontier_series: List[Dict[str, Any]] = [
        {
            "id": p.id,
            "name": p.name,
            "cost": p.cost,
            "shelf_life_days": p.shelf_life_days,
            "recyclability_score": p.recyclability_score,
            "epr_category": p.epr_category,
            "is_pareto_optimal": True,
        }
        for p in frontier
    ]

    dominated_series: List[Dict[str, Any]] = [
        {
            "id": p.id,
            "name": p.name,
            "cost": p.cost,
            "shelf_life_days": p.shelf_life_days,
            "recyclability_score": p.recyclability_score,
            "epr_category": p.epr_category,
            "is_pareto_optimal": False,
            "dominated_by": p.dominated_by,
        }
        for p in dominated_points
    ]

    # Generate human-readable trade-off notes
    notes: List[str] = []
    if frontier:
        cheapest = min(frontier, key=lambda p: p.cost)
        longest = max(frontier, key=lambda p: p.shelf_life_days)
        greenest = max(frontier, key=lambda p: p.recyclability_score)

        notes.append(
            f"Lowest cost option: '{cheapest.name}' at ₹{cheapest.cost:.2f}/pack "
            f"({cheapest.shelf_life_days:.0f} days shelf life, {cheapest.epr_category})."
        )
        if longest.id != cheapest.id:
            notes.append(
                f"Maximum shelf life: '{longest.name}' with {longest.shelf_life_days:.0f} days "
                f"(₹{longest.cost:.2f}/pack, {longest.epr_category})."
            )
        if greenest.id != cheapest.id and greenest.id != longest.id:
            notes.append(
                f"Highest recyclability: '{greenest.name}' in {greenest.epr_category} "
                f"(score {greenest.recyclability_score:.2f}, ₹{greenest.cost:.2f}/pack)."
            )

    return ParetoFrontierResult(
        frontier=frontier,
        dominated=dominated_points,
        all_points=points,
        chart_series=ParetoChartSeries(
            frontier_series=frontier_series,
            dominated_series=dominated_series,
        ),
        trade_off_notes=notes,
    )
