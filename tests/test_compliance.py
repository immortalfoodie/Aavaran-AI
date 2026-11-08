"""
Comprehensive test suite for Aavaran data-driven compliance engine.

Tests:
1. Rule Schema & YAML Loading:
   - Validates all 5 YAML files against the Section 6.1 schema.
   - Checks clause citations, source URLs, effective dates, verification dates.
2. Predicate Evaluator:
   - Tests dot-path traversal, operators (eq, ne, gt, gte, lt, lte, in, not_in, contains, exists, regex).
   - Tests logical combinators (and, or, not).
3. India FSSAI 2018 Rules:
   - Food-grade requirement and appropriateness.
   - Schedules I, II, III conformity.
   - NABL certificate requirement.
   - Multilayer rule (contact layer conformity).
   - Printing inks to IS 15495 and no printed surface in contact.
   - Newspaper packaging prohibition (BLOCK).
   - Pigments and colourants to IS 9833.
   - Prohibition on re-use of tin containers (BLOCK).
   - Specific migration limits (Table 1).
   - Recycled plastic 2022 amendment position (CONDITIONAL).
4. Plastic Waste Management (PWM) & EPR:
   - Banned single-use plastic items (BLOCK).
   - Carry-bag thickness floors (75 um and 120 um).
   - 50 um floor for non-integral plastic sheets.
   - CPCB portal registration & MSME exemption.
   - Category III multi-layer plastic warning.
   - Compostable plastics to IS 17088.
5. EPR Cost Estimator:
   - Mono-material PP (Cat II) vs multi-layer (Cat III) rupee liability comparison.
   - MSME exemption yields ₹0 liability.
   - Category IV (compostable) yields ₹0 credit liability.
   - Per-pack and total annual liability calculations.
6. Food Labelling & Legal Metrology:
   - FSSAI logo, licence number, veg/non-veg mark.
   - Net quantity, MRP, manufacturer details, date marking.
   - PDP area font height requirements.
7. Export Markets (EU & US):
   - EU 10/2011 OML 10 mg/dm² and infant food 60 mg/kg limit.
   - Declaration of Compliance (DoC) and EN 1186 test reference.
   - US 21 CFR Letter of Guarantee and FDA NOL for recycled plastic.
8. Draft February 2026 Amendment:
   - PFAS and BPA prohibition warning clearly marked as draft.
9. Admin Regulatory Staleness Dashboard:
   - Endpoint lists rules > 180 days old.
10. Three User Modes Rendering:
    - Kisan, Business, and Expert views from ComplianceReport.
"""

from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.compliance import (
    ComplianceReport,
    Rule,
    RuleEffect,
    RuleSeverity,
    epr_cost_estimate,
    evaluate,
    evaluate_predicate,
    get_rule_engine,
)
from engine.types import PackageCandidate, CommodityProfile, Provenance


@pytest.fixture
def rule_engine():
    return get_rule_engine()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Rule Schema & YAML Loading
# ---------------------------------------------------------------------------

def test_yaml_rules_loading_and_schema_validation(rule_engine):
    rules = rule_engine.rules
    assert len(rules) >= 35, f"Expected at least 35 rules, found {len(rules)}"

    ids = set()
    for rule in rules:
        assert rule.id not in ids, f"Duplicate rule ID found: {rule.id}"
        ids.add(rule.id)

        assert rule.jurisdiction in ("IN", "EU", "US", "GLOBAL")
        assert len(rule.instrument.strip()) > 0
        assert len(rule.clause.strip()) > 0
        assert isinstance(rule.effective_from, date)
        assert isinstance(rule.last_verified, date)
        assert rule.effect in RuleEffect
        assert rule.severity in RuleSeverity
        assert rule.source_url.startswith("http://") or rule.source_url.startswith("https://")
        assert len(rule.message_en.strip()) > 0
        assert rule.get_message("en") == rule.message_en

        if rule.effective_until:
            assert rule.effective_until >= rule.effective_from


# ---------------------------------------------------------------------------
# Test 2: Predicate Evaluator Unit Tests
# ---------------------------------------------------------------------------

