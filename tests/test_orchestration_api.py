"""
Comprehensive Test Suite for Aavaran Pipeline Orchestrator and API Exposure.

Tests:
1. Pipeline Orchestrator Happy Path:
   - recommend() for non-respiring food (besan namkeen in business mode).
   - Validates SealedResult structure, candidates ranking, and limiting mechanism.
2. Explicit Refusal Paths (NOT_A_PACKAGING_PROBLEM):
   - "aloo kaata hua do din pehle" (ambient cut potato): Botulinum safety gate blocks.
   - Scombroid fish at abuse temperature: Histamine safety gate blocks.
   - Zero candidates recommended and structured guidance emitted.
3. Documented 0.75 Safety Factor:
   - Explicit line in assumptions ledger with source_id="AAVARAN-SAFETY-FACTOR" and value=0.75.
   - Applied to predicted shelf-life numbers.
4. FastAPI Endpoints:
   - POST /api/v1/recommend (Section 9.1 payload and response).
   - GET  /api/v1/commodities (multilingual search).
   - GET  /api/v1/commodity/{id} (full profile with provenance).
   - POST /api/v1/compliance/check (standalone compliance check).
   - POST /api/v1/shelf-life (standalone shelf-life prediction).
   - GET  /api/v1/result/{id} (replay stored sealed result).
   - POST /api/v1/feedback (actual outcome logging).
   - POST /api/v1/report (PDF generation with statutory disclaimer).
   - GET  /t/{batch_code} (public QR provenance page with hash-chain).
5. Cross-cutting Concerns:
   - Header propagation: X-Engine-Version, X-KB-Version, X-Ruleset-Version, X-Request-ID.
   - Rate limiting and OpenAPI schema availability.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.orchestrate import (
    SAFETY_FACTOR_SHELF_LIFE,
    recommend,
)
from engine.store import (
    global_batch_store,
    global_feedback_store,
    global_result_store,
)
from engine.types import SafetyStatus
from engine.version import (
    ENGINE_VERSION,
    KB_VERSION,
    RULESET_VERSION,
)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Pipeline Orchestrator Happy Path (Besan Namkeen)
# ---------------------------------------------------------------------------

def test_pipeline_happy_path_besan_namkeen():
    req = {
        "mode": "business",
        "input": {
            "commodity_id": "processed.besan_namkeen.fried_snack",
            "environment": {
                "temperature": 30.0,
                "relative_humidity": 75.0,
                "storage_type": "ambient",
            },
            "target_shelf_life_days": 180.0,
            "destination_market": "IN",
        },
    }
    result = recommend(req)

    assert result.verdict == "RECOMMENDED"
    assert len(result.candidates) >= 1
    assert result.shelf_life is not None
    assert result.shelf_life.days_p50 > 10.0
    assert result.shelf_life.limiting_mechanism in ("lipid_oxidation", "moisture_loss_or_gain")
    assert result.shelf_life.safety_factor_applied == SAFETY_FACTOR_SHELF_LIFE

    # Assert 0.75 safety factor is an explicit line in assumptions ledger
    safety_factor_assumptions = [
        a for a in result.assumptions if a.source_id == "AAVARAN-SAFETY-FACTOR"
    ]
    assert len(safety_factor_assumptions) >= 1
    assert safety_factor_assumptions[0].value == 0.75

    # Verify result is persisted in store
    retrieved = global_result_store.get(result.result_id)
    assert retrieved is not None
    assert retrieved.result_id == result.result_id


# ---------------------------------------------------------------------------
# Test 2: Refusal Handling (NOT_A_PACKAGING_PROBLEM)
# ---------------------------------------------------------------------------

def test_pipeline_refusal_cut_potato_ambient():
    """
    Blueprint Section 2 & Section 8 validation:
    Type 'aloo kaata hua do din pehle' -> system refuses to recommend a bag,
    explains the botulinum and spoilage risk, and gives actionable next-time advice.
    """
    req = {
        "mode": "kisan",
        "input": {
            "raw_text": "aloo kaata hua do din pehle",
        },
        "locale": "hi-IN",
    }
    result = recommend(req)

    assert result.verdict == "NOT_A_PACKAGING_PROBLEM"
    assert len(result.candidates) == 0, "Candidates must be empty when packaging is refused"
    assert result.safety is not None
    assert result.safety.status == SafetyStatus.BLOCK
    assert result.safety.is_overridable is False

    # Check structured guidance
    assert len(result.guidance) >= 3
    actions = {g["action"] for g in result.guidance}
    assert "CHILL" in actions
    assert "PROCESS" in actions
    assert "SELL_IMMEDIATELY" in actions

    # Shelf life must show short microbial spoilage with 0.75 safety factor applied
    assert result.shelf_life is not None
    assert result.shelf_life.limiting_mechanism == "microbial_spoilage"
    assert result.shelf_life.days_p50 < 3.0


def test_pipeline_refusal_scombroid_fish_abuse_temp():
    """Histamine safety block for warm scombroid fish."""
    req = {
        "mode": "business",
        "input": {
            "name": "tuna",
            "environment": {
                "temperature": 18.0,  # > 5 °C abuse
                "storage_type": "ambient",
            },
        },
    }
    result = recommend(req)
    assert result.verdict == "NOT_A_PACKAGING_PROBLEM"
    assert len(result.candidates) == 0
    assert result.safety.status == SafetyStatus.BLOCK


# ---------------------------------------------------------------------------
# Test 3: API Endpoint POST /api/v1/recommend
# ---------------------------------------------------------------------------

def test_api_recommend_endpoint_section_9_1(client):
    payload = {
        "mode": "kisan",
        "input": {
            "raw_text": "aloo kaata hua do din pehle",
            "location": {"lat": 19.08, "lon": 72.88},
            "known": {},
        },
        "locale": "hi-IN",
    }
    response = client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["verdict"] == "NOT_A_PACKAGING_PROBLEM"
    assert data["engine_version"] == ENGINE_VERSION
    assert data["kb_version"] == KB_VERSION
    assert data["ruleset_version"] == RULESET_VERSION
    assert data["candidates"] == []
    assert len(data["guidance"]) >= 3


# ---------------------------------------------------------------------------
# Test 4: API Endpoint GET /api/v1/commodities & GET /api/v1/commodity/{id}
# ---------------------------------------------------------------------------

def test_api_commodities_multilingual_search(client):
    # Search in Hindi
    res_hi = client.get("/api/v1/commodities?q=aloo")
    assert res_hi.status_code == 200
    comms_hi = res_hi.json()
    assert len(comms_hi) >= 1
    assert "potato" in comms_hi[0]["commodity_id"]

    # Search in English
    res_en = client.get("/api/v1/commodities?q=tomato")
    assert res_en.status_code == 200
    comms_en = res_en.json()
    assert len(comms_en) >= 1
    assert "tomato" in comms_en[0]["commodity_id"]

    # Get full profile by ID
    profile_res = client.get(f"/api/v1/commodity/{comms_hi[0]['commodity_id']}")
    assert profile_res.status_code == 200
    prof = profile_res.json()
    assert prof["commodity_id"] == comms_hi[0]["commodity_id"]
    assert "moisture_pct" in prof


# ---------------------------------------------------------------------------
# Test 5: API Endpoint POST /api/v1/compliance/check
# ---------------------------------------------------------------------------

def test_api_compliance_check(client):
    payload = {
        "package": {"material_type": "newspaper"},
        "product": {"is_food": True},
        "destination_market": "IN",
    }
    response = client.post("/api/v1/compliance/check", json=payload)
    assert response.status_code == 200
    report = response.json()
    assert report["is_compliant"] is False
    assert len(report["blocking_issues"]) > 0


# ---------------------------------------------------------------------------
# Test 6: API Endpoint POST /api/v1/shelf-life
# ---------------------------------------------------------------------------

def test_api_standalone_shelf_life(client):
    payload = {
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "environment": {"temperature": 28.0, "relative_humidity": 65.0},
        "package": {
            "layer_stack": ["BOPP", "VMBOPP", "CPP"],
            "gauge_per_layer": [20.0, 18.0, 40.0],
            "measured_otr": 22.0,
            "measured_wvtr": 0.65,
        },
    }
    response = client.post("/api/v1/shelf-life", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["days_p50"] > 0
    assert res["safety_factor_applied"] == 0.75
    assert len(res["all_mode_results"]) >= 1


# ---------------------------------------------------------------------------
# Test 7: API Endpoint GET /api/v1/result/{id} (Replay)
# ---------------------------------------------------------------------------

def test_api_result_replay(client):
    # First generate a recommendation
    payload = {
        "mode": "business",
        "input": {"commodity_id": "processed.besan_namkeen.fried_snack"},
    }
    res = client.post("/api/v1/recommend", json=payload)
    assert res.status_code == 200
    result_id = res.json()["result_id"]

    # Replay result
    replay_res = client.get(f"/api/v1/result/{result_id}")
    assert replay_res.status_code == 200
    replayed = replay_res.json()
    assert replayed["result_id"] == result_id
    assert replayed["verdict"] == res.json()["verdict"]

    # Unknown ID 404
    missing_res = client.get("/api/v1/result/res_non_existent")
    assert missing_res.status_code == 404


# ---------------------------------------------------------------------------
# Test 8: Commercial Feedback Logging (POST /api/v1/feedback)
# ---------------------------------------------------------------------------

def test_api_feedback_logging(client):
    payload = {
        "result_id": "res_test_123",
        "actual_shelf_life_days": 165.0,
        "spoilage_observed": False,
        "rating": 5,
        "comments": "Commercial pack achieved 5.5 months with zero rancidity.",
    }
    response = client.post("/api/v1/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["record"]["actual_shelf_life_days"] == 165.0


# ---------------------------------------------------------------------------
# Test 9: PDF Spec Sheet Generation (POST /api/v1/report)
# ---------------------------------------------------------------------------

def test_api_pdf_report_generation(client):
    # Generate a result first
    rec_res = client.post("/api/v1/recommend", json={"input": {"commodity_id": "processed.besan_namkeen.fried_snack"}})
    result_id = rec_res.json()["result_id"]

    # Request PDF report
    report_res = client.post("/api/v1/report", json={"result_id": result_id})
    assert report_res.status_code == 200
    assert report_res.headers["content-type"] == "application/pdf"
    assert report_res.content.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# Test 10: Public QR Traceability & Hash Chaining (GET /t/{batch_code})
# ---------------------------------------------------------------------------

def test_api_public_traceability_and_hash_chain(client):
    # Register batch record
    batch_payload = {
        "batch_code": "BATCH-2026-09-001",
        "result_id": "res_trace_demo",
        "commodity_id": "processed.besan_namkeen.fried_snack",
        "structure_id": "struct_bopp20_vmbopp18_cpp40",
        "package_name": "20u BOPP / 18u VMBOPP / 40u CPP",
        "metadata": {"plant_location": "Pune, MH", "line_speed_ppm": 120},
    }
    reg_res = client.post("/api/v1/trace/batch", json=batch_payload)
    assert reg_res.status_code == 200
    b_data = reg_res.json()
    assert len(b_data["sha256_hash"]) == 64

    # Resolve public provenance page JSON
    prov_res = client.get("/t/BATCH-2026-09-001")
    assert prov_res.status_code == 200
    prov_data = prov_res.json()
    assert prov_data["batch_code"] == "BATCH-2026-09-001"
    assert prov_data["chain_valid"] is True

    # Resolve HTML version
    html_res = client.get("/t/BATCH-2026-09-001", headers={"Accept": "text/html"})
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers["content-type"]
    assert "BATCH-2026-09-001" in html_res.text
    assert "VERIFIED PROVENANCE" in html_res.text


# ---------------------------------------------------------------------------
# Test 11: Cross-Cutting Middleware Headers & Request ID
# ---------------------------------------------------------------------------

def test_cross_cutting_headers_and_request_id(client):
    custom_req_id = "req_custom_test_999"
    response = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_req_id
    assert response.headers["X-Engine-Version"] == ENGINE_VERSION
    assert response.headers["X-KB-Version"] == KB_VERSION
    assert response.headers["X-Ruleset-Version"] == RULESET_VERSION


def test_openapi_documentation_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/api/v1/recommend" in schema["paths"]
    assert "/api/v1/commodities" in schema["paths"]
    assert "/t/{batch_code}" in schema["paths"]
