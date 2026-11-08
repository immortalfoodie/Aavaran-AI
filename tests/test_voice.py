"""
Tests for the Aavaran Saathi voice layer (Gnani Prisma + Timbre).

Gnani is never called for real: GnaniClient is wired to an httpx.MockTransport
so request shape, auth header and error mapping are all verified offline.
"""

from __future__ import annotations

import base64
import re
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.voice import tts_cache
from api.voice.dialogue import Session, advance, extract_slots, parse_feedback
from api.voice.gnani import STT_URL, TTS_URL, GnaniClient, GnaniError, set_gnani_client
from api.voice.keyterms import build_keyterms
from api.voice.spoken import int_to_words, to_spoken

FAKE_MP3 = b"ID3fake-mp3-bytes"


class FakeGnani:
    """Records requests and plays back canned Prisma / Timbre responses."""

    def __init__(self, transcript: str = "", stt_status: int = 200, tts_status: int = 200):
        self.transcript = transcript
        self.stt_status = stt_status
        self.tts_status = tts_status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == STT_URL:
            if self.stt_status != 200:
                return httpx.Response(self.stt_status, json={"detail": {"error_code": "RATE_LIMITED", "message": "slow down", "status_code": 429}})
            return httpx.Response(200, json={
                "success": True, "request_id": "req-1", "transcript": self.transcript,
                "model": "prisma-v3.0", "detected_language_code": "hi-IN",
                "processing_time": 0.4, "end_to_end_latency": 0.5,
            })
        if url == TTS_URL:
            if self.tts_status != 200:
                return httpx.Response(self.tts_status, json={"success": False, "message": "bad voice", "status_code": 400})
            return httpx.Response(200, content=FAKE_MP3, headers={"content-type": "audio/mpeg"})
        return httpx.Response(404)


@pytest.fixture
def fake_gnani(tmp_path, monkeypatch):
    monkeypatch.setenv("AAVARAN_TTS_CACHE_DIR", str(tmp_path))
    tts_cache.clear_memory()
    fake = FakeGnani()
    set_gnani_client(GnaniClient(api_key="test-key", transport=httpx.MockTransport(fake)))
    yield fake
    set_gnani_client(None)
    tts_cache.clear_memory()


@pytest.fixture
def no_gnani(monkeypatch):
    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    set_gnani_client(None)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------- Gnani client
class TestGnaniClient:
    def test_transcribe_sends_prisma_v3_multipart_with_key_and_context(self):
        fake = FakeGnani(transcript="आलू कटा हुआ है")
        c = GnaniClient(api_key="k-123", transport=httpx.MockTransport(fake))
        res = c.transcribe(b"RIFF....WAVE", lang="hi-en", keyterms=["aloo", "कांदा"])
        assert res.transcript == "आलू कटा हुआ है"
        assert res.model == "prisma-v3.0"
        req = fake.requests[0]
        assert req.headers["X-API-Key-ID"] == "k-123"
        body = req.content.decode("utf-8", errors="ignore")
        assert 'name="audio_file"' in body
        assert "prisma-v3.0" in body
        assert "hi-IN,en-IN" in body  # Hinglish -> multi-language hint
        assert 'name="keyterms"' in body and "aloo" in body
        assert 'name="topic"' in body

    def test_synthesize_posts_timbre_json_and_returns_audio(self):
        fake = FakeGnani()
        c = GnaniClient(api_key="k", transport=httpx.MockTransport(fake))
        audio = c.synthesize("नमस्ते", lang="mr-IN")
        assert audio == FAKE_MP3
        payload = json.loads(fake.requests[0].content)
        assert payload["model"] == "timbre-v3.0"
        assert payload["language"] == "mr-IN"
        assert payload["voice"] == "Shivani"
        assert payload["audio_config"]["container"] == "mp3"

    def test_hinglish_uses_dedicated_code_mixed_voice(self):
        fake = FakeGnani()
        c = GnaniClient(api_key="k", transport=httpx.MockTransport(fake))
        c.synthesize("Aapka aloo theek hai", lang="hi-en")
        payload = json.loads(fake.requests[0].content)
        assert (payload["model"], payload["voice"], payload["language"]) == ("timbre-v2.5", "Poorvi", "hi-en")

    def test_error_mapping(self):
        fake = FakeGnani(stt_status=429)
        c = GnaniClient(api_key="k", transport=httpx.MockTransport(fake))
        with pytest.raises(GnaniError) as exc:
            c.transcribe(b"abc")
        assert exc.value.status_code == 429
        assert exc.value.code == "RATE_LIMITED"

    def test_missing_key_is_not_configured(self):
        c = GnaniClient(api_key="")
        assert not c.enabled
        with pytest.raises(GnaniError) as exc:
            c.synthesize("hi")
        assert exc.value.code == "NOT_CONFIGURED"