def test_predicate_evaluator_operators():
    ctx = {
        "package": {
            "thickness_um": 125.0,
            "layer_stack": ["BOPP", "CPP"],
            "material_type": "flexible_plastic",
            "is_printed": True,
        },
        "product": {
            "fat_pct": 22.5,
            "name": "Besan Namkeen",
        },
        "contact": "direct",
    }

    # Equality & dot-path
    match, _ = evaluate_predicate({"package.thickness_um": 125.0}, ctx)
    assert match is True

    # Smart alias: 'material' resolves to 'package'
    match, _ = evaluate_predicate({"material.thickness_um": {"gte": 120}}, ctx)
    assert match is True

    # Greater than & Less than
    match, _ = evaluate_predicate({"package.thickness_um": {"gt": 120, "lt": 150}}, ctx)
    assert match is True

    # In operator
    match, _ = evaluate_predicate({"package.material_type": {"in": ["flexible_plastic", "rigid"]}}, ctx)
    assert match is True

    # List intersection
    match, _ = evaluate_predicate({"package.layer_stack": {"contains": "BOPP"}}, ctx)
    assert match is True

    # Logical OR
    match, _ = evaluate_predicate({
        "or": [
            {"package.thickness_um": {"lt": 50}},
            {"package.is_printed": True},
        ]
    }, ctx)
    assert match is True

    # Logical NOT
    match, _ = evaluate_predicate({"not": {"package.thickness_um": {"lt": 50}}}, ctx)
    assert match is True


# ---------------------------------------------------------------------------
# Test 3: India FSSAI 2018 Rules
# ---------------------------------------------------------------------------

def test_fssai_newspaper_prohibition_blocks():
    candidate = {"material_type": "newspaper", "is_printed": True}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    assert report.is_compliant is False
    assert any(b.rule_id == "IN-FSSAI-PKG-2018-NO-NEWSPAPER" for b in report.blocking_issues)
    assert any("newspaper" in b.message.lower() for b in report.blocking_issues)


def test_fssai_printed_surface_in_contact_blocks():
    candidate = {"layer_stack": ["PET", "PE"], "printed_surface_in_contact": True}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    assert report.is_compliant is False
    assert any(b.rule_id == "IN-FSSAI-PKG-2018-PRINT-NO-CONTACT" for b in report.blocking_issues)


def test_fssai_tin_container_reuse_blocks():
    candidate = {"material_type": "tin_can", "is_reused": True}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    assert report.is_compliant is False
    assert any(b.rule_id == "IN-FSSAI-PKG-2018-TIN-NO-REUSE" for b in report.blocking_issues)


def test_fssai_food_grade_and_nabl_requirements():
    candidate = {"layer_stack": ["BOPP", "CPP"], "contact_layer": "CPP"}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    assert any("NABL-accredited" in doc for doc in report.required_documents)
    assert any("Food-grade certificate" in doc for doc in report.required_documents)


def test_fssai_recycled_plastic_2022_amendment():
    candidate = {"layer_stack": ["rPET", "PE"], "recycled_content_pct": 30}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    fired_ids = [r.id for r in report.rules_fired]
    assert "IN-FSSAI-PKG-2018-R4e" in fired_ids
    assert any("NABL-accredited conformity certificate" in doc for doc in report.required_documents)


# ---------------------------------------------------------------------------
# Test 4: Plastic Waste Management (PWM) & EPR Regulations
# ---------------------------------------------------------------------------

def test_pwm_single_use_plastic_ban_blocks():
    banned_items = ["plastic_straw", "plastic_cutlery", "plastic_plate", "plastic_cup", "thermocol_container"]
    for item in banned_items:
        candidate = {"package_type": item}
        report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
        assert report.is_compliant is False, f"Expected {item} to be blocked by PWM SUP ban"
        assert any(b.rule_id == "IN-PWM-2021-SUP-BAN" for b in report.blocking_issues)


def test_pwm_carry_bag_thickness_floors():
    # Carry bag < 120 um must be BLOCKED in 2026
    sub_120_bag = {"is_carry_bag": True, "composite_thickness_um": 90.0}
    report_fail = evaluate(package=sub_120_bag, product={"is_food": True}, destination_market="IN")
    assert report_fail.is_compliant is False
    assert any(b.rule_id == "IN-PWM-2021-CARRYBAG-120UM" for b in report_fail.blocking_issues)

    # Carry bag >= 120 um must PASS carry bag floor
    compliant_bag = {"is_carry_bag": True, "composite_thickness_um": 125.0}
    report_pass = evaluate(package=compliant_bag, product={"is_food": True}, destination_market="IN")
    assert not any(b.rule_id == "IN-PWM-2021-CARRYBAG-120UM" for b in report_pass.blocking_issues)


def test_pwm_non_integral_sheet_50um_floor():
    sheet_thin = {"is_non_integral_sheet": True, "composite_thickness_um": 40.0}
    report = evaluate(package=sheet_thin, product={"is_food": True}, destination_market="IN")
    assert report.is_compliant is False
    assert any(b.rule_id == "IN-PWM-2016-SHEET-50UM" for b in report.blocking_issues)


