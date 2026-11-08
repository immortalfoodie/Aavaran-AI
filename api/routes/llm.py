"""
FastAPI Routes for LLM Parsing and Explanation Services.

Endpoints:
- POST /api/v1/parse   : Converts natural language & voice text to validated ParsedQuery
- POST /api/v1/explain : Explains SealedResult across Kisan, Business, and Expert registers
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.llm.explainer import explain_result
from api.llm.parser import parse_query
from api.llm.schemas import ExplanationMode, ExplanationResult, ParsedQuery
from engine.result import SealedResult
from engine.store import global_result_store

router = APIRouter(tags=["LLM Services"])


class ParseRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Raw query text in any of 9 Indian languages or English",
    )


class ExplainApiRequest(BaseModel):
    result_id: str | None = Field(
        None, description="ID of a previously stored SealedResult"
    )
    result: dict[str, Any] | None = Field(
        None, description="Inline SealedResult dictionary if not saved"
    )
    mode: str = Field(default="business", description="kisan, business, or expert")
    locale: str = Field(
        default="en-IN", description="Target locale (e.g. hi-IN, mr-IN, en-IN)"
    )


@router.post("/api/v1/parse", response_model=ParsedQuery)
def post_parse_query(request: ParseRequest) -> ParsedQuery:
    """
    Parses unstructured text or transcribed voice query into a structured,
    validated ParsedQuery with pgvector-based commodity retrieval.
    """
    try:
        return parse_query(request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query parsing failed: {str(e)}")


@router.post("/api/v1/explain", response_model=ExplanationResult)
def post_explain_result(request: ExplainApiRequest) -> ExplanationResult:
    """
    Generates prose explanation for a SealedResult across Kisan, Business,
    or Expert registers with post-generation number verification.
    """
    sealed: SealedResult | None = None
    if request.result_id:
        sealed = global_result_store.get(request.result_id)
        if not sealed:
            raise HTTPException(
                status_code=404, detail=f"Result ID '{request.result_id}' not found."
            )
    elif request.result:
        try:
            sealed = SealedResult.model_validate(request.result)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid SealedResult data: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=400, detail="Must provide either 'result_id' or 'result' body."
        )

    try:
        mode_enum = ExplanationMode.from_str(request.mode)
        return explain_result(sealed, mode=mode_enum, locale=request.locale)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Explanation generation failed: {str(e)}"
        )