# --------------------------------------------------------------------------- helpers
class TestSpokenAndKeyterms:
    @pytest.mark.parametrize("n,lang,expected", [
        (18, "hi", "अठारह"), (135, "hi", "एक सौ पैंतीस"), (2, "mr", "दोन"),
        (250, "mr", "दोनशे पन्नास"), (100, "mr", "शंभर"), (42, "en", "forty-two"),
    ])
    def test_int_to_words(self, n, lang, expected):
        assert int_to_words(n, lang) == expected

    def test_to_spoken_rupees_and_gauge(self):
        out = to_spoken("₹1.75 प्रति पैकेट, 20u BOPP / 40u CPP", "hi-IN")
        assert "एक रुपये पचहत्तर पैसे" in out
        assert "बीस माइक्रोन BOPP" in out
        assert not any(ch.isdigit() for ch in out)

    def test_keyterms_include_kb_names_and_are_capped(self):
        terms = build_keyterms()
        assert 0 < len(terms) <= 200
        assert "कांदा" in terms
        assert not any("." in t for t in terms)


# --------------------------------------------------------------------------- slot extraction
class TestSlotExtraction:
    def test_hinglish_one_shot(self):
        s = extract_slots("aloo kaata hua do din pehle, shed mein rakha hai", "kisan")
        assert s == {"commodity_id": "veg.potato.solanum_tuberosum", "physical_state": "cut",
                     "hours_since": 48.0, "storage": "shed"}

    def test_marathi_devanagari(self):
        s = extract_slots("कांदा अख्खे आहेत, काल काढले, शेडमध्ये ठेवले", "kisan")
        assert s["commodity_id"] == "veg.onion.allium_cepa"
        assert s["physical_state"] == "whole"
        assert s["hours_since"] == 24.0
        assert s["storage"] == "shed"

    def test_business_pack_and_months(self):
        s = extract_slots("namkeen ka 200 gram packet, chhe mahine chalna chahiye", "business")
        assert s["pack_size_g"] == 200.0
        assert s["target_days"] == 180.0

    def test_bare_number_uses_expected_slot(self):
        assert extract_slots("250", "business", expecting="pack_size_g") == {"pack_size_g": 250.0}
        assert extract_slots("90", "business", expecting="target_days") == {"target_days": 90.0}

    def test_feedback_parse(self):
        assert parse_feedback("5 din chala, phir kharab ho gaya") == {"actual_shelf_life_days": 5.0, "spoilage_observed": True}
        assert parse_feedback("दस दिन ठीक रहा, कुछ खराब नहीं हुआ")["spoilage_observed"] is False


# --------------------------------------------------------------------------- dialogue
class TestDialogue:
    def test_cut_potato_is_refused(self):
        s = Session(id="t1", mode="kisan", lang="hi-IN")
        out = advance(s, "आलू कटा हुआ है, दो दिन पहले काटा, शेड में रखा है")
        assert out.status == "blocked"
        assert out.result is not None and out.result.verdict == "NOT_A_PACKAGING_PROBLEM"
        assert "पैकेजिंग की समस्या नहीं" in out.reply_text
        assert "जालीदार" not in out.reply_text  # never suggest a sack for a blocked case

    def test_asks_one_missing_slot_at_a_time(self):
        s = Session(id="t2", mode="kisan", lang="mr-IN")
        assert advance(s, "कांदा आहे").asked_slot == "physical_state"
        assert advance(s, "अख्खे").asked_slot == "hours_since"
        assert advance(s, "काल").asked_slot == "storage"
        done = advance(s, "शेडमध्ये")
        assert done.status == "done"
        assert done.result.verdict == "RECOMMENDED"
        assert not re.search(r"\d+\.\d+", done.reply_text)  # whole days only, never a decimal
        assert "दिवस" in done.reply_text

    def test_processed_food_routes_to_business(self):
        s = Session(id="t3", mode="kisan", lang="hi-IN")
        out = advance(s, "मैं नमकीन बेचता हूँ")
        assert s.mode == "business"
        assert out.asked_slot == "pack_size_g"

    def test_business_reply_uses_only_engine_numbers(self):
        s = Session(id="t4", mode="business", lang="en-IN")
        out = advance(s, "namkeen 200 gram pack, must last 90 days")
        assert out.status == "done"
        c1 = out.result.candidates[0]
        assert f"₹{c1.cost_per_pack:g}" in out.reply_text or f"₹{c1.cost_per_pack}" in out.reply_text

    def test_paneer_asks_storage_then_refuses_at_ambient(self):
        s = Session(id="t5", mode="business", lang="en-IN")
        assert advance(s, "paneer 200 gram, 7 days").asked_slot == "storage"
        out = advance(s, "kept in the shop, normal room")
        assert out.status == "blocked"

    def test_unknown_crop_is_honest(self):
        s = Session(id="t6", mode="kisan", lang="en-IN")
        out = advance(s, "kiwi")
        assert out.status == "asking"
        assert "don't have data" in out.reply_text


