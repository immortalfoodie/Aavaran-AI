"""
Tests for the Aavaran expansion: 10 languages, new crops, chilling-injury warnings,
low-cost storage options and mandi prices. No network: data.gov.in is mocked.
"""

from __future__ import annotations

import contextlib
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api import lowcost, market
from api.main import app
from api.voice.dialogue import Session, advance, normalize_lang
from api.voice.texts import LANGS, TEXT


def _advance(session, text):
    with contextlib.redirect_stdout(io.StringIO()):  # engine prints diagnostics
        return advance(session, text)


# --------------------------------------------------------------------------- languages
class TestLanguages:
    def test_every_sentence_exists_in_every_language(self):
        single_lang_keys = {"kisan_hinglish", "blocked_hinglish"}
        for key, table in TEXT.items():
            if key in single_lang_keys:
                continue
            missing = [l for l in LANGS if l not in table]
            assert not missing, f"{key} missing {missing}"

    @pytest.mark.parametrize("raw,expected", [("ta", "ta-IN"), ("te-IN", "te-IN"), ("kn", "kn-IN"), ("gu", "gu-IN"),
                                              ("pa", "pa-IN"), ("bn", "bn-IN"), ("hinglish", "hi-en"), ("xx", "hi-IN")])
    def test_normalize_lang(self, raw, expected):
        assert normalize_lang(raw) == expected

    @pytest.mark.parametrize("lang,utterance,crop", [
        ("ta-IN", "தக்காளி முழு, நேற்று, கொட்டகை", "veg.tomato.solanum_lycopersicum"),
        ("te-IN", "ఉల్లిపాయ మొత్తం నిన్న షెడ్", "veg.onion.allium_cepa"),
        ("gu-IN", "ડુંગળી આખું ગઈકાલે શેડ", "veg.onion.allium_cepa"),
        ("pa-IN", "ਪਿਆਜ਼ ਸਾਬਤ ਕੱਲ੍ਹ ਸ਼ੈੱਡ", "veg.onion.allium_cepa"),
        ("kn-IN", "ಈರುಳ್ಳಿ ಪೂರ್ತಿ ನಿನ್ನೆ ಶೆಡ್", "veg.onion.allium_cepa"),
        ("bn-IN", "আলু আস্ত, আজ, কোল্ড স্টোরেজ", "veg.potato.solanum_tuberosum"),
    ])
    def test_one_shot_in_new_languages(self, lang, utterance, crop):
        s = Session(id="l", mode="kisan", lang=lang)
        out = _advance(s, utterance)
        assert out.status == "done", (lang, s.slots)
        assert s.slots["commodity_id"] == crop
        # The answer must not fall back to a Hindi crop word mid-sentence.
        assert "प्याज" not in out.reply_text and "आलू" not in out.reply_text

    def test_tamil_business_days(self):
        s = Session(id="b", mode="business", lang="ta-IN")
        out = _advance(s, "namkeen 200 கிராம், 90 நாள்")
        assert s.slots["pack_size_g"] == 200.0 and s.slots["target_days"] == 90.0
        assert out.status == "done"


# --------------------------------------------------------------------------- crops & chilling
class TestNewCropsAndChilling:
    @pytest.mark.parametrize("utterance,crop", [
        ("अमरूद साबुत कल तोड़े शेड में", "fruit.guava.psidium_guajava"),
        ("फुलकोबी अख्खी आज काढली शेडमध्ये", "veg.cauliflower.brassica_oleracea_botrytis"),
        ("patta gobhi sabut kal shed mein", "veg.cabbage.brassica_oleracea_capitata"),
        ("anar sabut kal shed mein", "fruit.pomegranate.punica_granatum"),
        ("बैंगन साबुत आज तोड़े शेड में", "veg.brinjal.solanum_melongena"),
    ])
    def test_new_crop_recognised(self, utterance, crop):
        s = Session(id="c", mode="kisan", lang="hi-IN")
        out = _advance(s, utterance)
        assert s.slots["commodity_id"] == crop
        assert out.result is not None and out.result.verdict == "RECOMMENDED"

    def test_cut_new_crop_is_refused(self):
        s = Session(id="c2", mode="kisan", lang="en-IN")
        out = _advance(s, "guava cut two days ago kept in shed")
        assert out.status == "blocked"

    def test_brinjal_in_cold_room_warns_chilling(self):
        s = Session(id="c3", mode="kisan", lang="en-IN")
        out = _advance(s, "brinjal whole picked today kept in cold storage")
        assert out.status == "done"
        assert "chilling injury below 10 degrees" in out.reply_text

    def test_onion_in_shed_has_no_chilling_warning(self):
        s = Session(id="c4", mode="kisan", lang="en-IN")
        out = _advance(s, "onion whole picked yesterday kept in shed")
        assert "chilling" not in out.reply_text


