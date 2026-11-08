"""
Pydantic schemas and validation models for Aavaran LLM layer.

Defines:
- QueryConfidence: per-field extraction confidence scores [0.0, 1.0]
- ParsedQuery: validated query extraction output
- ExplanationMode: enum of supported prose registers (kisan, business, expert)
- ExplanationRequest & ExplanationResult: contracts for the explainer
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QueryConfidence(BaseModel):
    """Per-field extraction confidence scores bounded between 0.0 and 1.0."""

    commodity_hint: float = Field(default=0.0, ge=0.0, le=1.0)
    state: float = Field(default=0.0, ge=0.0, le=1.0)
    hours_since: float = Field(default=0.0, ge=0.0, le=1.0)
    quantity: float = Field(default=0.0, ge=0.0, le=1.0)
    destination: float = Field(default=0.0, ge=0.0, le=1.0)
    storage_hint: float = Field(default=0.0, ge=0.0, le=1.0)
    target_days: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        return self.model_dump()


class ParsedQuery(BaseModel):
    """
    Structured query extracted from natural language and voice input.
    Contains strictly extracted fields, never inferred physical constants.
    """

    commodity_hint: str | None = Field(
        default=None,
        description="Raw mention of the commodity in user text (e.g. 'aloo', 'tomato', 'बटाटा')",
    )
    state: str | None = Field(
        default=None,
        description="Physical state modifier (e.g. 'cut', 'sliced', 'washed', 'whole', 'fresh')",
    )
    hours_since: float | None = Field(
        default=None,
        ge=0.0,
        description="Hours elapsed since harvest or cutting/processing (e.g. 48.0 for '2 din pehle')",
    )
    quantity: str | None = Field(
        default=None,
        description="Stated quantity or batch size (e.g. '5 kg', '10 quintal', '50 bori')",
    )
    destination: str | None = Field(
        default=None,
        description="Destination market, transit mode, or trade channel (e.g. 'mandi', 'Delhi', 'truck')",
    )
    storage_hint: str | None = Field(
        default=None,
        description="Storage condition mentioned (e.g. 'cold storage', 'ambient', 'room temp')",
    )
    target_days: float | None = Field(
        default=None,
        ge=0.0,
        description="Target shelf life requested in days (e.g. 10.0 for '10 din chalna chahiye')",
    )
    confidence: QueryConfidence = Field(
        default_factory=QueryConfidence,
        description="Per-field extraction confidence scores",
    )
    resolved_commodity_id: str | None = Field(
        default=None,
        description="Canonical commodity_id resolved against alias table using pgvector cosine similarity",
    )
    language_detected: str | None = Field(
        default=None,
        description="Detected language code (e.g. 'hi', 'mr', 'ta', 'te', 'bn', 'kn', 'gu', 'pa', 'en')",
    )
    parser_source: str = Field(
        default="llm",
        description="Extraction source: 'llm' or 'deterministic_fallback'",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def parse_confidence(cls, v: Any) -> Any:
        if isinstance(v, dict):
            # Fill missing keys with 0.0
            defaults = {
                "commodity_hint": 0.0,
                "state": 0.0,
                "hours_since": 0.0,
                "quantity": 0.0,
                "destination": 0.0,
                "storage_hint": 0.0,
                "target_days": 0.0,
            }
            defaults.update({k: float(val) for k, val in v.items() if k in defaults})
            return QueryConfidence(**defaults)
        return v


class ExplanationMode(str, Enum):
    """Supported prose registers for explanation generation."""

    KISAN = "kisan"
    BUSINESS = "business"
    EXPERT = "expert"

    @classmethod
    def from_str(cls, value: str) -> "ExplanationMode":
        val_clean = value.strip().lower()
        for member in cls:
            if member.value == val_clean:
                return member
        raise ValueError(
            f"Unknown explanation mode: '{value}'. Expected one of: {[m.value for m in cls]}"
        )


class ExplanationRequest(BaseModel):
    """Input payload for the SealedResult explainer."""

    result: Any = Field(..., description="SealedResult instance or dictionary")
    mode: ExplanationMode = Field(
        default=ExplanationMode.BUSINESS,
        description="Target prose register: kisan, business, or expert",
    )
    locale: str = Field(
        default="en-IN",
        description="Target locale code, e.g. 'en-IN', 'hi-IN', 'mr-IN', 'ta-IN'",
    )


class ExplanationResult(BaseModel):
    """Output payload from the SealedResult explainer."""

    mode: str = Field(..., description="Mode used (kisan, business, expert)")
    locale: str = Field(..., description="Locale used")
    explanation: str = Field(..., description="Generated prose explanation text")
    verified_numbers: list[str] = Field(
        default_factory=list,
        description="List of verified numbers extracted from prose that matched source result",
    )
    hallucinations_detected: list[str] = Field(
        default_factory=list,
        description="List of unauthorized numbers detected in generated prose (if any)",
    )
    is_valid: bool = Field(
        default=True,
        description="True if number verification pass passed; False if rejected",
    )
