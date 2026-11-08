"""
Saarthi — Aavaran AI's multi-turn voice dialogue manager.

Turns free speech ("aloo kaata hua do din pehle, shed mein rakha hai") into the
exact structured input the deterministic Aavaran engine needs, asking ONE short
follow-up question at a time for whatever is still missing.

Design rules
- The engine decides; Saarthi only collects inputs and speaks the result.
- No number is ever spoken that did not come from the SealedResult.
- If the engine refuses (NOT_A_PACKAGING_PROBLEM) Saarthi says so plainly.
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.llm.explainer import explain_result
from api.llm.parser import parse_query
from api.llm.schemas import ExplanationMode
from api.voice.spoken import _HI_0_99, _MR_0_99, round_days_for_speech
from engine.orchestrate import recommend
from engine.result import SealedResult
from engine.store import global_result_store

KB_COMMODITY_DIR = Path(__file__).resolve().parents[2] / "kb" / "commodities"

# Crops the Kisan UI can display (web/src/modes/kisan/types.ts CropId)
KISAN_CROPS = {
    "fruit.guava.psidium_guajava",
    "veg.cauliflower.brassica_oleracea_botrytis",
    "veg.cabbage.brassica_oleracea_capitata",
    "fruit.grape.vitis_vinifera",
    "fruit.pomegranate.punica_granatum",
    "veg.brinjal.solanum_melongena",
    "veg.potato.solanum_tuberosum",
    "veg.tomato.solanum_lycopersicum",
    "veg.onion.allium_cepa",
    "fruit.banana.musa_acuminata",
    "fruit.mango.mangifera_indica",
    "veg.okra.abelmoschus_esculentus",
    "veg.spinach.spinacia_oleracea",
    "veg.green_chilli.capsicum_annuum",
}

REQUIRED_SLOTS = {
    "kisan": ["commodity_id", "physical_state", "hours_since", "storage"],
    "business": ["commodity_id", "pack_size_g", "target_days"],
}

# Engine value-of-information fields that a user can answer by voice.
VOI_FIELD_TO_SLOT = {"storage_temperature": "storage", "storage_rh": "storage"}
MIN_VOI_GAIN = 0.10  # only ask if knowing it cuts shelf-life uncertainty by >= 10 %

SESSION_TTL_S = 30 * 60
MAX_SESSIONS = 500


# --------------------------------------------------------------------------- text tables
from api.voice.texts import LANGS, t as _tt  # noqa: E402


def _t(key: str, lang: str, **kw: Any) -> str:
    return _tt(key, lang, **kw)


def normalize_lang(lang: Optional[str]) -> str:
    l = (lang or "hi-IN").strip().lower().replace("_", "-")
    if l in ("hi-en", "hinglish"):
        return "hi-en"
    base = l.split("-")[0]
    for code in LANGS:
        if code.lower().startswith(base + "-") and code != "hi-en":
            return code
    return "hi-IN"


def explainer_locale(lang: str) -> str:
    return "hi-IN" if lang == "hi-en" else lang


# --------------------------------------------------------------------------- slot extraction
WORD_NUMBERS = {
    # Hindi / Hinglish
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10, "pandrah": 15, "bees": 20, "tees": 30, "pachaas": 50,
    "sau": 100,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "पंद्रह": 15, "बीस": 20, "तीस": 30, "पचास": 50, "सौ": 100,
    # Marathi
    "दोन": 2, "पाच": 5, "सहा": 6, "नऊ": 9, "दहा": 10, "पंधरा": 15, "वीस": 20, "पन्नास": 50, "शंभर": 100,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "fifty": 50, "hundred": 100,
}
# Every Hindi / Marathi number word 1-99 ("बारह", "पंचवीस" ...) from the TTS tables.
for _i, _w in enumerate(_HI_0_99):
    if _i:
        WORD_NUMBERS.setdefault(_w, _i)
for _i, _w in enumerate(_MR_0_99):
    if _i:
        WORD_NUMBERS.setdefault(_w, _i)

_NUM_TOKEN = r"(\d+(?:\.\d+)?|" + "|".join(sorted((re.escape(w) for w in WORD_NUMBERS), key=len, reverse=True)) + r")"

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _num(tok: str) -> Optional[float]:
    tok = tok.strip().lower()
    if tok in WORD_NUMBERS:
        return float(WORD_NUMBERS[tok])
    try:
        return float(tok)
    except ValueError:
        return None


def _has_any(text: str, words: List[str]) -> bool:
    for w in words:
        if any(ord(c) > 127 for c in w):
            if w in text:
                return True
        elif re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text):
            return True
    return False


@lru_cache(maxsize=1)
def _commodity_name_index() -> tuple:
    """(name, commodity_id) pairs from KB, longest names first."""
    pairs: List[tuple] = []
    if KB_COMMODITY_DIR.exists():
        for path in KB_COMMODITY_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            cid = data.get("commodity_id")
            if not cid:
                continue
            for names in (data.get("names") or {}).values():
                for n in names:
                    if n and "." not in n and len(n) >= 2:
                        pairs.append((n.lower(), cid))
    extra = {
        "aloo": "veg.potato.solanum_tuberosum", "aalu": "veg.potato.solanum_tuberosum",
        "batata": "veg.potato.solanum_tuberosum", "आलू": "veg.potato.solanum_tuberosum",
        "बटाटा": "veg.potato.solanum_tuberosum", "बटाटे": "veg.potato.solanum_tuberosum",
        "pyaaz": "veg.onion.allium_cepa", "pyaz": "veg.onion.allium_cepa", "kanda": "veg.onion.allium_cepa",
        "प्याज": "veg.onion.allium_cepa", "प्याज़": "veg.onion.allium_cepa", "कांदा": "veg.onion.allium_cepa",
        "कांदे": "veg.onion.allium_cepa",
        "tamatar": "veg.tomato.solanum_lycopersicum", "टमाटर": "veg.tomato.solanum_lycopersicum",
        "टोमॅटो": "veg.tomato.solanum_lycopersicum", "टमाटे": "veg.tomato.solanum_lycopersicum",
        "kela": "fruit.banana.musa_acuminata", "केला": "fruit.banana.musa_acuminata",
        "केळी": "fruit.banana.musa_acuminata", "केले": "fruit.banana.musa_acuminata",
        "aam": "fruit.mango.mangifera_indica", "आम": "fruit.mango.mangifera_indica",
        "आंबा": "fruit.mango.mangifera_indica", "आंबे": "fruit.mango.mangifera_indica",
        "bhindi": "veg.okra.abelmoschus_esculentus", "भिंडी": "veg.okra.abelmoschus_esculentus",
        "भेंडी": "veg.okra.abelmoschus_esculentus",
        "palak": "veg.spinach.spinacia_oleracea", "पालक": "veg.spinach.spinacia_oleracea",
        "mirchi": "veg.green_chilli.capsicum_annuum", "hari mirch": "veg.green_chilli.capsicum_annuum",
        "मिर्च": "veg.green_chilli.capsicum_annuum", "मिर्ची": "veg.green_chilli.capsicum_annuum",
        "मिरची": "veg.green_chilli.capsicum_annuum",
        "namkeen": "processed.besan_namkeen.fried_snack", "नमकीन": "processed.besan_namkeen.fried_snack",
        "farsan": "processed.besan_namkeen.fried_snack", "फरसाण": "processed.besan_namkeen.fried_snack",
        "bhujia": "processed.besan_namkeen.fried_snack", "भुजिया": "processed.besan_namkeen.fried_snack",
        "chivda": "processed.besan_namkeen.fried_snack", "चिवडा": "processed.besan_namkeen.fried_snack",
        "milk powder": "dairy.milk_powder.whole", "doodh powder": "dairy.milk_powder.whole",
        "दूध पाउडर": "dairy.milk_powder.whole", "दूध पावडर": "dairy.milk_powder.whole",
        "paneer": "dairy.paneer.cottage_cheese", "पनीर": "dairy.paneer.cottage_cheese",
        "haldi": "spice.turmeric_powder.curcuma_longa", "हल्दी": "spice.turmeric_powder.curcuma_longa",
        "हळद": "spice.turmeric_powder.curcuma_longa", "turmeric": "spice.turmeric_powder.curcuma_longa",
    }
    pairs.extend(extra.items())
    seen = set()
    uniq = []
    for n, c in sorted(pairs, key=lambda p: len(p[0]), reverse=True):
        if n not in seen:
            seen.add(n)
            uniq.append((n, c))
    return tuple(uniq)


def _find_commodity(text: str) -> Optional[str]:
    for name, cid in _commodity_name_index():
        if _has_any(text, [name]):
            return cid
    # Fall back to the existing multilingual parser + alias resolver
    try:
        pq = parse_query(text)
        if pq.resolved_commodity_id and pq.commodity_hint:
            return pq.resolved_commodity_id
    except Exception:
        pass
    return None


STATE_WORDS = {
    "cut": ["cut", "sliced", "chopped", "kata", "kaata", "kati", "kate", "kaat", "kapla", "kaapla", "kaplela",
            "कटा", "कटे", "कटी", "काटा", "काटे", "काटी", "कापले", "कापलेला", "कापलेले", "कापलेली", "चिरलेले", "टुकड़े",
            "வெட்டிய", "நறுக்கிய", "కోసిన", "ముక్కలు", "ಕತ್ತರಿಸಿದ", "કાપેલું", "કાપેલા", "ਕੱਟਿਆ", "ਕੱਟੇ", "কাটা"],
    "washed": ["washed", "dhoya", "dhoye", "dhula", "dhule", "धोया", "धोए", "धुले", "धुला", "धुतलेले", "धुतलेला",
               "கழுவிய", "కడిగిన", "ತೊಳೆದ", "ધોયેલું", "ਧੋਤਾ", "ধোয়া"],
    "damaged": ["bruised", "damaged", "kharab", "daba", "dabe", "sada", "sadne", "खराब", "दबा", "दबे", "सड़", "सडलेले",
                "दबलेले", "मार लगा",
                "நசுங்கிய", "అழுகిన", "పాడైన", "ಜಜ್ಜಿದ", "ಹಾಳಾದ", "બગડેલું", "ਖ਼ਰਾਬ", "ਖਰਾਬ", "থেঁতলে", "নষ্ট"],
    "whole": ["whole", "sabut", "saabut", "poora", "pura", "pure", "akkha", "akkhe", "fresh", "taaza", "taza",
              "साबुत", "पूरा", "पूरे", "अख्खा", "अख्खे", "अख्खी", "अक्खा", "आख्खा", "पूरी", "साबूत", "ताजा", "ताज़ा", "ताजे",
              "முழு", "మొత్తం", "తాజా", "ಪೂರ್ತಿ", "ತಾಜಾ", "આખું", "આખા", "તાજું", "ਸਾਬਤ", "ਤਾਜ਼ਾ", "আস্ত", "টাটকা"],
}

STORAGE_WORDS = {
    "ice": ["ice", "barf", "baraf", "बर्फ", "बर्फात", "बर्फ़", "ஐஸ்", "ఐస్", "ಐಸ್", "બરફ", "ਬਰਫ਼", "বরফ"],
    "cold_room": ["cold storage", "cold room", "coldstorage", "fridge", "refrigerator", "cold", "कोल्ड", "फ्रिज",
                  "शीतगृह", "ठंडे गोदाम", "शीत भंडार",
                  "குளிர் சேமிப்பு", "கோல்ட் ஸ்டோரேஜ்", "కోల్డ్ స్టోరేజ్", "ಕೋಲ್ಡ್ ಸ್ಟೋರೇಜ್", "કોલ્ડ સ્ટોરેજ", "ਕੋਲਡ ਸਟੋਰੇਜ",
                  "কোল্ড স্টোরেজ", "ফ্রিজ"],
    "shed": ["shed", "godown", "room", "kamra", "kamre", "ghar", "bahar", "khule", "open", "ambient", "dukaan",
             "शेड", "गोदाम", "कमरे", "कमरा", "घर", "बाहर", "खुले", "खोली", "खोलीत", "दुकान", "मंडी", "mandi", "normal",
             "सामान्य", "साध्या",
             "கொட்டகை", "அறை", "షెడ్", "గది", "ಶೆಡ್", "ಕೋಣೆ", "શેડ", "ઓરડ", "ਸ਼ੈੱਡ", "ਕਮਰੇ", "চালাঘর", "ঘরে", "kirana", "किराना"],
}


def _hours_from_text(text: str, expecting: bool) -> Optional[float]:
    if _has_any(text, ["abhi", "aaj", "today", "just now", "आज", "अभी", "आत्ताच", "आत्ता", "subah", "सुबह", "सकाळी",
                         "இன்று", "ఈరోజు", "ఈ రోజు", "ಇಂದು", "આજે", "ਅੱਜ", "আজ"]):
        return 4.0
    if _has_any(text, ["parso", "parson", "परसों", "परवा", "day before yesterday", "நேற்று முன்தினம்", "మొన్న", "ಮೊನ್ನೆ",
                       "પરમદિવસે", "ਪਰਸੋਂ", "পরশু"]):
        return 48.0
    m = re.search(_NUM_TOKEN + r"\s*(?:din|days?|दिन|दिवस|दिवसांपूर्वी|दिवसां|நாள்|நாட்கள்|రోజు|రోజులు|ದಿನ|દિવસ|ਦਿਨ|দিন)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n * 24.0
    m = re.search(_NUM_TOKEN + r"\s*(?:ghante|ghanta|hours?|hrs?|घंटे|घंटा|तास)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n
    if _has_any(text, ["kal", "yesterday", "कल", "काल", "நேற்று", "నిన్న", "ನಿನ್ನೆ", "ગઈકાલે", "ગઈ કાલે", "ਕੱਲ੍ਹ", "গতকাল", "কাল"]):
        return 24.0
    if expecting:
        m = re.fullmatch(r"\s*" + _NUM_TOKEN + r"\s*", text)
        if m:
            n = _num(m.group(1))
            if n is not None:
                return n * 24.0
    return None


def _pack_size_from_text(text: str, expecting: bool) -> Optional[float]:
    if _has_any(text, ["aadha kilo", "adha kilo", "half kilo", "आधा किलो", "अर्धा किलो"]):
        return 500.0
    if _has_any(text, ["paav kilo", "pav kilo", "पाव किलो"]):
        return 250.0
    m = re.search(_NUM_TOKEN + r"\s*(?:kg|kilo|kilogram|किलो|கிலோ|కిలో|ಕೆಜಿ|ಕಿಲೋ|કિલો|ਕਿਲੋ|কেজি|কিলো)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n * 1000.0
    m = re.search(_NUM_TOKEN + r"\s*(?:g|gm|gms|gram|grams|ग्राम|ग्रॅम|கிராம்|గ్రాములు|గ్రాము|ಗ್ರಾಂ|ગ્રામ|ਗ੍ਰਾਮ|গ্রাম)(?![a-z])", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n
    if expecting:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            return float(m.group(1))
    return None


def _target_days_from_text(text: str, expecting: bool) -> Optional[float]:
    if _has_any(text, ["ek saal", "1 saal", "one year", "1 year", "एक साल", "एक वर्ष", "1 साल", "बारा महिने"]):
        return 365.0
    m = re.search(_NUM_TOKEN + r"\s*(?:mahine|mahina|months?|महीने|महीना|महिने|महिना|மாதம்|மாதங்கள்|నెలలు|నెల|ತಿಂಗಳು|ತಿಂಗಳ|મહિના|ਮਹੀਨੇ|ਮਹੀਨਾ|মাস)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n * 30.0
    m = re.search(_NUM_TOKEN + r"\s*(?:hafte|hafta|weeks?|हफ्ते|हफ़्ते|आठवडे)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n * 7.0
    m = re.search(_NUM_TOKEN + r"\s*(?:din|days?|दिन|दिवस|நாள்|நாட்கள்|రోజులు|రోజు|ದಿನ|દિવસ|ਦਿਨ|দিন)", text)
    if m:
        n = _num(m.group(1))
        if n is not None:
            return n
    if expecting:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            return float(m.group(1))
    return None


def extract_slots(text: str, mode: str, expecting: Optional[str] = None) -> Dict[str, Any]:
    """Pull every slot we can hear in this utterance. Never guesses missing ones."""
    clean = (text or "").translate(DEVANAGARI_DIGITS).lower().strip()
    clean = re.sub(r"[।॥,.!?]", " ", clean)
    clean = re.sub(r"\s+", " ", clean)
    out: Dict[str, Any] = {}
    if not clean:
        return out

    cid = _find_commodity(clean)
    if cid:
        out["commodity_id"] = cid

    if mode == "kisan":
        for state, words in STATE_WORDS.items():
            if _has_any(clean, words):
                out["physical_state"] = state
                break
        hrs = _hours_from_text(clean, expecting == "hours_since")
        if hrs is not None:
            out["hours_since"] = hrs
        for storage, words in STORAGE_WORDS.items():
            if _has_any(clean, words):
                out["storage"] = storage
                break
    else:
        # Business: strip pack-size phrases before looking for durations, and vice versa.
        size = _pack_size_from_text(clean, expecting == "pack_size_g")
        if size is not None and expecting != "target_days":
            out["pack_size_g"] = size
        days_text = re.sub(_NUM_TOKEN + r"\s*(?:kg|kilo|किलो|கிலோ|కిలో|ಕೆಜಿ|ಕಿಲೋ|કિલો|ਕਿਲੋ|কেজি|কিলো|g|gm|gram|grams|ग्राम|ग्रॅम|கிராம்|గ్రాములు|గ్రాము|ಗ್ರಾಂ|ગ્રામ|ਗ੍ਰਾਮ|গ্রাম)(?![a-z])", " ", clean)
        days = _target_days_from_text(days_text, expecting == "target_days")
        if days is not None and expecting != "pack_size_g":
            out["target_days"] = days
        elif days is not None and "pack_size_g" not in out:
            out["target_days"] = days
        for storage, words in STORAGE_WORDS.items():
            if _has_any(clean, words):
                out["storage"] = storage
                break
    return out


# --------------------------------------------------------------------------- session store
@dataclass
class Session:
    id: str
    mode: str
    lang: str
    slots: Dict[str, Any] = field(default_factory=dict)
    turns: List[Dict[str, str]] = field(default_factory=list)
    asked: List[str] = field(default_factory=list)
    result_id: Optional[str] = None
    status: str = "asking"
    touched: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, Session] = {}

    def create(self, mode: str, lang: str) -> Session:
        s = Session(id=uuid.uuid4().hex[:16], mode=mode, lang=lang)
        with self._lock:
            self._evict()
            self._items[s.id] = s
        return s

    def get(self, sid: Optional[str]) -> Optional[Session]:
        if not sid:
            return None
        with self._lock:
            s = self._items.get(sid)
            if s and time.time() - s.touched > SESSION_TTL_S:
                del self._items[sid]
                return None
            if s:
                s.touched = time.time()
            return s

    def _evict(self) -> None:
        now = time.time()
        for k in [k for k, v in self._items.items() if now - v.touched > SESSION_TTL_S]:
            del self._items[k]
        while len(self._items) >= MAX_SESSIONS:
            oldest = min(self._items.values(), key=lambda v: v.touched)
            del self._items[oldest.id]


session_store = SessionStore()


# --------------------------------------------------------------------------- engine bridge
STORAGE_ENV = {
    "shed": {"storage_type": "ambient", "temperature": 30.0},
    "cold_room": {"storage_type": "refrigerated", "temperature": 4.0},
    "ice": {"storage_type": "chilled", "temperature": 2.0},
}


def build_recommend_input(session: Session) -> Dict[str, Any]:
    s = session.slots
    if session.mode == "kisan":
        hrs = float(s.get("hours_since", 24.0))
        state = s.get("physical_state", "whole")
        return {
            "commodity_id": s["commodity_id"],
            "state": {
                "cut": state == "cut",
                "washed": state == "washed",
                "bruised": state == "damaged",
                "hoursSinceCut": hrs,
                "hoursSinceHarvest": hrs,
            },
            "environment": dict(STORAGE_ENV.get(s.get("storage", "shed"), STORAGE_ENV["shed"])),
        }
    size = float(s.get("pack_size_g", 200.0))
    inp: Dict[str, Any] = {
        "commodity_id": s["commodity_id"],
        "pack_size_g": size,
        "target_shelf_life_days": float(s.get("target_days", 90.0)),
        "pack_geometry": {"product_mass_kg": size / 1000.0},
    }
    if s.get("storage"):
        env = STORAGE_ENV.get(s["storage"], STORAGE_ENV["shed"])
        inp["environment"] = {"storage_type": env["storage_type"], "temperature_c": env["temperature"]}
    return inp


def hours_to_interval(hours: float) -> str:
    if hours <= 12:
        return "today"
    if hours <= 36:
        return "one_day"
    if hours <= 60:
        return "two_days"
    return "three_days_plus"


def _commodity_label(result: SealedResult, lang: str) -> str:
    comm = result.resolved.commodity if result.resolved else None
    names = getattr(comm, "names", None) or {}
    if lang == "hi-en":
        for n in names.get("hi", []):
            if n.isascii():
                return n
        en = names.get("en") or ["it"]
        return en[0]
    key = lang.split("-")[0]
    lst = names.get(key) or names.get("en") or ["it"]
    return lst[0]


def _layers_spoken(candidate: Any) -> str:
    stack = getattr(candidate, "layer_stack", None) or []
    return ", ".join(stack) if stack else (getattr(candidate, "name", "") or "")


def _num_str(v: Optional[float]) -> str:
    if v is None:
        return ""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def compose_spoken_result(result: SealedResult, session: Session) -> str:
    """One short spoken answer built ONLY from SealedResult numbers."""
    lang = session.lang
    blocked = result.verdict == "NOT_A_PACKAGING_PROBLEM"
    comm = _commodity_label(result, lang)
    was_cut = session.slots.get("physical_state") == "cut"

    if blocked:
        if lang == "hi-en":
            base = _t("blocked_hinglish", lang, comm=comm)
        else:
            base = explain_result(result, mode=ExplanationMode.KISAN, locale=explainer_locale(lang)).explanation
        return f"{base} {_t('cut_tail', lang)}" if was_cut else base

    days = round_days_for_speech(result.shelf_life.days_p50 if result.shelf_life else None)

    if session.mode == "kisan":
        if lang == "hi-en":
            pkg = (result.recommendation.packaging_name if result.recommendation else "") or "hawadar packing"
            return _t("kisan_hinglish", lang, comm=comm, pkg=pkg, days=days)
        base = explain_result(result, mode=ExplanationMode.KISAN, locale=explainer_locale(lang)).explanation
        # Speak whole days only (conservative floor), never a decimal.
        return re.sub(r"(\d+)\.\d+", lambda m: str(int(m.group(1))), base)

    # Business: top two options with ₹/pack and days, plus target check.
    cands = list(result.candidates or [])[:3]
    if not cands:
        return _t("see_screen", lang)
    c1 = cands[0]
    c2 = cands[1] if len(cands) > 1 else None
    target = session.slots.get("target_days")
    size = int(float(session.slots.get("pack_size_g", 0)))
    parts = [_t("biz_best", lang, size=size, comm=comm, layers=_layers_spoken(c1), cost=_num_str(c1.cost_per_pack), days=days)]
    if c2 is not None:
        parts.append(_t("biz_second", lang, layers=_layers_spoken(c2), cost=_num_str(c2.cost_per_pack)))
    if days is not None and target is not None and days < float(target):
        parts.append(_t("biz_short", lang, target=int(float(target))))
    parts.append(_t("see_screen", lang))
    return " ".join(parts)


def chilling_risk(result: SealedResult) -> Optional[float]:
    """Chilling-injury threshold (deg C) if the storage temperature is below it, else None.

    The threshold is the sourced `chilling_sensitive_below_C` from the commodity profile
    (USDA AH-66). The engine's shelf-life models do not penalise chilling injury, so this
    is surfaced as an explicit warning instead.
    """
    resolved = result.resolved
    comm = resolved.commodity if resolved else None
    env = resolved.environment if resolved else None
    if comm is None or env is None or comm.chilling_sensitive_below_c is None or env.temperature is None:
        return None
    thr = comm.chilling_sensitive_below_c.value
    temp = env.temperature.value
    if thr is None or temp is None:
        return None
    thr_f, temp_f = float(thr), float(temp)
    return thr_f if temp_f < thr_f else None


def summarize_result(result: SealedResult) -> Dict[str, Any]:
    return {
        "chilling_below_c": chilling_risk(result),
        "result_id": result.result_id,
        "verdict": result.verdict,
        "safety_status": str(getattr(result.safety.status, "value", result.safety.status)) if result.safety else None,
        "days_p50": result.shelf_life.days_p50 if result.shelf_life else None,
        "packaging_name": result.recommendation.packaging_name if result.recommendation else None,
        "key_action": result.recommendation.key_action if result.recommendation else None,
        "candidates": [
            {
                "name": c.name,
                "layer_stack": c.layer_stack,
                "cost_per_pack": c.cost_per_pack,
                "epr_category": c.epr_category,
            }
            for c in (result.candidates or [])[:3]
        ],
        "guidance": [
            {"action": g.get("action"), "headline": g.get("headline")}
            for g in (result.guidance or [])
            if isinstance(g, dict)
        ],
        "value_of_information": result.value_of_information.field if result.value_of_information else None,
    }


# --------------------------------------------------------------------------- the turn
@dataclass
class TurnOutcome:
    status: str  # asking | done | blocked
    reply_text: str
    asked_slot: Optional[str] = None
    result: Optional[SealedResult] = None
    heard: Dict[str, Any] = field(default_factory=dict)


# Perishables whose answer flips on storage temperature: in business mode we ask
# where they are kept instead of silently assuming ambient.
PERISHABLE_BUSINESS = KISAN_CROPS | {"dairy.paneer.cottage_cheese"}


def required_slots(session: Session) -> List[str]:
    slots = list(REQUIRED_SLOTS[session.mode])
    if session.mode == "business" and session.slots.get("commodity_id") in PERISHABLE_BUSINESS:
        slots.append("storage")
    return slots


def _next_missing(session: Session) -> Optional[str]:
    for slot in required_slots(session):
        if slot not in session.slots:
            return slot
    return None


def intro_text(mode: str, lang: str) -> str:
    return _t("intro_business" if mode == "business" else "intro_kisan", lang)


def advance(session: Session, transcript: str) -> TurnOutcome:
    """Merge what the user just said, then either ask for the next slot or run the engine."""
    transcript = (transcript or "").strip()
    expecting = session.asked[-1] if session.asked else None
    session.turns.append({"role": "user", "text": transcript})

    if not transcript:
        reply = _t("not_heard", session.lang)
        session.turns.append({"role": "saathi", "text": reply})
        return TurnOutcome(status="asking", reply_text=reply, asked_slot=expecting)

    # If the session already produced a result, a new utterance either answers the
    # value-of-information follow-up or starts a fresh consultation.
    if session.status in ("done", "blocked") and expecting != "storage_voi":
        fresh = extract_slots(transcript, session.mode)
        if fresh.get("commodity_id"):
            session.slots = {}
            session.result_id = None
        session.status = "asking"

    heard = extract_slots(transcript, session.mode, "storage" if expecting == "storage_voi" else expecting)

    # Auto-route: processed foods belong to the business flow, produce to kisan.
    cid = heard.get("commodity_id")
    if cid and session.mode == "kisan" and cid not in KISAN_CROPS:
        session.mode = "business"
        heard = extract_slots(transcript, "business")
    session.slots.update({k: v for k, v in heard.items() if v is not None})

    missing = _next_missing(session)
    if missing:
        if missing == "commodity_id" and not heard:
            reply = _t("unknown_commodity", session.lang) + " " + _t("commodity_id", session.lang)
        else:
            reply = _t(missing, session.lang)
        session.asked.append(missing)
        session.turns.append({"role": "saathi", "text": reply})
        return TurnOutcome(status="asking", reply_text=reply, asked_slot=missing, heard=heard)

    # All required slots present: run the deterministic engine.
    req = {"mode": session.mode, "input": build_recommend_input(session), "locale": explainer_locale(session.lang)}
    result = recommend(req)
    global_result_store.save(result)
    session.result_id = result.result_id

    blocked = result.verdict == "NOT_A_PACKAGING_PROBLEM"
    reply = compose_spoken_result(result, session)
    session.status = "blocked" if blocked else "done"

    chill = None if blocked else chilling_risk(result)
    if chill is not None:
        reply = f"{reply} {_t('chill_warn', session.lang, comm=_commodity_label(result, session.lang), t=_num_str(chill))}"

    # Farmers: add the single best low-cost, no-plastic option (sourced data only).
    if session.mode == "kisan" and not blocked:
        from api.lowcost import spoken_line

        extra = spoken_line(session.slots["commodity_id"], session.lang, session.slots.get("physical_state"))
        if extra:
            reply = f"{reply} {extra}"

    # One extra question only if the engine says it is the most valuable unknown
    # AND the user can answer it AND we have not asked it yet.
    voi = result.value_of_information
    voi_field = voi.field if voi else None
    voi_gain = float(getattr(voi, "variance_reduction", 0.0) or 0.0) if voi else 0.0
    voi_slot = VOI_FIELD_TO_SLOT.get(voi_field or "")
    if (
        not blocked
        and voi_slot
        and voi_gain >= MIN_VOI_GAIN
        and voi_slot not in session.slots
        and "storage_voi" not in session.asked
    ):
        reply = f"{reply} {_t('storage_voi', session.lang)}"
        session.asked.append("storage_voi")
        session.turns.append({"role": "saathi", "text": reply})
        return TurnOutcome(status="done", reply_text=reply, asked_slot="storage_voi", result=result, heard=heard)

    session.asked.append("__done__")
    session.turns.append({"role": "saathi", "text": reply})
    return TurnOutcome(status=session.status, reply_text=reply, result=result, heard=heard)


# --------------------------------------------------------------------------- spoken feedback
SPOIL_WORDS = ["kharab", "sad", "sada", "sadne", "rot", "rotten", "spoil", "spoiled", "bad", "खराब", "सड़", "सडले",
               "बिगड़", "बिघडले", "गल गया", "fungus", "fafund", "फफूंद", "बुरशी"]
OK_WORDS = ["theek", "thik", "accha", "achha", "good", "fine", "badhiya", "ठीक", "अच्छा", "बढ़िया", "चांगला", "चांगले"]
NEG_WORDS = ["nahi", "nahin", "no", "not", "नहीं", "नही", "नाही"]


def parse_feedback(text: str) -> Dict[str, Any]:
    clean = (text or "").translate(DEVANAGARI_DIGITS).lower()
    clean = re.sub(r"[।॥,.!?]", " ", clean)
    days = None
    m = re.search(_NUM_TOKEN + r"\s*(?:din|days?|दिन|दिवस|நாள்|நாட்கள்|రోజులు|రోజు|ದಿನ|દિવસ|ਦਿਨ|দিন)", clean)
    if m:
        days = _num(m.group(1))
    else:
        m = re.search(_NUM_TOKEN + r"\s*(?:hafte|hafta|weeks?|हफ्ते|आठवडे)", clean)
        if m:
            n = _num(m.group(1))
            days = n * 7 if n is not None else None
        else:
            m = re.search(r"(\d+(?:\.\d+)?)", clean)
            if m:
                days = float(m.group(1))
    spoiled_word = _has_any(clean, SPOIL_WORDS)
    negated = spoiled_word and _has_any(clean, NEG_WORDS)
    spoiled = bool(spoiled_word and not negated)
    return {"actual_shelf_life_days": days, "spoilage_observed": spoiled}
