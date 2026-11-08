"""
Unit and Integration Tests for Aavaran Append-Only Batch Traceability & Merkle Root.

Validates:
1. Canonical SHA-256 hash chaining (each row commits to previous hash).
2. Genesis hash is 64 zeroes.
3. Tamper detection: modifying any field in an earlier record invalidates the entire chain.
4. Daily Merkle root calculation and grouping.
5. QR code generation resolves to GET /t/{batch_code}.
6. Fast public provenance page returns valid HTML (no-JS) and JSON when requested.
"""

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.store import BatchStore, compute_merkle_root, global_batch_store, global_result_store
from engine.result import SealedResult, ResolvedInputs
from engine.types import SafetyStatus, SafetyVerdict, CommodityProfile, Environment, ShelfLifeResult, Provenance
from engine.version import ENGINE_VERSION, KB_VERSION, RULESET_VERSION



@pytest.fixture
def clean_batch_store():
    store = BatchStore()
    return store


@pytest.fixture
def mock_sealed_result():
    res = SealedResult(
        result_id="res_trace_test_01",
        engine_version=ENGINE_VERSION,
        kb_version=KB_VERSION,
        ruleset_version=RULESET_VERSION,
        verdict="PACKAGING_RECOMMENDED",
        computed_at=datetime.now(),
        resolved=ResolvedInputs(
            commodity=CommodityProfile(
                commodity_id="potato.fresh",
                names={"en": ["Potato"], "hi": ["Aloo"]},
                group="vegetables",
                commodity_class="tuber",
            ),
            environment=Environment(
                temperature=Provenance(value=12.0, unit="degC"),
                relative_humidity=Provenance(value=85.0, unit="%"),
                duration=Provenance(value=30.0, unit="days"),
            ),

        ),
        shelf_life=ShelfLifeResult(
            days_p50=35.0,
            days_p10=28.0,
            days_p90=42.0,
            limiting_mechanism="moisture_loss",
            safety_factor_applied=0.85,
        ),
        safety=SafetyVerdict(
            status=SafetyStatus.PASS,
            rule_id="RULE_BOTULINUM",
            message_key="safety.pass",
        ),
    )
    global_result_store.save(res)
    return res



def test_genesis_hash_and_append_chain(clean_batch_store):
    b1 = clean_batch_store.create_batch(
        batch_code="PW-2026-TEST-01",
        result_id="res_test_01",
        commodity="Potato",
        quantity="500 kg",
        packaging_used="Micro-perforated LDPE 40um",
    )
    assert b1.prev_hash == "0" * 64
    assert len(b1.sha256_hash) == 64
    assert clean_batch_store.verify_integrity() is True

    b2 = clean_batch_store.create_batch(
        batch_code="PW-2026-TEST-02",
        result_id="res_test_01",
        commodity="Onion",
        quantity="1000 kg",
        packaging_used="Jute / Leno Net Bag",
    )
    assert b2.prev_hash == b1.sha256_hash
    assert clean_batch_store.verify_integrity() is True

    b3 = clean_batch_store.create_batch(
        batch_code="PW-2026-TEST-03",
        result_id="res_test_01",
        commodity="Tomato",
        quantity="300 kg",
        packaging_used="MAP Polyolefin Pouch",
    )
    assert b3.prev_hash == b2.sha256_hash
    assert clean_batch_store.verify_integrity() is True


def test_tamper_detection(clean_batch_store):
    clean_batch_store.create_batch(batch_code="B1", result_id="R1", commodity="Mango")
    b2 = clean_batch_store.create_batch(batch_code="B2", result_id="R1", commodity="Banana")
    clean_batch_store.create_batch(batch_code="B3", result_id="R1", commodity="Guava")

    assert clean_batch_store.verify_integrity() is True

    # Tamper with B2 quantity/commodity
    b2.commodity = "Tampered Mango"
    assert clean_batch_store.verify_integrity() is False