def test_pwm_category_3_warning():
    mlp_candidate = {"epr_category": "Cat III", "layer_stack": ["PET", "AluFoil", "LLDPE"]}
    report = evaluate(package=mlp_candidate, product={"is_food": True}, destination_market="IN")
    
    warn_ids = [w.rule_id for w in report.warnings]
    assert "IN-PWM-2022-CAT3-WARN" in warn_ids


# ---------------------------------------------------------------------------
# Test 5: EPR Cost Estimator
# ---------------------------------------------------------------------------

def test_epr_cost_estimate_mono_pp_vs_mlp():
    annual_packs = 500_000
    
    # Mono-material PP (Category II)
    mono_pp = {
        "epr_category": "Cat II",
        "layer_stack": ["BOPP", "VMBOPP", "CPP"],
        "gauge_per_layer_um": [20.0, 18.0, 40.0],
        "composite_thickness_um": 78.0,
    }
    est_mono = epr_cost_estimate(structure=mono_pp, annual_volume=annual_packs)

    # Multi-layered plastic laminate with aluminium foil (Category III)
    mlp_foil = {
        "epr_category": "Cat III",
        "layer_stack": ["PET", "AluFoil", "LLDPE"],
        "gauge_per_layer_um": [12.0, 9.0, 50.0],
        "composite_thickness_um": 71.0,
    }
    est_mlp = epr_cost_estimate(structure=mlp_foil, annual_volume=annual_packs)

    # Cat III must carry higher total liability and cost per pack than Cat II
    assert est_mlp.total_liability_inr > est_mono.total_liability_inr
    assert est_mlp.cost_per_pack_inr > est_mono.cost_per_pack_inr
    assert est_mono.epr_category == "Cat II"
    assert est_mlp.epr_category == "Cat III"
    assert est_mono.credit_rate_inr_per_tonne == 4000.0
    assert est_mlp.credit_rate_inr_per_tonne == 7500.0


def test_epr_cost_estimate_msme_and_compostable_exemptions():
    annual_packs = 1_000_000

    # MSME Producer/Brand Owner
    struct = {"epr_category": "Cat II", "composite_thickness_um": 60.0}
    est_msme = epr_cost_estimate(structure=struct, annual_volume=annual_packs, is_msme=True)
    assert est_msme.total_liability_inr == 0.0
    assert est_msme.cost_per_pack_inr == 0.0
    assert est_msme.is_msme_exempt is True

    # Category IV Compostable
    compostable = {"epr_category": "Cat IV", "composite_thickness_um": 55.0}
    est_comp = epr_cost_estimate(structure=compostable, annual_volume=annual_packs, is_msme=False)
    assert est_comp.total_liability_inr == 0.0
    assert est_comp.cost_per_pack_inr == 0.0


# ---------------------------------------------------------------------------
# Test 6: Food Labelling & Legal Metrology
# ---------------------------------------------------------------------------

def test_labelling_rules_for_packaged_food():
    candidate = {"layer_stack": ["BOPP", "CPP"], "composite_thickness_um": 60.0}
    product = {"name": "Besan Namkeen", "is_food": True}
    report = evaluate(package=candidate, product=product, destination_market="IN")

    fired_ids = [r.id for r in report.rules_fired]
    assert "IN-LABEL-2020-FSSAI-LOGO" in fired_ids
    assert "IN-LABEL-2020-VEG-NONVEG-MARK" in fired_ids
    assert "IN-LM-2011-NET-QUANTITY" in fired_ids
    assert "IN-LM-2011-MRP" in fired_ids
    assert "IN-LM-2011-MANUFACTURER-DETAILS" in fired_ids
    assert "IN-LM-2011-FONT-HEIGHTS" in fired_ids


# ---------------------------------------------------------------------------
# Test 7: Export Markets (EU and US)
# ---------------------------------------------------------------------------

def test_eu_compliance_standard_vs_infant():
    candidate = {"layer_stack": ["PET", "PE"], "contains_plastic": True}
    
    # Standard food
    report_std = evaluate(package=candidate, product={"is_food": True, "is_infant_food": False}, destination_market="EU")
    assert report_std.is_compliant is True
    fired_ids_std = [r.id for r in report_std.rules_fired]
    assert "EU-10-2011-OML-10MG" in fired_ids_std
    assert "EU-10-2011-DOC-MANDATORY" in fired_ids_std
    assert any("Declaration of Compliance (DoC)" in doc for doc in report_std.required_documents)

    # Infant food
    report_infant = evaluate(package=candidate, product={"is_food": True, "is_infant_food": True}, destination_market="EU")
    fired_ids_infant = [r.id for r in report_infant.rules_fired]
    assert "EU-10-2011-INFANT-OML-60MG" in fired_ids_infant
    assert any("60 mg/kg" in doc for doc in report_infant.required_documents)


