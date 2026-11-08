"""
Aavaran LLM Subsystem (api.llm).

Two strictly bounded responsibilities:
1. parser.py: Natural language and voice input to structured query with
   pgvector cosine similarity alias resolution and deterministic fallback.
2. explainer.py: SealedResult to prose across Kisan, Business, and Expert
   registers with pre-formatted number immutability and post-generation
   number verification pass.
"""

from api.llm.alias_resolver import (
    generate_embedding,
    resolve_commodity_hint,
)
from api.llm.explainer import (
    explain_result,
    extract_numbers_from_result,
    extract_numbers_from_text,
    verify_numbers,
)
from api.llm.parser import (
    deterministic_parse_query,
    parse_query,
)
from api.llm.schemas import (
    ExplanationMode,
    ExplanationRequest,
    ExplanationResult,
    ParsedQuery,
    QueryConfidence,
)

__all__ = [
    "parse_query",
    "deterministic_parse_query",
    "resolve_commodity_hint",
    "generate_embedding",
    "explain_result",
    "verify_numbers",
    "extract_numbers_from_result",
    "extract_numbers_from_text",
    "ParsedQuery",
    "QueryConfidence",
    "ExplanationMode",
    "ExplanationRequest",
    "ExplanationResult",
]
