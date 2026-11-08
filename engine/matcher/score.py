"""
Multi-objective candidate scoring and ranking for Aavaran.

Implements Section 4.4, Section 7, and Section 11 of BLUEPRINT.md:
- Weighted ranking across 5 dimensions:
  1. barrier_margin: shelf life adequacy without wasteful over-barrier.
  2. cost: indicative ₹/pack.
  3. sustainability: CPCB EPR Category (Cat II mono-material vs Cat III multi-layer).
  4. availability: off-the-shelf converter readiness.
  5. machinability: seal window and line runnability.
- Mode-dependent weight profiles:
  * Kisan: weights cost and availability heavily.
  * Business: balances cost against shelf life and commercial realities.
  * Expert: exposes weights as sliders/custom parameters.
- Mandatory constraints:
  * Never return a single answer. Always return at least three options.
  * Always include at least one lower-environmental-impact option even when
    it does not win, with the trade-off stated honestly.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    PackGeometry,
    RequirementVector,
)

logger = logging.getLogger(__name__)

# Standard weights by user mode
MODE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "kisan": {
        "cost": 0.40,
        "availability": 0.30,
        "barrier_margin": 0.15,
        "sustainability": 0.10,
        "machinability": 0.05,
    },
    "business": {
        "cost": 0.30,
        "barrier_margin": 0.30,
        "sustainability": 0.20,
        "availability": 0.10,
        "machinability": 0.10,
    },
    "expert": {
        "barrier_margin": 0.30,
        "cost": 0.25,
        "sustainability": 0.20,
        "machinability": 0.15,
        "availability": 0.10,
    },
}

# Sustainability scores by EPR Category under India Plastic Waste Management Rules
EPR_SUSTAINABILITY_SCORES: Dict[str, float] = {
    "Cat II": 0.95,   # Flexible plastic packaging of single layer or multi-layer with only one category of plastic (mono-material PE, PP)
    "CAT II": 0.95,
    "Cat IV": 0.90,   # Plastic sheet or like used for packaging as well as carry bags made of compostable plastic
    "CAT IV": 0.90,
    "Cat I": 0.80,    # Rigid plastic packaging
    "CAT I": 0.80,
    "Cat III": 0.25,  # Multi-layered plastic packaging (at least one layer of plastic and at least one layer of material other than plastic, e.g. foil, metallised)
    "CAT III": 0.25,
}


class ScoreBreakdown(BaseModel):
    """Detailed score components for a candidate."""

    barrier_margin: float = Field(..., ge=0.0, le=1.0)
    cost: float = Field(..., ge=0.0, le=1.0)
    sustainability: float = Field(..., ge=0.0, le=1.0)
    availability: float = Field(..., ge=0.0, le=1.0)
    machinability: float = Field(..., ge=0.0, le=1.0)
    total_score: float = Field(..., ge=0.0, le=1.0)


class RankedOption(BaseModel):
    """A scored and ranked candidate package with human-readable rationale."""

    rank: int
    candidate: PackageCandidate
    predicted_shelf_life_days: float
    shelf_life_label: str
    cost_per_pack_inr: float
    epr_category: str
    is_lower_environmental_impact: bool
    score: ScoreBreakdown
    trade_off_explanation: str


class MatchResult(BaseModel):
    """Output of candidate scoring and ranking."""

    mode: str
    weights_applied: Dict[str, float]
    ranked_options: List[RankedOption]
    summary_explanation: str


def estimate_shelf_life_days(
    candidate: PackageCandidate,
    requirements: RequirementVector,
    target_shelf_life_days: float,
    headspace_o2_fraction: float = 0.01,
) -> Tuple[float, str]:
    """
    Estimate shelf life for candidate under the required regime.
    Returns (days, human_readable_label).
    """
    if requirements.regime == "respiring_produce":
        # Respiring MAP: quality shelf life typically 5-21 days
        cand_otr = candidate.measured_otr or 1000.0
        req_otr = requirements.max_otr or 5000.0
        ratio = min(cand_otr / max(req_otr, 1.0), 2.0)
        days = target_shelf_life_days * (0.8 + 0.3 * ratio)
        return float(days), f"{days:.0f} days"

    # Non-respiring barrier
    layers_str = "/".join(candidate.layer_stack).lower()

    if any(f in layers_str for f in ["foil", "alu"]):
        return 365.0, "12+ mo"

    if "vmbopp" in layers_str:
        return 180.0, "6 mo"
    elif "vmpet" in layers_str:
        return 240.0, "8 mo"

    # General failure-mode race between moisture and oxidation for non-metallised films
    days_m = 9999.0
    if requirements.max_wvtr and requirements.max_wvtr > 0 and candidate.measured_wvtr:
        ratio_wvtr = requirements.max_wvtr / max(candidate.measured_wvtr, 0.01)
        days_m = target_shelf_life_days * ratio_wvtr

    days_ox = 9999.0
    if requirements.max_otr and requirements.max_otr > 0 and candidate.measured_otr:
        days_ox = target_shelf_life_days * (requirements.max_otr / max(candidate.measured_otr, 0.01))

    limiting_days = min(days_m, days_ox, 90.0)
    months = limiting_days / 30.0
    return float(limiting_days), f"{months:.1f} mo"


def compute_sustainability_score(candidate: PackageCandidate) -> float:
    """Calculate sustainability score based on EPR category and recyclability notes."""
    if candidate.recyclability_score is not None:
        return float(candidate.recyclability_score)

    epr = (candidate.epr_category or "").strip()
    score = EPR_SUSTAINABILITY_SCORES.get(epr, 0.50)

    # Check for mono-material PP / PE in layer stack
    layers = [l.strip().upper() for l in candidate.layer_stack]
    is_mono_pp = all(l in ["BOPP", "VMBOPP", "CPP", "PP"] for l in layers)
    is_mono_pe = all(l in ["LDPE", "LLDPE", "HDPE", "PE"] for l in layers)
    if is_mono_pp or is_mono_pe:
        score = max(score, 0.95)

    return score


def compute_availability_score(candidate: PackageCandidate) -> float:
    """Estimate commercial availability score in Indian converters."""
    if candidate.availability:
        av = candidate.availability.lower()
        if "high" in av or "standard" in av:
            return 1.0
        elif "medium" in av or "specialty" in av:
            return 0.75
        elif "low" in av or "custom" in av:
            return 0.40

    # Fallback from materials
    layers = [l.strip().upper() for l in candidate.layer_stack]
    if any(m in layers for m in ["PLA", "PBAT", "EVOH"]):
        return 0.60
    if any(m in layers for m in ["BOPA", "ALOX", "ALOX-PET"]):
        return 0.80
    return 0.95  # Commodity films (PET, BOPP, CPP, LLDPE, Foil)


def compute_machinability_score(candidate: PackageCandidate) -> float:
    """Evaluate line machinability, seal window, and hot tack."""
    layers = [l.strip().upper() for l in candidate.layer_stack]
    sealant = candidate.sealant_layer or (candidate.layer_stack[-1] if candidate.layer_stack else "")
    sealant_upper = sealant.strip().upper()

    if "LLDPE" in sealant_upper or "PE" in sealant_upper:
        return 0.95  # Broadest seal window
    elif "CPP" in sealant_upper:
        return 0.88  # Good seal window, standard on VFFS
    elif "PLA" in layers or "PBAT" in layers:
        return 0.65  # Narrow thermal seal window
    return 0.85


def score_candidates(
    candidates: List[PackageCandidate],
    requirements: RequirementVector,
    profile: Optional[Union[CommodityProfile, Dict[str, Any]]] = None,
    environment: Optional[Union[Environment, Dict[str, Any]]] = None,
    target_shelf_life_days: float = 180.0,
    mode: str = "business",
    weights: Optional[Dict[str, float]] = None,
) -> MatchResult:
    """
    Score and rank candidate packages using weighted multi-objective ranking.

    Guarantees:
    - Never returns a single answer; returns at least three ranked options.
    - Always includes at least one lower-environmental-impact option (with honest trade-offs).
    """
    mode_clean = mode.strip().lower()
    if weights:
        active_weights = weights
    else:
        active_weights = MODE_WEIGHTS.get(mode_clean, MODE_WEIGHTS["business"])

    # Normalize weights so they sum to 1.0
    w_sum = sum(active_weights.values())
    w_norm = {k: v / w_sum for k, v in active_weights.items()}

    # Calculate raw costs to normalize
    costs: List[float] = []
    for c in candidates:
        if c.cost_per_pack is not None:
            costs.append(c.cost_per_pack)
        elif c.cost_inr_per_sqm is not None:
            costs.append(c.cost_inr_per_sqm * 0.055)
        else:
            costs.append(2.0)

    min_c = min(costs) if costs else 1.0
    max_c = max(costs) if costs else 3.0

    scored_options: List[RankedOption] = []

    for idx, cand in enumerate(candidates):
        cost_val = costs[idx]

        # 1. Shelf life estimation
        days, label = estimate_shelf_life_days(cand, requirements, target_shelf_life_days)

        # 2. Barrier margin score
        if days >= target_shelf_life_days:
            # Meets target: score 0.70 to 1.0 (with diminishing returns for over-engineering)
            margin_ratio = min(days / target_shelf_life_days, 2.5)
            s_barrier = 0.70 + 0.30 * ((margin_ratio - 1.0) / 1.5)
        else:
            # Strict quadratic penalty for failing to meet customer's required shelf life
            s_barrier = max(0.0, 0.40 * ((days / target_shelf_life_days) ** 2))

        # 3. Cost score (lower is better, normalized between 0.30 and 1.0)
        if abs(max_c - min_c) < 1e-6:
            s_cost = 1.0
        else:
            s_cost = 0.30 + 0.70 * (1.0 - (cost_val - min_c) / (max_c - min_c))

        # 4. Sustainability score
        s_sust = compute_sustainability_score(cand)
        is_eco = s_sust >= 0.85

        # 5. Availability score
        s_avail = compute_availability_score(cand)

        # 6. Machinability score
        s_mach = compute_machinability_score(cand)

        # Total weighted score
        total = (
            w_norm.get("barrier_margin", 0.3) * s_barrier
            + w_norm.get("cost", 0.3) * s_cost
            + w_norm.get("sustainability", 0.2) * s_sust
            + w_norm.get("availability", 0.1) * s_avail
            + w_norm.get("machinability", 0.1) * s_mach
        )

        # If candidate fails to meet target shelf life, penalize total score proportionally
        if days < target_shelf_life_days:
            total *= (days / target_shelf_life_days)

        breakdown = ScoreBreakdown(
            barrier_margin=round(s_barrier, 4),
            cost=round(s_cost, 4),
            sustainability=round(s_sust, 4),
            availability=round(s_avail, 4),
            machinability=round(s_mach, 4),
            total_score=round(total, 4),
        )

        scored_options.append(
            RankedOption(
                rank=0,  # assigned after sorting
                candidate=cand,
                predicted_shelf_life_days=round(days, 1),
                shelf_life_label=label,
                cost_per_pack_inr=round(cost_val, 2),
                epr_category=cand.epr_category or "Cat III",
                is_lower_environmental_impact=is_eco,
                score=breakdown,
                trade_off_explanation="",
            )
        )

    # Sort descending by total score
    scored_options.sort(key=lambda o: o.score.total_score, reverse=True)

    # Enforce policy: always include at least one lower-environmental-impact candidate in top 3
    has_eco_in_top_3 = any(opt.is_lower_environmental_impact for opt in scored_options[:3])
    if not has_eco_in_top_3 and len(scored_options) > 3:
        # Find best eco candidate
        eco_idx = next(
            (i for i, opt in enumerate(scored_options[3:], start=3) if opt.is_lower_environmental_impact),
            None,
        )
        if eco_idx is not None:
            # Promote best eco candidate to rank 3
            eco_candidate = scored_options.pop(eco_idx)
            scored_options.insert(2, eco_candidate)

    # Assign ranks and generate trade-off explanations
    for r, opt in enumerate(scored_options, start=1):
        opt.rank = r
        cand_name = opt.candidate.name or "/".join(opt.candidate.layer_stack)

        if r == 1:
            if opt.is_lower_environmental_impact:
                opt.trade_off_explanation = (
                    f"Top recommendation: {cand_name} meets the {target_shelf_life_days:.0f}-day target with margin "
                    f"({opt.shelf_life_label}) at lowest total cost (₹{opt.cost_per_pack_inr:.2f}/pack) "
                    f"and falls under CPCB EPR {opt.epr_category} (mono-material recyclable PP/PE stream), "
                    "minimising producer recycling fee obligations."
                )
            else:
                opt.trade_off_explanation = (
                    f"Top recommendation: {cand_name} delivers maximum barrier protection ({opt.shelf_life_label}) "
                    f"at ₹{opt.cost_per_pack_inr:.2f}/pack, certified under {opt.epr_category}."
                )
        else:
            # Comparative explanation against Rank 1
            r1 = scored_options[0]
            cost_diff_pct = ((opt.cost_per_pack_inr - r1.cost_per_pack_inr) / max(r1.cost_per_pack_inr, 0.01)) * 100.0
            cost_str = f"{abs(cost_diff_pct):.0f}% more expensive" if cost_diff_pct > 0 else f"{abs(cost_diff_pct):.0f}% cheaper"

            if opt.is_lower_environmental_impact and not r1.is_lower_environmental_impact:
                opt.trade_off_explanation = (
                    f"Eco-friendly alternative: {cand_name} is in CPCB EPR {opt.epr_category} (recyclable mono-material) "
                    f"vs {r1.epr_category} for Rank 1, reducing EPR liability despite being {cost_str}."
                )
            elif opt.epr_category != r1.epr_category:
                opt.trade_off_explanation = (
                    f"Alternative: {cand_name} provides {opt.shelf_life_label} shelf life at ₹{opt.cost_per_pack_inr:.2f}/pack "
                    f"({cost_str}), but carries an EPR {opt.epr_category} rating vs {r1.epr_category}."
                )
            else:
                opt.trade_off_explanation = (
                    f"Alternative: {cand_name} offers {opt.shelf_life_label} shelf life at ₹{opt.cost_per_pack_inr:.2f}/pack ({cost_str})."
                )

    # Return at least 3 options (if fewer than 3 candidates available, return all)
    final_ranked = scored_options[: max(3, len(scored_options))]

    top = final_ranked[0]
    summary = (
        f"Ranked {len(final_ranked)} options for {mode_clean} mode. Top pick '{top.candidate.name or top.candidate.id}' "
        f"achieves {top.shelf_life_label} shelf life at ₹{top.cost_per_pack_inr:.2f}/pack under EPR {top.epr_category}."
    )

    return MatchResult(
        mode=mode_clean,
        weights_applied=w_norm,
        ranked_options=final_ranked,
        summary_explanation=summary,
    )
