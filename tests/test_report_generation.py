"""
Unit and Integration Tests for Multi-Tier Reports (Kisan, Business, Expert)
and Shared HTML/PDF Template Rendering.

Validates:
1. Shared HTML templates render all three report types:
   - Kisan: A5, largely pictorial, B&W friendly, vernacular copy
   - Business: A4, RFQ spec, candidate ranking, official Compliance Annexe
   - Expert: A4, mathematical equations, assumption ledger, citations
2. Every report footer carries:
   - Engine version, KB version, Rule-set version
   - Generation timestamp
   - Mandatory decision-support legal disclaimer (FBO compliance responsibility)
3. PDF generation outputs valid '%PDF-' bytes.
4. API endpoints POST /api/v1/report, POST /api/v1/report/html, and GET endpoints.
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.reports import generate_report_pdf, render_report_html
from engine.result import ResolvedInputs, SealedResult
from engine.store import global_result_store
from engine.types import CommodityProfile, Environment, PackageCandidate, Provenance, SafetyStatus, SafetyVerdict, ShelfLifeResult
from engine.version import ENGINE_VERSION, KB_VERSION, RULESET_VERSION


@pytest.fixture
def sample_result():
    res = SealedResult(
        result_id="res_spec_audit_777",
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
                temperature=Provenance(value=14.0, unit="degC"),
                relative_humidity=Provenance(value=85.0, unit="%"),
                duration=Provenance(value=45.0, unit="days"),
            ),
        ),
        shelf_life=ShelfLifeResult(
            days_p50=38.0,
            days_p10=30.0,
            days_p90=45.0,
            limiting_mechanism="moisture_loss",
            safety_factor_applied=0.85,
            all_mode_results={"moisture_loss": 38.0, "microbial": 55.0, "respiration_decay": 60.0},
        ),
        safety=SafetyVerdict(
            status=SafetyStatus.PASS,
            rule_id="RULE_BOTULINUM",
            message_key="safety.pass",
        ),
        candidates=[
            PackageCandidate(
                name="Micro-perforated LDPE 40um",
                layer_stack=["LDPE"],
                gauge_per_layer=[40.0],
                composite_thickness_um=40.0,
                cost_per_pack=1.85,
                epr_category="Cat I (Mono-material PE)",
            ),
            PackageCandidate(
                name="Macro-perforated Polypropylene",
                layer_stack=["BOPP"],
                gauge_per_layer=[35.0],
                composite_thickness_um=35.0,
                cost_per_pack=2.10,
                epr_category="Cat I (Mono-material PP)",
            )
        ],

        assumptions=[
            Provenance(value=22.4, unit="mg/kg·h", note="Respiration Rate (R_O2)", source_id="USDA AH-66 (2016)"),
            Provenance(value=0.65, unit="aw", note="Critical Water Activity", source_id="Labuza Sorption Isotherms (2020)"),
        ],

    )
    global_result_store.save(res)
    return res


def test_kisan_advisory_template(sample_result):
    html = render_report_html(sample_result, report_type="kisan")
    assert "A5 portrait" in html
    assert "किसान सलाह कार्ड" in html
    assert "Potato" in html
    assert "हवा आने वाली" in html
    assert "data:image/png;base64," in html  # Embedded QR
    # Check mandatory footer elements
    assert f"Engine v{ENGINE_VERSION}" in html
    assert f"KB v{KB_VERSION}" in html
    assert f"Ruleset v{RULESET_VERSION}" in html
    assert "Food Business Operator (FBO)" in html


def test_business_spec_template(sample_result):
    html = render_report_html(sample_result, report_type="business")
    assert "AAVARAN AI SPECIFICATION SHEET" in html
    assert "COMMERCIAL RFQ SPEC" in html
    assert "STATUTORY COMPLIANCE ANNEXE" in html
    assert "FSSAI" in html
    assert "Plastic Waste Management (PWM)" in html
    assert "IS 9845" in html
    assert "ASTM F1249" in html
    assert "Cat I (Mono-material PE)" in html
    # Check mandatory footer elements
    assert f"Engine v{ENGINE_VERSION}" in html
    assert f"KB v{KB_VERSION}" in html
    assert f"Ruleset v{RULESET_VERSION}" in html
    assert "Food Business Operator (FBO)" in html


def test_expert_technical_template(sample_result):
    html = render_report_html(sample_result, report_type="expert")
    assert ("EXPERT AUDIT &amp; TECHNICAL REPORT" in html or "EXPERT AUDIT & TECHNICAL REPORT" in html)
    # Check governing equations
    assert "Labuza GAB Model" in html
    assert "m(a_w) =" in html
    assert "Headspace Oxygen Budget" in html
    assert "R_{O2}(T) =" in html
    assert "Ratkowsky Square-Root" in html
    assert "USDA AH-66" in html
    # Check mandatory footer elements
    assert f"Engine v{ENGINE_VERSION}" in html
    assert f"KB v{KB_VERSION}" in html
    assert f"Ruleset v{RULESET_VERSION}" in html
    assert "Food Business Operator (FBO)" in html


def test_generate_report_pdf(sample_result):
    # PDF generation for all three tiers
    for r_type in ["kisan", "business", "expert"]:
        pdf_bytes = generate_report_pdf(sample_result, report_type=r_type)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 2000
        assert pdf_bytes.startswith(b"%PDF-")


def test_api_report_endpoints(sample_result):
    client = TestClient(app)

    # 1. POST /api/v1/report (PDF)
    resp_pdf = client.post("/api/v1/report", json={"result_id": sample_result.result_id, "report_type": "business"})
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert resp_pdf.content.startswith(b"%PDF-")

    # 2. POST /api/v1/report/html (Web Spec Sheet preview)
    resp_html = client.post("/api/v1/report/html", json={"result_id": sample_result.result_id, "report_type": "business"})
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]
    assert "STATUTORY COMPLIANCE ANNEXE" in resp_html.text

    # 3. GET /api/v1/report/{id}/pdf
    resp_get_pdf = client.get(f"/api/v1/report/{sample_result.result_id}/pdf?type=kisan")
    assert resp_get_pdf.status_code == 200
    assert resp_get_pdf.content.startswith(b"%PDF-")

    # 4. GET /api/v1/report/{id}/html
    resp_get_html = client.get(f"/api/v1/report/{sample_result.result_id}/html?type=expert")
    assert resp_get_html.status_code == 200
    assert "Ratkowsky" in resp_get_html.text


def test_render_rfq_html_all_three_sections():
    from engine.reports import render_rfq_html
    from api.routes.report import RFQRequest

    req = RFQRequest(
        commodity="Organic Spices",
        structure_rank=1,
        brand_name="SpiceCraft India Ltd",
        converter_name="Apex Laminates",
        order_quantity=50000,
    )
    html = render_rfq_html(req)
    # Verify all 3 core sections are visible
    assert "1. Physical Barrier & Mechanical Requirements" in html
    assert "2. Recommended Packaging Structures" in html
    assert "STATUTORY COMPLIANCE ANNEXE" in html
    # Verify RFQ procurement details
    assert "SpiceCraft India Ltd" in html
    assert "Apex Laminates" in html
    assert "50,000 Units" in html
    assert "AUTHORIZED BUYER SIGN-OFF" in html
    assert "CONVERTER ACKNOWLEDGEMENT & SEAL" in html


def test_rfq_pdf_endpoint_binary_download():
    client = TestClient(app)

    payload = {
        "commodity": "Organic Spices",
        "structure_rank": 1,
        "brand_name": "SpiceCraft India Ltd",
        "converter_name": "Apex Laminates",
        "order_quantity": 75000,
    }

    for path in ["/api/v1/rfq/pdf", "/rfq/pdf"]:
        resp = client.post(path, json=payload)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["content-disposition"].startswith('attachment; filename="Aavaran_RFQ_')
        assert int(resp.headers["content-length"]) > 0
        assert resp.content.startswith(b"%PDF")
        assert list(resp.content[:4]) == [0x25, 0x50, 0x44, 0x46]


def test_audit_pdf_endpoint(sample_result):
    client = TestClient(app)
    resp = client.post("/api/v1/report/audit", json={"result_id": sample_result.result_id})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith(('attachment; filename="Aavaran_Audit_', 'attachment; filename="Aavaran_Expert_Audit_'))
    assert int(resp.headers["content-length"]) > 0
    assert resp.content.startswith(b"%PDF")


def test_audit_pdf_endpoint_with_expert_result_data():
    client = TestClient(app)
    expert_payload = {
        "result_data": {
            "result_id": "sealed_exp_client_side_123",
            "engine_version": "Aavaran Core v1.4.2-wasm",
            "kb_version": "KB-2026.09-IN",
            "ruleset_version": "FSSAI-2018.v3 / PWM-2022.v4",
            "verdict": "RECOMMENDED_ENGINEERING_SPEC",
            "resolved_inputs": {
                "commodity": "food.snack.namkeen_bhujia",
                "storage_ambient_c": 30.0,
                "storage_rh_pct": 75.0,
            },
            "overrides_ledger": [
                {
                    "parameter_id": "geom_wvtr",
                    "name": "Water Vapor Transmission Rate",
                    "default_value": 0.62,
                    "override_value": 0.45,
                    "unit": "g/m²·day",
                }
            ],
            "shelf_life_simulation": {
                "p10_days": 195,
                "p50_days": 245,
                "p90_days": 295,
                "safety_factor": 0.75,
                "limiting_mechanism": "Moisture uptake",
            },
            "active_candidate": {
                "name": "12u PET / 18u VMBOPP / 40u mLLDPE",
                "layer_stack": ["12u BOPET", "18u VMBOPP", "40u mLLDPE"],
                "thickness_um": 70.0,
                "cost_inr": 2.15,
                "epr_category": "Category III (MLP)",
            },
            "citations": ["Robertson (2012)"],
        },
        "report_type": "expert",
    }
    resp = client.post("/api/v1/report/audit", json=expert_payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith(('attachment; filename="Aavaran_Audit_', 'attachment; filename="Aavaran_Expert_Audit_'))
    assert int(resp.headers["content-length"]) > 0
    assert resp.content.startswith(b"%PDF")