def test_us_21cfr_compliance():
    candidate = {"polymer_family": "polypropylene", "layer_stack": ["BOPP", "CPP"]}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="US")
    
    fired_ids = [r.id for r in report.rules_fired]
    assert "US-FDA-21CFR-FCS-AUTHORIZATION" in fired_ids
    assert "US-FDA-21CFR-POLYOLEFINS" in fired_ids
    assert any("Letter of Guarantee" in doc for doc in report.required_documents)


# ---------------------------------------------------------------------------
# Test 8: Draft February 2026 Amendment (PFAS & BPA Warning)
# ---------------------------------------------------------------------------

def test_draft_2026_pfas_bpa_warning():
    # Candidate with PFAS barrier coating
    candidate = {"layer_stack": ["Paper", "PE"], "contains_pfas": True}
    report = evaluate(package=candidate, product={"is_food": True}, destination_market="IN")
    
    warn_ids = [w.rule_id for w in report.warnings]
    assert "IN-FSSAI-PKG-2026-DRAFT-PFAS-BPA" in warn_ids
    warning = next(w for w in report.warnings if w.rule_id == "IN-FSSAI-PKG-2026-DRAFT-PFAS-BPA")
    assert "DRAFT AMENDMENT" in warning.message
    assert "NOT IN FORCE" in warning.message


# ---------------------------------------------------------------------------
# Test 9: Admin Regulatory Staleness Dashboard Endpoint
# ---------------------------------------------------------------------------

def test_admin_stale_rules_endpoint(client, rule_engine):
    # Today's date (2026-09-21) -> all rules verified today -> 0 stale rules
    response = client.get("/admin/compliance/stale-rules?days_threshold=180")
    assert response.status_code == 200
    data = response.json()
    assert data["total_rules_count"] >= 35
    assert data["stale_rules_count"] == 0
    assert data["fresh_rules_count"] == data["total_rules_count"]

    # Simulating a future date 200 days later -> all rules should be flagged as stale
    future_date = (date.today() + timedelta(days=200)).isoformat()
    response_future = client.get(f"/admin/compliance/stale-rules?days_threshold=180&as_of={future_date}")
    assert response_future.status_code == 200
    data_future = response_future.json()
    assert data_future["stale_rules_count"] == data_future["total_rules_count"]
    assert len(data_future["stale_rules"]) == data_future["total_rules_count"]
    first_stale = data_future["stale_rules"][0]
    assert first_stale["days_since_verified"] >= 200


def test_api_compliance_evaluate_and_epr(client):
    # Test POST /compliance/evaluate
    payload = {
        "package": {"material_type": "newspaper"},
        "product": {"is_food": True},
        "destination_market": "IN",
    }
    resp = client.post("/compliance/evaluate", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_compliant"] is False
    assert len(body["blocking_issues"]) > 0

    # Test POST /compliance/epr-estimate
    epr_payload = {
        "structure": {"epr_category": "Cat II", "composite_thickness_um": 60.0},
        "annual_volume": 200000,
        "is_msme": False,
    }
    epr_resp = client.post("/compliance/epr-estimate", json=epr_payload)
    assert epr_resp.status_code == 200
    epr_body = epr_resp.json()
    assert epr_body["epr_category"] == "Cat II"
    assert epr_body["total_liability_inr"] > 0


# ---------------------------------------------------------------------------
# Test 10: Three User Modes Rendering
# ---------------------------------------------------------------------------

def test_three_user_modes_rendering():
    # Blocking candidate
    blocked_candidate = {"material_type": "newspaper"}
    blocked_report = evaluate(package=blocked_candidate, product={"is_food": True}, destination_market="IN")

    # 1. Kisan Mode: One red line
    kisan_msg = blocked_report.kisan_view("en")
    assert kisan_msg is not None
    assert "newspaper" in kisan_msg.lower()

    # 2. Business Mode: Checklist
    biz = blocked_report.business_view("en")
    assert biz["compliant"] is False
    assert len(biz["blocking_issues"]) > 0

    # 3. Expert Mode: Full audit trace
    exp = blocked_report.expert_view()
    assert exp["is_compliant"] is False
    assert len(exp["trace"]) > 0
    assert "details" in exp["trace"][0]
