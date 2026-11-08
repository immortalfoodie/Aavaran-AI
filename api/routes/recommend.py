"""
FastAPI Recommendation & Shelf-Life Routes for Aavaran.

Implements:
- POST /api/v1/recommend : Section 9.1 master recommendation endpoint
- GET  /api/v1/result/{id} : Replay previously sealed decision record
- POST /api/v1/shelf-life  : Standalone shelf-life prediction applying 0.75 safety factor
"""

import math
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from api.llm.explainer import explain_result
from api.llm.schemas import ExplanationMode
from engine.models.microbial import time_to_spoilage
from engine.models.moisture import shelf_life_moisture_limited
from engine.models.oxidation import shelf_life_oxidation_limited
from engine.orchestrate import (
    RecommendInput,
    RecommendRequest,
    SAFETY_FACTOR_SHELF_LIFE,
    recommend,
)
from engine.resolver.environment import resolve_environment
from engine.resolver.hierarchy import resolve_commodity
from engine.result import SealedResult
from engine.store import global_result_store
from engine.types import PackageCandidate, PackGeometry, ShelfLifeResult

router = APIRouter(tags=["Recommendation & Results"])


def generate_and_cache_explanation(
    result_id: str, locale: str = "en-IN", mode: str = "kisan"
) -> None:
    """Background task to generate and cache LLM explanation without blocking recommendation response."""
    sealed = global_result_store.get(result_id)
    if not sealed:
        return
    try:
        mode_enum = ExplanationMode.from_str(mode)
        expl_res = explain_result(sealed, mode=mode_enum, locale=locale)
        global_result_store.save_explanation(
            result_id,
            {
                "status": "ready",
                "explanation": {
                    "kisan_instruction": expl_res.explanation,
                    "verified_numbers": expl_res.verified_numbers,
                    "is_valid": expl_res.is_valid,
                },
            },
            locale=locale,
        )
    except Exception:
        instr = "Stack gently in recommended packaging and maintain proper ventilation."
        if sealed.recommendation and sealed.recommendation.kisan_instruction:
            instr = sealed.recommendation.kisan_instruction
        global_result_store.save_explanation(
            result_id,
            {
                "status": "ready",
                "explanation": {
                    "kisan_instruction": instr,
                    "verified_numbers": [],
                    "is_valid": True,
                },
            },
            locale=locale,
        )


class StandaloneShelfLifeRequest(BaseModel):
    commodity_id: str = Field(..., description="Commodity identifier or common name")
    package: Optional[Dict[str, Any]] = Field(default=None, description="Packaging structure details")
    environment: Optional[Dict[str, Any]] = Field(default=None, description="Storage temperature and RH")
    pack_geometry: Optional[Dict[str, Any]] = Field(default=None, description="Pack area and product mass")


@router.post("/api/v1/recommend", response_model=SealedResult)
@router.post("/recommend", response_model=SealedResult)
def post_recommend(
    request: RecommendRequest, background: BackgroundTasks
) -> SealedResult:
    """
    Master decision-support endpoint as defined in Section 9.1 of BLUEPRINT.md.
    Executes Stages 2 through 9 of the architecture.
    Returns sealed result immediately and defers LLM explanation to background task.
    """
    try:
        result = recommend(request)
        global_result_store.save(result)

        # Queue LLM explanation generation in background
        background.add_task(
            generate_and_cache_explanation,
            result.result_id,
            request.locale,
            request.mode,
        )

        # In Kisan mode, return result with kisan_instruction set to null
        # so frontend displays shimmer skeleton while polling explanation
        if request.mode.lower() == "kisan" and result.recommendation:
            res_dict = result.model_dump()
            if res_dict.get("recommendation"):
                res_dict["recommendation"]["kisan_instruction"] = None
            return SealedResult.model_validate(res_dict)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation pipeline failed: {str(e)}")


@router.get("/api/v1/recommend/{result_id}/explanation")
@router.get("/recommend/{result_id}/explanation")
def get_recommendation_explanation(
    result_id: str, locale: Optional[str] = None
) -> Dict[str, Any]:
    """
    Lightweight polling endpoint to retrieve deferred explanation for a SealedResult.
    Accepts an optional locale query parameter to retrieve or dynamically generate
    the explanation in the requested language (e.g., 'mr-IN', 'hi-IN', 'en-IN').
    Returns status: 'pending' or status: 'ready' with explanation payload.
    """
    cached = global_result_store.get_explanation(result_id, locale=locale)
    if cached is not None:
        return cached

    # If the sealed result exists, dynamically generate on-the-fly for requested locale
    sealed = global_result_store.get(result_id)
    if not sealed:
        return {"status": "pending"}

    target_locale = locale or "en-IN"
    try:
        expl_res = explain_result(sealed, mode=ExplanationMode.KISAN, locale=target_locale)
        ready_payload = {
            "status": "ready",
            "explanation": {
                "kisan_instruction": expl_res.explanation,
                "verified_numbers": expl_res.verified_numbers,
                "is_valid": expl_res.is_valid,
            },
        }
        global_result_store.save_explanation(result_id, ready_payload, locale=target_locale)
        return ready_payload
    except Exception:
        return {"status": "pending"}


