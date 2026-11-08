"""
Pytest integration for Aavaran Golden Validation Suite (tests/golden/cases.yaml).
"""

from pathlib import Path
import pytest
import yaml

from tests.golden.run_golden_harness import CASES_FILE, DOCS_ACCURACY_FILE, run_all_cases


def test_golden_cases_count_and_schema():
    assert CASES_FILE.exists(), f"Missing {CASES_FILE}"
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    cases = data.get("cases", [])
    assert len(cases) >= 60, f"Expected at least 60 golden cases, found {len(cases)}"

    for c in cases:
        assert "case_id" in c, f"Case missing case_id: {c}"
        assert "commodity" in c, f"Case missing commodity: {c}"
        assert "expected_outcome" in c, f"Case missing expected_outcome: {c}"
        assert "source" in c and len(c["source"]) > 5, f"Case missing citation: {c}"


def test_run_golden_validation_harness():
    summary, results = run_all_cases()
    assert summary["total_cases"] >= 60
    assert summary["accuracy_percentage"] >= 85.0, f"Accuracy {summary['accuracy_percentage']}% below 85%"
    assert summary["safety_cases_evaluated"] >= 5
    assert summary["safety_cases_blocked"] >= 5

    assert DOCS_ACCURACY_FILE.exists()
    doc_text = DOCS_ACCURACY_FILE.read_text(encoding="utf-8")
    assert "Aavaran Accuracy & Validation Report" in doc_text
    assert "Headline Accuracy" in doc_text
    assert "Our Published Misses & Edge Limitations" in doc_text
