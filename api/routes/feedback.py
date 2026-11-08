"""
FastAPI Commercial Outcome Feedback Route for Aavaran.

Implements:
- POST /api/v1/feedback : Logs actual commercial shelf-life outcomes and observations
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine.store import FeedbackRecord, global_feedback_store

router = APIRouter(tags=["Feedback"])


class FeedbackRequest(BaseModel):
    result_id: str = Field(..., description="ID of the SealedResult being reported on")
    actual_shelf_life_days: float = Field(..., ge=0.0, description="Observed commercial shelf life in days")
    spoilage_observed: bool = Field(..., description="Whether premature spoilage was observed")
    limiting_mechanism_observed: Optional[str] = Field(None, description="Observed spoilage mechanism (e.g. microbial, moisture, oxidation)")
    rating: Optional[int] = Field(None, ge=1, le=5, description="User satisfaction rating 1 to 5")
    comments: Optional[str] = Field(None, description="Additional qualitative converter or packer notes")


class FeedbackResponse(BaseModel):
    status: str
    message: str
    record: FeedbackRecord


@router.post("/api/v1/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Logs actual commercial outcome data against a recommendation.
    Enables continuous empirical calibration and drift monitoring.
    """
    try:
        record = FeedbackRecord(
            result_id=request.result_id,
            actual_shelf_life_days=request.actual_shelf_life_days,
            spoilage_observed=request.spoilage_observed,
            limiting_mechanism_observed=request.limiting_mechanism_observed,
            rating=request.rating,
            comments=request.comments,
        )
        global_feedback_store.save(record)
        return FeedbackResponse(
            status="success",
            message="Actual commercial outcome logged successfully.",
            record=record,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log feedback: {str(e)}")