@router.get("/api/v1/result/{result_id}", response_model=SealedResult)
def get_sealed_result(result_id: str) -> SealedResult:
    """
    Replays a previously stored SealedResult object by result_id for audit,
    diffing, or inspection.
    """
    result = global_result_store.get(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Sealed result '{result_id}' not found.")
    return result


@router.post("/api/v1/shelf-life", response_model=ShelfLifeResult)
def post_standalone_shelf_life(request: StandaloneShelfLifeRequest) -> ShelfLifeResult:
    """
    Standalone multi-failure-mode shelf-life calculator.
    Simulates microbial, moisture, and oxidation degradation in parallel and
    applies the mandatory 0.75 safety factor.
    """
    try:
        # Resolve commodity
        res_comm = resolve_commodity(query=request.commodity_id)
        profile = res_comm.profile

        # Resolve environment
        env_dict = request.environment or {}
        temp_c = float(env_dict.get("temperature_c") or env_dict.get("temperature") or 25.0)
        rh_pct = float(env_dict.get("relative_humidity_pct") or env_dict.get("relative_humidity") or 65.0)
        env = resolve_environment(temp_c=temp_c, rh_pct=rh_pct)

        # Pack geometry
        geom = PackGeometry.model_validate(request.pack_geometry or {})

        # Candidate package if supplied
        candidate = PackageCandidate.model_validate(request.package) if request.package else None

        all_modes: Dict[str, float] = {}

        # 1. Microbial
        t_mic = time_to_spoilage(profile, env)
        t_mic_val = t_mic.shelf_life_days if hasattr(t_mic, "shelf_life_days") else float(t_mic)
        t_mic_safe = round(t_mic_val * SAFETY_FACTOR_SHELF_LIFE, 2) if math.isfinite(t_mic_val) and t_mic_val < 10000 else 999.0
        all_modes["microbial_spoilage"] = t_mic_safe

        # 2. Moisture
        try:
            t_moist = shelf_life_moisture_limited(
                profile=profile,
                environment=env,
                package=candidate,
                pack_area_m2=geom.pack_area_m2,
                dry_solids_kg=geom.dry_solids_kg,
            )
            t_m_val = t_moist.shelf_life_days
            t_m_safe = round(t_m_val * SAFETY_FACTOR_SHELF_LIFE, 2) if math.isfinite(t_m_val) and t_m_val < 10000 else 999.0
            all_modes["moisture_loss_or_gain"] = t_m_safe
        except Exception:
            all_modes["moisture_loss_or_gain"] = 180.0

        # 3. Oxidation
        try:
            t_ox = shelf_life_oxidation_limited(
                profile=profile,
                environment=env,
                package=candidate,
                pack_area_m2=geom.pack_area_m2,
                headspace_o2_fraction=geom.headspace_o2_fraction,
                product_mass_kg=geom.product_mass_kg,
                headspace_volume_cc=geom.headspace_volume_cc,
            )
            t_ox_val = t_ox.shelf_life_days
            t_ox_safe = round(t_ox_val * SAFETY_FACTOR_SHELF_LIFE, 2) if math.isfinite(t_ox_val) and t_ox_val < 10000 else 999.0
            all_modes["lipid_oxidation"] = t_ox_safe
        except Exception:
            all_modes["lipid_oxidation"] = 240.0

        limiting_mech = min(all_modes, key=all_modes.get)
        p50 = all_modes[limiting_mech]

        return ShelfLifeResult(
            days_p10=round(p50 * 0.70, 2),
            days_p50=round(p50, 2),
            days_p90=round(p50 * 1.30, 2),
            limiting_mechanism=limiting_mech,
            all_mode_results=all_modes,
            safety_factor_applied=SAFETY_FACTOR_SHELF_LIFE,
            equations_used=["MIC-01", "M-01", "OX-01"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shelf life prediction failed: {str(e)}")
