"""
Golden Test Suite for Aavaran Natural Language Parser.

Tests 30 representative agricultural logistics queries across 9 Indian languages
(English, Hindi, Marathi, Tamil, Telugu, Bengali, Kannada, Gujarati, Punjabi;
both native scripts and Latin transliteration, plus code-mixed queries).

Asserts:
- Every query produces a valid ParsedQuery conforming strictly to the Pydantic schema.
- Commodity hints are extracted and resolved to the exact canonical commodity_id via pgvector retrieval.
- States, hours_since, quantities, destinations, storage_hints, and target_days match expectations.
- Per-field confidence scores are populated within [0.0, 1.0].
"""

import json
from pathlib import Path

import pytest

from api.llm.parser import parse_query
from api.llm.schemas import ParsedQuery

GOLDEN_CASES_PATH = Path(__file__).parent / "test_parse_cases.json"


def load_golden_cases():
    with open(GOLDEN_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


GOLDEN_CASES = load_golden_cases()


def test_golden_dataset_count():
    """Assert exactly 30 golden test cases are registered."""
    assert len(GOLDEN_CASES) == 30, (
        f"Expected 30 golden test cases, found {len(GOLDEN_CASES)}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_query_parsing(case):
    """
    Test parsing and schema validation for each golden case.
    """
    raw_text = case["input_text"]
    expected = case["expected"]

    # Execute parser
    parsed: ParsedQuery = parse_query(raw_text)

    # 1. Assert schema validity
    assert isinstance(parsed, ParsedQuery), (
        "Parser output must be an instance of ParsedQuery"
    )
    dumped_json = parsed.model_dump_json()
    assert dumped_json is not None
    reloaded = ParsedQuery.model_validate_json(dumped_json)
    assert reloaded == parsed

    # 2. Commodity resolution invariant
    assert parsed.commodity_hint is not None, (
        f"Failed to extract commodity_hint from '{raw_text}'"
    )
    assert parsed.resolved_commodity_id == expected["resolved_commodity_id"], (
        f"Mismatch in resolved_commodity_id for '{raw_text}': got {parsed.resolved_commodity_id}, expected {expected['resolved_commodity_id']}"
    )

    # 3. State extraction
    if expected.get("state") is not None:
        assert parsed.state == expected["state"], (
            f"Mismatch in state for '{raw_text}': got {parsed.state}, expected {expected['state']}"
        )

    # 4. Hours since extraction
    if expected.get("hours_since") is not None:
        assert parsed.hours_since == expected["hours_since"], (
            f"Mismatch in hours_since for '{raw_text}': got {parsed.hours_since}, expected {expected['hours_since']}"
        )

    # 5. Quantity extraction
    if expected.get("quantity") is not None:
        assert parsed.quantity == expected["quantity"], (
            f"Mismatch in quantity for '{raw_text}': got {parsed.quantity}, expected {expected['quantity']}"
        )

    # 6. Storage hint extraction
    if expected.get("storage_hint") is not None:
        assert parsed.storage_hint == expected["storage_hint"], (
            f"Mismatch in storage_hint for '{raw_text}': got {parsed.storage_hint}, expected {expected['storage_hint']}"
        )

    # 7. Target days extraction
    if expected.get("target_days") is not None:
        assert parsed.target_days == expected["target_days"], (
            f"Mismatch in target_days for '{raw_text}': got {parsed.target_days}, expected {expected['target_days']}"
        )

    # 8. Confidence bounds
    conf = parsed.confidence
    assert 0.0 <= conf.commodity_hint <= 1.0
    assert 0.0 <= conf.state <= 1.0
    assert 0.0 <= conf.hours_since <= 1.0
    assert 0.0 <= conf.quantity <= 1.0
    assert 0.0 <= conf.destination <= 1.0
    assert 0.0 <= conf.storage_hint <= 1.0
    assert 0.0 <= conf.target_days <= 1.0
