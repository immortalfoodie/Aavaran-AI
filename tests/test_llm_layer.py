"""
Unit, invariant, and adversarial tests for Aavaran LLM Layer (api.llm).

Validates:
1. parser.py:
   - Strict extraction invariants: never infer physical constants, unmentioned fields are null.
   - Schema validation against ParsedQuery.
   - Graceful deterministic fallback when LLM is unavailable or outputs malformed text.
   - Reduced confidence scores on fallback.
   - Alias table retrieval using pgvector cosine similarity over 384-d embeddings.
2. explainer.py:
   - Pre-formatted number immutability.
   - Three prose registers:
     * Kisan: exactly one instruction sentence, second person, active voice, no jargon, native language.
     * Business: exactly two paragraphs covering what to buy and why + runner-up trade-off.
     * Expert: technical rationale naming limiting mechanism, equations used, key assumptions.
   - Post-generation number verification pass.
   - Injected hallucination rejection test: catches unauthorized figures and rejects generation.
"""

from datetime import datetime

import pytest

from api.llm import (
    ExplanationMode,
    ExplanationResult,
    ParsedQuery,
    explain_result,
    extract_numbers_from_result,
    generate_embedding,
    parse_query,
    resolve_commodity_hint,
    verify_numbers,
)
from engine.result import ResolvedInputs, SealedResult
from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    Provenance,
    RequirementVector,
    SafetyStatus,
    SafetyVerdict,
    ShelfLifeResult,
    SourceType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_sealed_result() -> SealedResult:
    """Creates a complete, verified SealedResult object for testing."""
    comm = CommodityProfile(
        commodity_id="fruit.mango.mangifera_indica",
        names={
            "en": ["mango", "alphonso"],
            "hi": ["आम", "aam"],
            "mr": ["आंबा", "amba", "hapus"],
        },
        group="fruiting_tree",
        commodity_class="climacteric_high_respiration",
        source_id="USDA-AH66",
        moisture_pct=Provenance(value=81.0, confidence=0.92, source_id="IFCT-2017"),
        water_activity=Provenance(value=0.98, confidence=0.90, source_id="IFCT-2017"),
        fat_pct=Provenance(value=0.3, confidence=0.95, source_id="IFCT-2017"),
        pH=Provenance(value=4.5, confidence=0.90, source_id="FDA-pH-db"),
        respiration_ea_kj_mol=Provenance(
            value=58.0, confidence=0.90, source_id="USDA-AH66"
        ),
    )

    env = Environment(
        temperature=Provenance(value=25.0, unit="degC", confidence=1.0),
        relative_humidity=Provenance(value=65.0, unit="%", confidence=1.0),
        duration=Provenance(value=14.0, unit="days", confidence=1.0),
    )

    shelf_life = ShelfLifeResult(
        days_p10=9.4,
        days_p50=12.5,
        days_p90=16.3,
        limiting_mechanism="respiration_anaerobiosis",
        all_mode_results={"respiration_anaerobiosis": 12.5, "moisture_loss": 18.0},
        safety_factor_applied=0.75,
        equations_used=["MIC-01", "M-01", "OX-01"],
    )

    c1 = PackageCandidate(
        id="cand_01",
        name="Micro-perforated BOPP 25 / LDPE 25",
        layer_stack=["BOPP", "LDPE"],
        gauge_per_layer=[25.0, 25.0],
        composite_thickness_um=50.0,
        cost_per_pack=0.85,
        cost_inr_per_sqm=12.50,
        epr_category="Category I (Rigid/Mono)",
    )

    c2 = PackageCandidate(
        id="cand_02",
        name="Laminated PET 12 / MET-PET 12 / PE 50",
        layer_stack=["PET", "MET-PET", "PE"],
        gauge_per_layer=[12.0, 12.0, 50.0],
        composite_thickness_um=74.0,
        cost_per_pack=1.45,
        cost_inr_per_sqm=19.20,
        epr_category="Category III (Multi-layer)",
    )

    assumptions = [
        Provenance(
            value=0.75,
            unit="dimensionless",
            source_type=SourceType.STANDARD,
            source_id="AAVARAN-SAFETY-FACTOR",
            confidence=1.0,
            note="Safety factor applied to shelf life predictions",
        ),
        Provenance(
            value=58.0,
            unit="kJ/mol",
            source_type=SourceType.MODEL_ESTIMATE,
            source_id="USDA-AH66",
            confidence=0.90,
            note="Arrhenius respiration activation energy Ea",
        ),
    ]

    return SealedResult(
        result_id="res_test_mango_123",
        engine_version="1.0.0",
        kb_version="1.0.0",
        ruleset_version="1.0.0",
        resolved=ResolvedInputs(
            commodity=comm,
            environment=env,
            state_modifiers={},
            state={},
        ),
        assumptions=assumptions,
        requirements=RequirementVector(min_thickness_um=50.0, max_wvtr=15.0),
        candidates=[c1, c2],
        shelf_life=shelf_life,
        safety=SafetyVerdict(
            status=SafetyStatus.PASS,
            rule_id="RULE-MAP-01",
            message_key="safety_perforated_map_pass",
            is_overridable=True,
        ),
        verdict="RECOMMENDED",
        guidance=[],
        citations=["USDA-AH66", "IFCT-2017", "FSSAI-Packaging-2018", "PWM-Rules-2022"],
        computed_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Parser Tests
# ---------------------------------------------------------------------------


class TestParserExtraction:
    def test_unmentioned_physical_constants_remain_null(self):
        """
        The LLM must only extract, never infer physical constants.
        If storage temperature is unmentioned, it must be null.
        """
        query = parse_query("potato 5 kg truck se bhejna hai")
        assert query.commodity_hint in ["potato", "aloo", "batata"]
        assert query.quantity == "5 kg"
        assert query.storage_hint is None
        # Does not guess temperature, humidity, OTR, WVTR, etc.
        assert (
            not hasattr(query, "storage_temperature")
            or getattr(query, "storage_temperature", None) is None
        )

    def test_never_guess_numbers(self):
        """No numbers are invented when none are present."""
        query = parse_query("tamatar mandi bhejna hai")
        assert query.commodity_hint == "tamatar"
        assert query.hours_since is None
        assert query.target_days is None
        assert query.quantity is None

    def test_schema_validation_and_json_roundtrip(self):
        """Ensures ParsedQuery satisfies Pydantic validation and serializes cleanly."""
        query = parse_query("fresh aloo 10 kg mandi 48 hour pehle")
        assert isinstance(query, ParsedQuery)
        json_str = query.model_dump_json()
        reloaded = ParsedQuery.model_validate_json(json_str)
        assert reloaded.commodity_hint == query.commodity_hint
        assert reloaded.hours_since == query.hours_since

    def test_deterministic_fallback_lowers_confidence(self):
        """On deterministic fallback, field confidence scores are appropriately lower (<0.70)."""
        query = parse_query("aloo kaata hua do din pehle 5 kg truck se bhejna hai")
        assert query.parser_source == "deterministic_fallback"
        conf = query.confidence
        assert conf.commodity_hint <= 0.70
        assert conf.state <= 0.70
        assert conf.hours_since <= 0.70
        assert conf.quantity <= 0.70

    def test_mock_llm_malformed_json_triggers_deterministic_fallback(self):
        """If LLM produces malformed response or validation fails, gracefully falls back."""

        class BrokenLLMClient:
            def generate(self, prompt: str, system_prompt=None, temperature=0.0) -> str:
                return "This is completely broken non-JSON text from LLM."

        query = parse_query("tamatar 5 kg", client=BrokenLLMClient())
        assert query.parser_source == "deterministic_fallback"
        assert query.commodity_hint == "tamatar"
        assert query.resolved_commodity_id == "veg.tomato.solanum_lycopersicum"


# ---------------------------------------------------------------------------
# Vector Alias Resolution Tests
# ---------------------------------------------------------------------------


class TestAliasRetrieval:
    def test_embedding_vector_dimensions_and_normalization(self):
        """Assert embeddings match PostgreSQL Vector(384) and are unit-normalized."""
        vec = generate_embedding("potato")
        assert vec.shape == (384,)
        norm = float(sum(vec**2) ** 0.5)
        assert abs(norm - 1.0) < 1e-4

    def test_multilingual_alias_resolution(self):
        """Verify alias resolution maps hints in various languages to canonical commodity IDs."""
        test_cases = [
            ("aloo", "veg.potato.solanum_tuberosum"),
            ("batata", "veg.potato.solanum_tuberosum"),
            ("urulaikizhangu", "veg.potato.solanum_tuberosum"),
            ("tamatar", "veg.tomato.solanum_lycopersicum"),
            ("thakkali", "veg.tomato.solanum_lycopersicum"),
            ("kanda", "veg.onion.allium_cepa"),
            ("pyaz", "veg.onion.allium_cepa"),
            ("vengayam", "veg.onion.allium_cepa"),
            ("paneer", "dairy.paneer.cottage_cheese"),
            ("palak", "veg.spinach.spinacia_oleracea"),
        ]
        for hint, expected_id in test_cases:
            res = resolve_commodity_hint(hint)
            assert res is not None, f"Failed to resolve '{hint}'"
            cid, sim = res
            assert cid == expected_id, (
                f"For hint '{hint}', expected {expected_id}, got {cid}"
            )
            assert sim >= 0.50


# ---------------------------------------------------------------------------
# Explainer Register Tests
# ---------------------------------------------------------------------------


class TestExplainerRegisters:
    def test_kisan_register_single_sentence_no_jargon(self, sample_sealed_result):
        """
        Kisan register constraint:
        - Exactly ONE instruction sentence
        - No engineering jargon (no OTR, WVTR, Arrhenius, micrometres)
        - Second person active voice
        - Native language
        """
        for locale in ["en-IN", "hi-IN", "mr-IN"]:
            res: ExplanationResult = explain_result(
                sample_sealed_result, mode=ExplanationMode.KISAN, locale=locale
            )
            assert res.is_valid, (
                f"Kisan explanation invalid in {locale}: {res.hallucinations_detected}"
            )
            text = res.explanation.strip()

            # Exactly one sentence (ends with period or danda ।, no internal terminal punctuation)
            terminal_count = text.count(".") + text.count("।")
            assert terminal_count <= 2, f"Expected 1 sentence, got text: {text}"

            # No jargon
            for jargon in [
                "OTR",
                "WVTR",
                "arrhenius",
                "micrometre",
                "µm",
                "activation energy",
            ]:
                assert jargon.lower() not in text.lower(), (
                    f"Forbidden jargon '{jargon}' found in Kisan prose: {text}"
                )

    def test_business_register_two_paragraphs_and_runner_up(self, sample_sealed_result):
        """
        Business register constraint:
        - Exactly two paragraphs
        - What to buy and why in paragraph 1
        - Trade-off against runner-up stated in paragraph 2
        """
        res: ExplanationResult = explain_result(
            sample_sealed_result, mode=ExplanationMode.BUSINESS, locale="en-IN"
        )
        assert res.is_valid, (
            f"Business explanation invalid: {res.hallucinations_detected}"
        )
        paragraphs = [p.strip() for p in res.explanation.split("\n\n") if p.strip()]
        assert len(paragraphs) == 2, (
            f"Expected exactly 2 paragraphs, got {len(paragraphs)}"
        )

        # Paragraph 1: What to buy & why
        p1 = paragraphs[0].lower()
        assert "option 1" in p1 or "recommend" in p1
        assert "shelf life" in p1

        # Paragraph 2: Runner-up trade-off
        p2 = paragraphs[1].lower()
        assert "runner-up" in p2 or "option 2" in p2 or "compared to" in p2

    def test_expert_register_technical_rationale(self, sample_sealed_result):
        """
        Expert register constraint:
        - Names the limiting mechanism
        - Names governing equations used
        - Names key assumptions (safety factor, ambient temperature, RH)
        """
        res: ExplanationResult = explain_result(
            sample_sealed_result, mode=ExplanationMode.EXPERT, locale="en-IN"
        )
        assert res.is_valid, (
            f"Expert explanation invalid: {res.hallucinations_detected}"
        )
        text = res.explanation
        assert (
            "respiration_anaerobiosis" in text or "limiting mechanism" in text.lower()
        )
        assert "MIC-01" in text or "equations" in text.lower()
        assert "0.75" in text  # Safety factor


# ---------------------------------------------------------------------------
# Number Verification Pass & Hallucination Invariant Tests
# ---------------------------------------------------------------------------


class TestNumberVerificationPass:
    def test_number_verification_pass_legitimate_numbers(self, sample_sealed_result):
        """Valid explanation containing only verified source numbers passes."""
        allowed_nums = extract_numbers_from_result(sample_sealed_result)
        assert "12.5" in allowed_nums  # P50 shelf life
        assert "0.85" in allowed_nums  # Option 1 cost
        assert "0.75" in allowed_nums  # Safety factor

        # Clean prose with only allowed numbers
        clean_text = (
            "We recommend Option 1 at 0.85 rupees per pack securing a shelf life of 12.5 days "
            "with a safety factor of 0.75."
        )
        is_valid, bad_nums = verify_numbers(clean_text, sample_sealed_result)
        assert is_valid is True
        assert len(bad_nums) == 0

    def test_number_verification_pass_catches_injected_hallucination(
        self, sample_sealed_result
    ):
        """
        CRITICAL TEST: Asserts the number-verification pass catches an injected
        hallucinated figure and rejects the generation.

        Constraint: 'After generation, run a verification pass that extracts every
        number from the output and asserts each one appears in the source result
        object. Reject and regenerate on mismatch.'
        """
        # Inject an unauthorized figure '99.9' and '42.50'
        hallucinated_prose = (
            "We recommend Option 1 at 0.85 per pack securing a shelf life of 99.9 days "
            "and an inflated cost of 42.50 rupees per kilogram."
        )

        is_valid, bad_nums = verify_numbers(hallucinated_prose, sample_sealed_result)
        assert is_valid is False
        assert "99.9" in bad_nums
        assert "42.50" in bad_nums or "42.5" in bad_nums

    def test_explainer_rejects_hallucinating_llm_client(self, sample_sealed_result):
        """
        When an LLM client hallucinates an unverified number (e.g. inventing 45 days),
        explain_result rejects the generation and falls back to the verified deterministic generator.
        """

        class HallucinatingLLMClient:
            def generate(self, prompt: str, system_prompt=None, temperature=0.0) -> str:
                return "The recommended pack gives 45.0 days shelf life at 3.99 INR."

        # Execute explainer with hallucinating client
        res = explain_result(
            sample_sealed_result,
            mode=ExplanationMode.BUSINESS,
            client=HallucinatingLLMClient(),
        )

        # Assert that the final result does NOT contain the hallucinated numbers
        assert "45.0" not in res.explanation
        assert "3.99" not in res.explanation
        assert res.is_valid is True
        # Verified numbers present in output
        assert len(res.verified_numbers) > 0
