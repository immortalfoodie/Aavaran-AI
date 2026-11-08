"""
Tests for commodity display_name resolution and safety message templating.
Verifies that safety refusal messages use {commodity_name} placeholder
and SealedResult resolved commodity profile carries display_name for mango, spinach, onion, banana.
"""

import pytest
from kb import load_commodity
from engine.types import CommodityProfile
from engine.orchestrate import recommend


def test_commodity_profile_display_name():
    """Verify that CommodityProfile automatically populates display_name and local_name."""
    commodities = ["mango", "spinach", "onion", "banana", "potato"]
    for c_id in commodities:
        profile = load_commodity(f"kb/commodities/{c_id}.json")
        assert profile is not None, f"Commodity {c_id} must be loadable"
        assert profile.display_name is not None
        assert profile.display_name.lower() == c_id.lower()


def test_refusal_cut_produce_ambient_commodity_name():
    """Verify ambient cut produce refusal replaces {commodity_name} or provides display_name."""
    for comm in ["mango", "spinach", "onion", "banana"]:
        req = {
            "mode": "kisan",
            "input": {
                "name": comm,
                "state": {
                    "cut": True,
                },
                "environment": {
                    "temperature": 32.0,
                    "storage_type": "ambient",
                },
            },
            "locale": "en",
        }
        result = recommend(req)
        assert result.verdict == "NOT_A_PACKAGING_PROBLEM"
        assert result.resolved is not None
        assert result.resolved.commodity is not None
        assert result.resolved.commodity.display_name == comm

        # Check safety message does not contain hardcoded "potato"
        if result.safety:
            msg = result.safety.message_key
            assert "potato" not in msg.lower(), f"Unexpected potato in message_key for {comm}: {msg}"
            assert "{commodity_name}" in msg, f"Expected {{commodity_name}} placeholder in message_key: {msg}"

        if result.guidance:
            for g in result.guidance:
                detail = g.get("detail", "")
                headline = g.get("headline", "")
                assert "potato" not in detail.lower(), f"Unexpected potato in guidance detail: {detail}"
                assert "potato" not in headline.lower(), f"Unexpected potato in guidance headline: {headline}"
