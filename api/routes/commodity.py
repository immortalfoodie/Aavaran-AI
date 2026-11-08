"""
FastAPI Commodity Discovery & Profile Routes for Aavaran.

Implements:
- GET /api/v1/commodities     : Multilingual search across English, Hindi, and Marathi names
- GET /api/v1/commodity/{id}  : Full commodity profile with complete parameter provenance
"""

import difflib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from engine.resolver.hierarchy import get_all_commodities, match_commodity_id
from engine.types import CommodityProfile

router = APIRouter(tags=["Commodities"])


class CommoditySummary(BaseModel):
    commodity_id: str
    names: Dict[str, List[str]]
    group: str
    commodity_class: str
    match_score: Optional[float] = None


@router.get("/api/v1/commodities", response_model=List[CommoditySummary])
def search_commodities(
    q: Optional[str] = Query(None, description="Search term in English, Hindi, Marathi, or Latin binomial"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
) -> List[CommoditySummary]:
    """
    Multilingual commodity search supporting token overlap, phonetic transliteration,
    and fuzzy similarity across English, Hindi, and Marathi names.
    """
    all_comms = get_all_commodities()

    if not q or not q.strip():
        summaries = [
            CommoditySummary(
                commodity_id=c.commodity_id,
                names=c.names,
                group=c.group,
                commodity_class=c.commodity_class,
                match_score=1.0,
            )
            for c in list(all_comms.values())[:limit]
        ]
        return summaries

    query_clean = q.strip().lower()
    results: List[CommoditySummary] = []

    for cid, prof in all_comms.items():
        score = 0.0
        # Exact ID match
        if query_clean == cid.lower():
            score = 1.0
        elif query_clean in cid.lower():
            score = 0.85
        else:
            # Check all multilingual names
            best_name_sim = 0.0
            for _lang, name_list in prof.names.items():
                for n in name_list:
                    n_clean = n.strip().lower()
                    if query_clean == n_clean:
                        best_name_sim = max(best_name_sim, 1.0)
                    elif query_clean in n_clean:
                        best_name_sim = max(best_name_sim, 0.80)
                    else:
                        sim = difflib.SequenceMatcher(None, query_clean, n_clean).ratio()
                        best_name_sim = max(best_name_sim, sim)
            score = best_name_sim

        if score >= 0.35:
            results.append(
                CommoditySummary(
                    commodity_id=prof.commodity_id,
                    names=prof.names,
                    group=prof.group,
                    commodity_class=prof.commodity_class,
                    match_score=round(score, 3),
                )
            )

    # Sort descending by match score
    results.sort(key=lambda x: x.match_score or 0.0, reverse=True)
    return results[:limit]


@router.get("/api/v1/commodity/{commodity_id}", response_model=CommodityProfile)
def get_commodity_by_id(commodity_id: str) -> CommodityProfile:
    """
    Returns the full CommodityProfile for the specified ID, including all
    physical parameters, respiration constants, optimum storage bounds,
    and complete provenance records.
    """
    all_comms = get_all_commodities()

    # Exact or suffix match
    if commodity_id in all_comms:
        return all_comms[commodity_id]

    matched_id = match_commodity_id(commodity_id, all_comms)
    if matched_id and matched_id in all_comms:
        return all_comms[matched_id]

    raise HTTPException(
        status_code=404,
        detail=f"Commodity '{commodity_id}' not found in Aavaran Knowledge Base.",
    )