# --------------------------------------------------------------------------- API
class TestVoiceApi:
    def test_status_without_key(self, client, no_gnani):
        body = client.get("/api/v1/voice/status").json()
        assert body["gnani_enabled"] is False
        assert "hi-en" in body["languages"]

    def test_text_turn_without_key_still_works_text_only(self, client, no_gnani):
        start = client.post("/api/v1/voice/start", json={"mode": "kisan", "lang": "hi-en"}).json()
        assert start["reply_audio_b64"] is None and start["tts_error"] == "NOT_CONFIGURED"
        r = client.post("/api/v1/voice/text-turn", json={
            "session_id": start["session_id"], "mode": "kisan", "lang": "hi-en",
            "text": "aloo kaata hua do din pehle shed mein",
        }).json()
        assert r["status"] == "blocked"
        assert r["result"]["verdict"] == "NOT_A_PACKAGING_PROBLEM"
        assert r["slots"]["time_interval"] == "two_days"

    def test_audio_turn_round_trip(self, client, fake_gnani):
        fake_gnani.transcript = "टमाटर हैं, आज तोड़े, साबुत, कोल्ड स्टोरेज में"
        r = client.post(
            "/api/v1/voice/turn",
            files={"audio_file": ("speech.wav", b"RIFF0000WAVEfmt ", "audio/wav")},
            data={"mode": "kisan", "lang": "hi-IN"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["transcript"].startswith("टमाटर")
        assert body["status"] == "done"
        assert body["stt"]["model"] == "prisma-v3.0"
        assert base64.b64decode(body["reply_audio_b64"]) == FAKE_MP3
        assert body["recommend_input"]["environment"]["storage_type"] == "refrigerated"
        # TTS text must be digit-free (Timbre reads words, not numerals)
        tts_req = [q for q in fake_gnani.requests if str(q.url) == TTS_URL][-1]
        assert not any(ch.isdigit() for ch in json.loads(tts_req.content)["text"])

    def test_tts_is_cached(self, client, fake_gnani):
        for _ in range(2):
            r = client.post("/api/v1/voice/tts", json={"text": "नमस्ते", "lang": "hi-IN"})
            assert r.status_code == 200 and r.content == FAKE_MP3
        assert len([q for q in fake_gnani.requests if str(q.url) == TTS_URL]) == 1

    def test_audio_turn_without_key_is_503(self, client, no_gnani):
        r = client.post("/api/v1/voice/turn", files={"audio_file": ("a.wav", b"x", "audio/wav")})
        assert r.status_code == 503

    def test_spoken_feedback_saved(self, client, no_gnani):
        r = client.post("/api/v1/voice/text-turn", json={"mode": "kisan", "lang": "hi-IN", "speak": False,
                                                         "text": "प्याज साबुत है, कल निकाला, शेड में"}).json()
        rid = r["result"]["result_id"]
        fb = client.post("/api/v1/voice/feedback", data={"result_id": rid, "lang": "hi-IN", "text": "पता नहीं"}).json()
        assert fb["status"] == "asking"  # no number heard -> Saathi asks again
        fb = client.post("/api/v1/voice/feedback", data={"result_id": rid, "lang": "hi-IN", "text": "बारह दिन ठीक रहा"}).json()
        assert fb["status"] == "saved"
        assert fb["record"]["actual_shelf_life_days"] == 12.0
        assert fb["record"]["spoilage_observed"] is False