# --------------------------------------------------------------------------- low-cost options
FAKE_LOWCOST = {
    "options": [
        {
            "id": "zecc",
            "names": {"en": "Zero energy cool chamber", "hi": "शून्य ऊर्जा शीत कक्ष", "mr": "शून्य ऊर्जा शीतकक्ष"},
            "how_to": {"en": "Brick walls with wet sand.", "hi": "ईंट की दीवार, बीच में गीली रेत।", "mr": "विटांच्या भिंती, मध्ये ओली वाळू."},
            "cost_inr": {"low": 3000, "high": 5000, "basis": "test", "src": "SRC-A"},
            "applies_to": ["veg.tomato.solanum_lycopersicum"],
            "benefit": [{"commodity_id": "veg.tomato.solanum_lycopersicum", "ambient_days": [3, 5],
                         "with_option_days": [8, 12], "src": "SRC-A"}],
            "works_when": {"requires": ["water daily"]},
        },
        {
            "id": "sorting",
            "names": {"en": "Sort out damaged ones"},
            "how_to": {"en": "Remove bruised fruit first."},
            "cost_inr": {"low": 0, "high": 0, "src": "SRC-B"},
            "applies_to": ["veg.tomato.solanum_lycopersicum"],
            "benefit": [{"commodity_id": "veg.tomato.solanum_lycopersicum", "ambient_days": [3, 5],
                         "with_option_days": [4, 6], "src": "SRC-B"}],
        },
    ],
    "sources": [{"id": "SRC-A", "citation": "Test source A", "url": "https://example.org/a"}],
}


@pytest.fixture
def fake_lowcost(tmp_path, monkeypatch):
    f = tmp_path / "low_cost_storage.json"
    f.write_text(json.dumps(FAKE_LOWCOST, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(lowcost, "KB_FILE", f)
    lowcost.reload()
    yield
    lowcost.reload()


class TestLowCost:
    def test_sorted_by_gain_and_localised(self, fake_lowcost):
        opts = lowcost.options_for("veg.tomato.solanum_lycopersicum", "hi-IN")
        assert [o["id"] for o in opts] == ["zecc", "sorting"]
        assert opts[0]["name"] == "शून्य ऊर्जा शीत कक्ष"
        assert opts[0]["source"] == "Test source A"
        assert opts[1]["name"] == "Sort out damaged ones"  # falls back to English

    def test_never_for_cut_produce(self, fake_lowcost):
        assert lowcost.options_for("veg.tomato.solanum_lycopersicum", "en-IN", "cut") == []

    def test_spoken_line_only_in_supported_languages(self, fake_lowcost):
        line = lowcost.spoken_line("veg.tomato.solanum_lycopersicum", "hi-IN")
        assert "8 से 12 दिन" in line and "₹3000" in line
        assert lowcost.spoken_line("veg.tomato.solanum_lycopersicum", "ta-IN") is None

    def test_saathi_appends_best_option(self, fake_lowcost):
        s = Session(id="lc", mode="kisan", lang="en-IN")
        out = _advance(s, "tomato whole picked yesterday kept in shed")
        assert "Zero energy cool chamber" in out.reply_text

    def test_api(self, fake_lowcost):
        r = TestClient(app).get("/api/v1/lowcost/veg.tomato.solanum_lycopersicum?lang=en-IN").json()
        assert r["count"] == 2


# --------------------------------------------------------------------------- mandi prices
def _mandi_transport(records):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("filters[commodity]") == "Onion"
        assert request.url.params.get("api-key") == "test-key"
        return httpx.Response(200, json={"records": records})
    return httpx.MockTransport(handler)


@pytest.fixture
def mandi(monkeypatch):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "test-key")
    records = [
        {"state": "Maharashtra", "district": "Nashik", "market": "Lasalgaon", "commodity": "Onion",
         "variety": "Red", "arrival_date": "07/11/2026", "min_price": "1500", "max_price": "2600", "modal_price": "2200"},
        {"state": "Maharashtra", "district": "Nashik", "market": "Pimpalgaon", "commodity": "Onion",
         "variety": "Red", "arrival_date": "08/11/2026", "min_price": "1600", "max_price": "2700", "modal_price": "2300"},
    ]
    market.set_transport(_mandi_transport(records))
    yield
    market.set_transport(None)


class TestMarket:
    def test_latest_first_and_hold_advice(self, mandi):
        r = market.price_insight("veg.onion.allium_cepa", district="Nashik", shelf_life_days=18.6, lang="hi-IN")
        assert r["latest"]["market"] == "Pimpalgaon" and r["latest"]["modal_price"] == 2300
        assert r["advice"] == "can_hold" and r["hold_days"] == 18
        assert "₹2300" in r["spoken"]

    def test_short_shelf_life_says_sell_now(self, mandi):
        assert market.price_insight("veg.onion.allium_cepa", shelf_life_days=1.2)["advice"] == "sell_now"

    def test_not_configured_is_503(self, monkeypatch):
        monkeypatch.delenv("DATA_GOV_IN_API_KEY", raising=False)
        r = TestClient(app).get("/api/v1/market/price?commodity_id=veg.onion.allium_cepa")
        assert r.status_code == 503

    def test_unsupported_commodity(self, mandi):
        r = TestClient(app).get("/api/v1/market/price?commodity_id=dairy.paneer.cottage_cheese")
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "UNSUPPORTED_COMMODITY"