def test_merkle_root_computation():
    # Empty
    assert compute_merkle_root([]) == "0" * 64

    # Single leaf
    leaf1 = "a" * 64
    assert compute_merkle_root([leaf1]) == leaf1

    # Multiple leaves
    leaf2 = "b" * 64
    root = compute_merkle_root([leaf1, leaf2])
    assert len(root) == 64
    assert root != leaf1
    assert root != leaf2

    # Deterministic Merkle root
    root2 = compute_merkle_root([leaf1, leaf2])
    assert root == root2


def test_daily_merkle_roots(clean_batch_store):
    today = datetime.now()
    clean_batch_store.create_batch(batch_code="B-TODAY-1", result_id="R1", commodity="Okra")
    clean_batch_store.create_batch(batch_code="B-TODAY-2", result_id="R1", commodity="Spinach")

    today_str = today.strftime("%Y-%m-%d")
    daily_roots = clean_batch_store.get_daily_merkle_roots()
    assert today_str in daily_roots
    assert len(daily_roots[today_str]) == 64
    assert clean_batch_store.get_daily_merkle_root(today_str) == daily_roots[today_str]


def test_api_traceability_endpoints(mock_sealed_result):
    client = TestClient(app)

    # 1. Register batch via API
    batch_payload = {
        "batch_code": "PW-API-DEMO-01",
        "result_id": mock_sealed_result.result_id,
        "commodity": "Potato",
        "quantity": "750 kg",
        "packaging_used": "Macro-perforated LDPE 40um",
        "packer_identity": "Nashik Agro Cooperative",
        "location": "Nashik, Maharashtra",
        "handling_events": [
            {
                "name": "Field Harvest",
                "timestamp": "2026-09-22T08:00:00",
                "location": "Farm Block 4",
                "actor": "Harvester Team A",
                "notes": "Grade A harvest",
            },
            {
                "name": "MAP Pack Line",
                "timestamp": "2026-09-22T14:30:00",
                "location": "Packhouse 1",
                "actor": "Nashik Agro Cooperative",
                "notes": "Heat sealed with nitrogen flush",
            }
        ]
    }
    resp = client.post("/api/v1/trace/batch", json=batch_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_code"] == "PW-API-DEMO-01"
    assert len(data["sha256_hash"]) == 64

    # 2. Check Merkle roots endpoint
    resp_merkle = client.get("/api/v1/trace/merkle-roots")
    assert resp_merkle.status_code == 200
    m_data = resp_merkle.json()
    assert m_data["status"] == "SECURE"
    assert m_data["chain_integrity_valid"] is True
    assert m_data["total_batches_recorded"] >= 1
    assert len(m_data["today_merkle_root"]) == 64

    # 3. Check QR code image endpoint
    resp_qr = client.get("/api/v1/trace/qr/PW-API-DEMO-01")
    assert resp_qr.status_code == 200
    assert resp_qr.headers["content-type"] == "image/png"
    assert len(resp_qr.content) > 100

    # 4. Check Public Traceability Page (HTML)
    resp_html = client.get("/t/PW-API-DEMO-01", headers={"Accept": "text/html"})
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]

    html_text = resp_html.text
    assert "PW-API-DEMO-01" in html_text
    assert "POTATO" in html_text
    assert "VERIFIED PROVENANCE" in html_text
    assert "CRYPTOGRAPHIC CHAIN" in html_text
    assert "Nashik Agro Cooperative" in html_text
    assert "Macro-perforated LDPE 40um" in html_text
    # Fast without external scripts
    assert "<script" not in html_text

    # 5. Check Public Traceability Page (JSON mode)
    resp_json = client.get("/t/PW-API-DEMO-01?format=json")
    assert resp_json.status_code == 200
    j_data = resp_json.json()
    assert j_data["batch_code"] == "PW-API-DEMO-01"
    assert j_data["chain_verification"]["chain_valid"] is True
    assert "recommended_storage" in j_data
    assert "best_before" in j_data
    assert len(j_data["handling_events"]) == 2
