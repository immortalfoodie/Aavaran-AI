"""
Aavaran Natural Language & Voice Query Parser.

Strictly bounded responsibilities:
- Input: free text in any of English, Hindi, Marathi, Tamil, Telugu,
  Bengali, Kannada, Gujarati, or Punjabi (native scripts, transliterated,
  or mixed/code-mixed).
- Output: a JSON object validated against the ParsedQuery Pydantic schema
  containing commodity_hint, state, hours_since, quantity, destination,
  storage_hint, target_days, plus a per-field confidence.
- Boundary enforcement: The LLM must only extract, never infer physical
  constants (temperature, RH, barrier metrics). If the user did not state
  it, the field remains null. The LLM is explicitly instructed that it must
  not guess numbers.
- Commodity resolution: Resolves commodity_hint against the alias table
  using pgvector cosine similarity, not the LLM. Matching is a retrieval problem.
- Validation & Fallback: Validates every response against the schema. On
  validation failure or LLM unavailability, falls back to a deterministic
  keyword parser and lowers field confidences.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from api.llm.alias_resolver import resolve_commodity_hint
from api.llm.schemas import ParsedQuery, QueryConfidence

logger = logging.getLogger("aavaran.parser")

PARSER_SYSTEM_PROMPT = """You are Aavaran's Natural Language & Voice Query Parser for Indian agricultural supply chains.

STRICT BOUNDED RESPONSIBILITIES:
1. Extraction ONLY: Extract only facts and figures explicitly stated in the user input.
2. DO NOT infer or guess physical constants (e.g., storage temperature, relative humidity, respiration rate, water activity, OTR, WVTR). If the user did not explicitly state the storage temperature, leave the field null and let the Aavaran resolver handle it.
3. DO NOT guess, interpolate, or invent numbers. Only extract numbers explicitly present in the input for hours_since, quantity, or target_days.
4. Extract the user's raw commodity mention into 'commodity_hint'. DO NOT attempt taxonomic mapping or canonical resolution; matching is handled separately as a retrieval problem.
5. Return strictly a single valid JSON object matching this schema:
{
  "commodity_hint": string or null,
  "state": string or null,
  "hours_since": number (float) or null,
  "quantity": string or null,
  "destination": string or null,
  "storage_hint": string or null,
  "target_days": number (float) or null,
  "confidence": {
    "commodity_hint": float (0.0 to 1.0),
    "state": float (0.0 to 1.0),
    "hours_since": float (0.0 to 1.0),
    "quantity": float (0.0 to 1.0),
    "destination": float (0.0 to 1.0),
    "storage_hint": float (0.0 to 1.0),
    "target_days": float (0.0 to 1.0)
  }
}
"""


class LLMClient(Protocol):
    """Protocol for LLM clients that can generate text from prompts."""

    def generate(
        self, prompt: str, system_prompt: str | None = None, temperature: float = 0.0
    ) -> str: ...


# ---------------------------------------------------------------------------
# Deterministic Multilingual Keyword & Token Parser
# ---------------------------------------------------------------------------

# Multi-lingual keyword maps for commodities across 9 Indian languages + English
COMMODITY_KEYWORDS: dict[str, str] = {
    # Potato
    "potatoes": "potato",
    "potato": "potato",
    "solanum": "potato",
    "aloo": "aloo",
    "aalu": "aalu",
    "alu": "alu",
    "batata": "batata",
    "बटाटा": "बटाटा",
    "आलू": "आलू",
    "আলু": "আলু",
    "urulaikizhangu": "urulaikizhangu",
    "urulaikilangu": "urulaikilangu",
    "உருளைக்கிழங்கு": "உருளைக்கிழங்கு",
    "bangaladumpa": "bangaladumpa",
    "alugadda": "alugadda",
    "బంగాళాదుంప": "బంగాళాదుంప",
    "aalugadde": "aalugadde",
    "alugadde": "alugadde",
    "ಆಲೂಗಡ್ಡೆ": "ಆಲೂಗಡ್ಡೆ",
    "bataka": "bataka",
    "બટાકા": "બટાકા",
    "ਆਲੂ": "ਆਲੂ",
    # Tomato
    "tomatoes": "tomato",
    "tomato": "tomato",
    "lycopersicon": "tomato",
    "tamatar": "tamatar",
    "টमाटर": "tamatar",
    "टमाटर": "टमाटर",
    "टोमॅटो": "टोमॅटो",
    "thakkali": "thakkali",
    "தக்காளி": "தக்காளி",
    "tamata": "tamata",
    "tamota": "tamota",
    "టమోటా": "టమోటా",
    "tometo": "tometo",
    "টমেটো": "টমেটো",
    "ಟೊಮೆಟೊ": "ಟೊಮೆಟೊ",
    "tameta": "tameta",
    "ટામેટા": "ટામેટા",
    "ਟਮਾਟਰ": "ਟਮਾਟਰ",
    # Onion
    "onions": "onion",
    "onion": "onion",
    "pyaz": "pyaz",
    "pyaaz": "pyaaz",
    "प्याज": "प्याज",
    "kanda": "kanda",
    "कांदा": "कांदा",
    "vengayam": "vengayam",
    "வெங்காயம்": "வெங்காயம்",
    "ullipaya": "ullipaya",
    "ఉల్లిపాయ": "ఉల్లిపాయ",
    "peyaj": "peyaj",
    "পেঁয়াজ": "পেঁয়াজ",
    "eerulli": "eerulli",
    "irulli": "irulli",
    "ಈರುಳ್ಳಿ": "ಈರುಳ್ಳಿ",
    "dungli": "dungli",
    "dungari": "dungari",
    "ડુંગળી": "ડુંગળી",
    "ਪਿਆਜ਼": "ਪਿਆਜ਼",
    # Mango
    "mangoes": "mango",
    "mango": "mango",
    "alphonso": "alphonso",
    "hapus": "hapus",
    "aam": "aam",
    "आम": "आम",
    "amba": "amba",
    "आंबा": "आंबा",
    "mangai": "mangai",
    "mambazham": "mambazham",
    "மாங்காய்": "மாங்காய்",
    "mamidi": "mamidi",
    "మామిడి": "మామిడి",
    "আম": "আম",
    "mavinakayi": "mavinakayi",
    "ಮಾವಿನಕಾಯಿ": "ಮಾವಿನಕಾಯಿ",
    "keri": "keri",
    "કેરી": "કેરી",
    "ਅੰਬ": "ਅੰਬ",
    # Banana
    "bananas": "banana",
    "banana": "banana",
    "kela": "kela",
    "केला": "केला",
    "kele": "kele",
    "केळे": "केळे",
    "vazhaipazham": "vazhaipazham",
    "வாழை": "வாழை",
    "aratipandu": "aratipandu",
    "అరటిపండు": "అరటిపండు",
    "kola": "kola",
    "কলা": "কলা",
    "balehannu": "balehannu",
    "ಬಾಳೆಹಣ್ಣು": "ಬಾಳೆಹಣ್ಣು",
    "કેળા": "કેળા",
    "ਕੇਲਾ": "ਕੇਲਾ",
    # Green Chilli
    "green chillies": "green chilli",
    "green chilli": "green chilli",
    "chillies": "chilli",
    "chilli": "chilli",
    "mirch": "mirch",
    "mirchi": "mirchi",
    "hari mirch": "hari mirch",
    "मिर्च": "मिर्च",
    "मिरची": "मिरची",
    "pachai milagai": "pachai milagai",
    "மிளகாய்": "மிளகாய்",
    "mirapakaya": "mirapakaya",
    "మిరపకాయ": "మిరపకాయ",
    "lonka": "lonka",
    "কাঁচা লঙ্কা": "কাঁচা লঙ্কা",
    "menasinakayi": "menasinakayi",
    "ಮೆಣಸಿನಕಾಯಿ": "ಮೆಣಸಿನಕಾಯಿ",
    "marcha": "marcha",
    "મરચાં": "મરચાં",
    "ਮਿਰਚ": "ਮਿਰਚ",
    # Okra
    "okras": "okra",
    "okra": "okra",
    "lady finger": "lady finger",
    "bhindi": "bhindi",
    "भिंडी": "भिंडी",
    "bhendi": "bhendi",
    "भेंडी": "भेंडी",
    "vendakkai": "vendakkai",
    "வெண்டைக்காய்": "வெண்டைக்காய்",
    "bendakaya": "bendakaya",
    "బెండకాయ": "బెండకాయ",
    "dharosh": "dharosh",
    "ঢেঁড়শ": "ঢেঁড়শ",
    "bendekayi": "bendekayi",
    "ಬೆಂಡೆಕಾಯಿ": "ಬೆಂಡೆಕಾಯಿ",
    "bhindo": "bhindo",
    "ભીંડો": "ભીંડો",
    "ਭਿੰਡੀ": "ਭਿੰਡੀ",
    # Spinach
    "spinach": "spinach",
    "palak": "palak",
    "पालक": "पालक",
    "pasalai keerai": "pasalai keerai",
    "பசலைக்கீரை": "பசலைக்கீரை",
    "keerai": "keerai",
    "palakura": "palakura",
    "పాలకూర": "పాలకూర",
    "palong shak": "palong shak",
    "পালং শাক": "পালং শাক",
    "palak soppu": "palak soppu",
    "ಪಾಲಕ್": "ಪಾಲಕ್",
    "પાલેક": "પાલેક",
    "પાંદડા": "પાંદડા",
    "ਪਾਲਕ": "ਪਾਲਕ",
    # Paneer
    "paneer": "paneer",
    "cottage cheese": "cottage cheese",
    "पनीर": "पनीर",
    "panir": "panir",
    "பனீர்": "பனீர்",
    "పనీర్": "పనీర్",
    "chhana": "chhana",
    "ponir": "ponir",
    "পনির": "পনির",
    "ಪನ್ನೀರ್": "ಪನ್ನೀರ್",
    "પનીર": "પનીર",
    "ਪਨੀਰ": "ਪਨੀਰ",
    # Milk Powder
    "milk powder": "milk powder",
    "doodh powder": "doodh powder",
    "dudh powder": "dudh powder",
    "दूध पाउडर": "दूध पाउडर",
    "paal powder": "paal powder",
    "பால் பவுடர்": "பால் பவுடர்",
    "pala podi": "pala podi",
    "పాల పొడి": "పాల పొడి",
    "dudher guro": "dudher guro",
    "দুধের গুঁড়ো": "দুধের গুঁড়ো",
    "halina pudi": "halina pudi",
    "ಹಾಲಿನ ಪುಡಿ": "ಹಾಲಿನ ಪುಡಿ",
    "દૂધ પાવડર": "દૂધ પાવડર",
    "ਦੁੱਧ ਪਾਊਡਰ": "ਦੁੱਧ ਪਾਊਡਰ",
    # Turmeric Powder
    "turmeric": "turmeric",
    "haldi": "haldi",
    "हल्दी": "हल्दी",
    "halad": "halad",
    "हळद": "हळद",
    "manjal": "manjal",
    "மஞ்சள்": "மஞ்சள்",
    "pasupu": "pasupu",
    "పసుపు": "పసుపు",
    "holud": "holud",
    "হলুদ": "হলুদ",
    "arishina": "arishina",
    "ಅರಿಶಿನ": "ಅರಿಶಿನ",
    "haldar": "haldar",
    "હળદર": "હળદર",
    "ਹਲਦੀ": "ਹਲਦੀ",
    # Besan Namkeen
    "namkeen": "namkeen",
    "besan namkeen": "besan namkeen",
    "sev": "sev",
    "bhujia": "bhujia",
    "नमकीन": "नमकीन",
    "भुजिया": "भुजिया",
    "farsan": "farsan",
    "फरसाण": "फरसाण",
    "karasev": "karasev",
    "காராசேவ்": "காராசேவ்",
    "karappusa": "karappusa",
    "నంకీన్": "నంకీన్",
    "নিমকি": "নিমকি",
    "ನಮ್ಕೀನ್": "ನಮ್ಕೀನ್",
    "નમકીન": "નમકીન",
    "ਫਰਸਾਨ": "ਫਰਸਾਨ",
}

# State modifiers mapping
STATE_KEYWORDS: dict[str, str] = {
    # Cut / chopped / sliced
    "cut": "cut",
    "sliced": "sliced",
    "chopped": "chopped",
    "pieces": "cut",
    "kaata": "cut",
    "kata": "cut",
    "kaat": "cut",
    "tukde": "cut",
    "chirela": "cut",
    "kaplela": "cut",
    "काटा": "cut",
    "काट": "cut",
    "कापलेला": "cut",
    "चिरलेला": "cut",
    "कापलेले": "cut",
    "कापली": "cut",
    "vettiya": "cut",
    "narukkiya": "cut",
    "வெட்டிய": "cut",
    "நறுக்கிய": "cut",
    "kosina": "cut",
    "mukkalu": "cut",
    "కోసిన": "cut",
    "ముక్కలు": "cut",
    "কাটা": "cut",
    "টুকরো": "cut",
    "kattarisida": "cut",
    "ಕತ್ತರಿಸಿದ": "cut",
    "kapela": "cut",
    "કાપેલું": "cut",
    "કાપેલા": "cut",
    "katya": "cut",
    "katya hoya": "cut",
    "ਕੱਟਿਆ": "cut",
    # Washed
    "washed": "washed",
    "clean": "washed",
    "dhoya": "washed",
    "dho": "washed",
    "dhula": "washed",
    "dhutlela": "washed",
    "धोया": "washed",
    "धुतलेला": "washed",
    "kazhuviya": "washed",
    "கழுவிய": "washed",
    "kadigina": "washed",
    "కడిగిన": "washed",
    "ধোয়া": "washed",
    "toleda": "washed",
    "ತೊಳೆದ": "washed",
    "dhovelun": "washed",
    "ધોયેલું": "washed",
    "dhota": "washed",
    "ਧੋਤਾ": "washed",
    # Whole / Fresh
    "whole": "whole",
    "fresh whole": "whole",
    "sabut": "whole",
    "akkha": "whole",
    "muzhu": "whole",
    "fresh": "fresh",
    "taaza": "fresh",
    "साबुत": "whole",
    "ताज़ा": "fresh",
    "ताजा": "fresh",
    "अक्खा": "whole",
    "முழு": "whole",
    "తాజా": "fresh",
    "সবুজ": "fresh",
    "ತಾಜಾ": "fresh",
    "તાજું": "fresh",
    "ਤਾਜ਼ਾ": "fresh",
    # Cured / Dried
    "cured": "cured",
    "dried": "dried",
    "sukha": "dried",
    "sukhe": "dried",
    "shukno": "dried",
    "vaalela": "dried",
    "सूखा": "dried",
    "वाळलेला": "dried",
    "உலர்ந்த": "dried",
    "শুকনো": "dried",
    "ఎండిన": "dried",
    "ಒಣಗಿದ": "dried",
    "સૂકું": "dried",
    "ਸੁੱਕਾ": "dried",
    # Bruised
    "bruised": "bruised",
    "damaged": "damaged",
    "kharab": "damaged",
    "दबा हुआ": "bruised",
    "நசுங்கிய": "bruised",
    "పాడైన": "damaged",
    "ಜಜ್ಜಿದ": "bruised",
}


def _match_keyword(kw: str, text: str) -> bool:
    """Matches keyword in text respecting Indic scripts and word boundaries."""
    # Non-ASCII Indic scripts (Devanagari, Tamil, Telugu, Bengali, Kannada, Gujarati, Gurmukhi)
    if any(ord(c) > 127 for c in kw):
        return kw in text
    # ASCII words match with boundary
    pattern = (
        r"(?:^|[\s,._\-!?:;()\[\]])" + re.escape(kw) + r"(?:[\s,._\-!?:;()\[\]]|$)"
    )
    return bool(re.search(pattern, text, re.IGNORECASE))


def deterministic_parse_query(text: str) -> ParsedQuery:
    """
    Rule-based deterministic keyword & token parser across 9 Indian languages.
    Used when LLM is unavailable or fails schema validation.
    Applies lower confidence scores for fallback provenance.
    """
    clean = text.lower().strip()
    query = ParsedQuery(parser_source="deterministic_fallback")
    conf = QueryConfidence()

    # 1. Commodity hint extraction
    sorted_commodity_keys = sorted(COMMODITY_KEYWORDS.keys(), key=len, reverse=True)
    for kw in sorted_commodity_keys:
        if _match_keyword(kw, clean):
            query.commodity_hint = COMMODITY_KEYWORDS[kw]
            conf.commodity_hint = 0.65
            break

    # 2. State modifier extraction
    sorted_state_keys = sorted(STATE_KEYWORDS.keys(), key=len, reverse=True)
    for kw in sorted_state_keys:
        if _match_keyword(kw, clean):
            query.state = STATE_KEYWORDS[kw]
            conf.state = 0.60
            break

    # 3. Hours since harvest/cutting extraction
    hours_match = None
    # 3.1 Days ago patterns
    if any(
        w in clean
        for w in [
            "do din pehle",
            "2 din pehle",
            "do din",
            "2 days ago",
            "2 divas aadhi",
            "2 दिवस आधी",
            "दो दिन पहले",
            "2 दिन पहले",
            "दो दिन",
            "दोन दिवस आधी",
            "2 naatkal munbu",
            "2 நாட்கள் முன்பு",
            "இரண்டு நாட்கள் முன்பு",
            "2 rojula kritham",
            "2 రోజుల క్రితం",
            "రెండు రోజుల క్రితం",
            "2 din aage",
            "2 দিন আগে",
            "দুই দিন আগে",
            "2 dina munche",
            "2 ದಿನ ಮುಂಚೆ",
            "ಎರಡು ದಿನ ಮುಂಚೆ",
            "2 divas pehla",
            "2 દિવસ પહેલા",
            "બે દિવસ પહેલા",
            "2 din pehla",
            "2 ਦਿਨ ਪਹਿਲਾਂ",
            "ਦੋ ਦਿਨ ਪਹਿਲਾਂ",
            "day before yesterday",
            "parso",
        ]
    ):
        hours_match = 48.0
    elif any(
        w in clean
        for w in [
            "ek din pehle",
            "1 din pehle",
            "1 day ago",
            "kal",
            "ek din",
            "1 divas",
            "1 naal",
            "1 roju",
            "1 dina",
            "1 ದಿನ",
            "1 দিন",
            "1 ਦਿਨ",
            "1 દિવસ",
            "एक दिन पहले",
            "1 दिन पहले",
        ]
    ):
        hours_match = 24.0
    elif any(
        w in clean for w in ["teen din", "3 din", "3 days ago", "3 दिन पहले", "तीन दिन"]
    ):
        hours_match = 72.0
    elif any(
        w in clean for w in ["char din", "4 din", "4 days ago", "4 दिन पहले", "चार दिन"]
    ):
        hours_match = 96.0

    if hours_match is None:
        day_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:din|days|day|divas|naatkal|naal|rojulu|roju|dina|divaso|દિન|ਦਿਨ|દિવસ|రోజులు|ದಿನ|দিন|நாட்கள்|दिवस|दिन)\s*(?:pehle|pehla|ago|aadhi|munbu|kritham|aage|munche|pahila|પહેલા|ਪਹਿਲਾਂ|முன்பு|క్రితం|आधी|ముంచె|আগে|पहले)",
            clean,
        )
        if day_match:
            hours_match = float(day_match.group(1)) * 24.0

    # 3.2 Direct hours patterns
    if hours_match is None:
        hr_search = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:hours|hour|hr|ghante|ghanta|gantalu|mani|dhar)\s*(?:pehle|ago|kritham|munbu)?",
            clean,
        )
        if hr_search:
            hours_match = float(hr_search.group(1))

    if hours_match is not None:
        query.hours_since = hours_match
        conf.hours_since = 0.65

    # 4. Quantity extraction
    qty_search = re.search(
        r"(\d+(?:\.\d+)?\s*(?:kg|kilo|kilos|g|gm|grams|ton|tonne|tonnes|quintal|quintals|bori|bags|crates|peti|packets|pkt|boxes|కెజి|కిలోలు|కిలో|கிலோ|কেজি|ಕೆಜಿ|કિલો|ਕਿਲੋ|किलो|टन|बोरी|गोणी|पॅकेट))",
        clean,
    )
    if qty_search:
        query.quantity = qty_search.group(1).strip()
        conf.quantity = 0.60
    # 5. Destination extraction
    # Target markets, transit corridors, or transport modes
    dest_matches = []
    dest_keywords = [
        "delhi",
        "mumbai",
        "bangalore",
        "kolkata",
        "chennai",
        "hyderabad",
        "pune",
        "ahmedabad",
        "surat",
        "nashik",
        "mysore",
        "vijayawada",
        "dubai",
        "mandi",
        "apmc",
        "bazaar",
        "bazar",
        "market",
        "supermarket",
        "retail",
        "export",
        "local market",
        "local supermarket",
        "truck",
        "lorry",
        "tempo",
        "railway",
        "flight",
    ]
    for dkw in dest_keywords:
        pattern = r"(?:\b|^)" + re.escape(dkw) + r"(?:\b|$)"
        if re.search(pattern, clean):
            dest_matches.append(dkw)

    # Transit action hints (bhejna, pathvaycha, anuppa, pampali, etc.)
    transit_action = any(
        act in clean
        for act in [
            "bhejna",
            "bhejo",
            "bhejna hai",
            "pathvaycha",
            "pathavne",
            "anuppa",
            "anuppanum",
            "pampali",
            "pathate hobe",
            "kaluhisabeku",
            "kalsabeku",
            "moklavana",
            "bhejna chahida",
        ]
    )

    if dest_matches:
        dest_str = " ".join(dest_matches)
        if transit_action and "truck" in clean and "truck" not in dest_str:
            dest_str = f"{dest_str} via truck"
        query.destination = dest_str
        conf.destination = 0.60
    elif transit_action:
        if "truck" in clean:
            query.destination = "truck transit"
        else:
            query.destination = "transit"
        conf.destination = 0.50

    # 6. Storage hint extraction
    storage_map: dict[str, str] = {
        "cold storage": "cold storage",
        "cold store": "cold store",
        "chiller": "chiller",
        "refrigerated": "refrigerated",
        "fridge": "fridge",
        "freezer": "freezer",
        "ambient pack": "ambient pack",
        "ambient": "ambient",
        "room temperature": "room temperature",
        "room temp": "room temp",
        "open air": "open air",
        "godown": "godown",
        "warehouse": "warehouse",
        "chaon": "shade",
        "shade": "shade",
        "dry shade": "dry shade",
        "dry place": "dry place",
        "mesh bag": "mesh bag",
        "khule me": "open air",
        "moisture barrier": "moisture barrier",
        # Indic scripts
        "কোল্ড স্টোরেজে": "cold storage",
        "কোল্ড স্টোরেজ": "cold storage",
        "कोल्ड स्टोरेज": "cold storage",
        "कोल्ड स्टोर": "cold storage",
        "ಕೋಲ್ಡ್ ಸ್ಟೋರೇಜ್": "cold storage",
        "కోల్డ్ స్టోరేజ్": "cold storage",
        "கோல்ட் ஸ்டோரேஜ்": "cold storage",
        "કોલ્ડ સ્ટોરેજ": "cold storage",
        "ਕੋਲਡ ਸਟੋਰੇਜ": "cold storage",
    }
    for skw, canonical_hint in storage_map.items():
        if _match_keyword(skw, clean):
            query.storage_hint = canonical_hint
            conf.storage_hint = 0.60
            break

    # 7. Target shelf life days extraction
    target_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:din|days|day|divas|naal|naatkal|rojulu|dina|రోజులు|రోజు|ದಿನಗಳು|ದಿನ|நாட்கள்|நாள்|দিন|ਦਿਨ|દિવસ|दिवस|दिन)\s*(?:me|chalna|shelf life|life|tikna|lasting|sathi|venum|undali|hobe|chahida|target|నిల్వ|ఉండాలి)?",
        clean,
    )
    if target_match and (
        "chalna" in clean
        or "shelf life" in clean
        or "tikna" in clean
        or "venum" in clean
        or "undali" in clean
        or "నిల్వ" in clean
        or "రోజులు" in clean
        or "hobe" in clean
        or "chahida" in clean
        or "target" in clean
        or "life" in clean
        or "required" in clean
    ):
        # Ensure it's not the same as hours_since
        td_val = float(target_match.group(1))
        if td_val != query.hours_since:
            query.target_days = td_val
            conf.target_days = 0.60
    elif "1 year" in clean:
        query.target_days = 365.0
        conf.target_days = 0.60
    elif "1 month" in clean:
        query.target_days = 30.0
        conf.target_days = 0.60

    query.confidence = conf
    return query


# ---------------------------------------------------------------------------
# High-Level Parse Orchestrator
# ---------------------------------------------------------------------------


def parse_query(
    text: str,
    client: LLMClient | None = None,
    db_session: Any | None = None,
) -> ParsedQuery:
    """
    Parses natural language and voice queries into a validated ParsedQuery object.

    Execution Flow:
    1. If LLM client is available, prompt the LLM under strictly bounded extraction instructions.
    2. Validate LLM response against Pydantic schema ParsedQuery.
    3. If LLM is unavailable, times out, or fails schema validation:
       Fall back to deterministic keyword parser and lower field confidence.
    4. Resolve commodity_hint against the Knowledge Base alias table using
       pgvector cosine similarity (matching is a retrieval problem, not an LLM task).
    5. Return the finalized ParsedQuery.
    """
    if not text or not text.strip():
        return ParsedQuery(parser_source="empty_input")

    query: ParsedQuery | None = None

    # Step 1 & 2: Attempt LLM extraction if client provided
    if client is not None:
        try:
            raw_response = client.generate(
                prompt=f'Extract user query: "{text}"',
                system_prompt=PARSER_SYSTEM_PROMPT,
                temperature=0.0,
            )
            # Find and parse JSON within response
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                # Validate against Pydantic schema
                query = ParsedQuery.model_validate(data)
                query.parser_source = "llm"
            else:
                logger.warning(
                    "LLM response did not contain a valid JSON block; falling back to deterministic parser."
                )
        except Exception as e:
            logger.warning(
                f"LLM parsing or validation failed ({e}); activating deterministic fallback."
            )
            query = None

    # Step 3: Deterministic fallback if query is not yet populated
    if query is None:
        query = deterministic_parse_query(text)

    # Step 4: Resolve commodity_hint against the alias table using pgvector cosine similarity
    if query.commodity_hint:
        res = resolve_commodity_hint(
            commodity_hint=query.commodity_hint,
            db_session=db_session,
            top_k=1,
            threshold=0.35,
        )
        if res:
            commodity_id, sim = res
            query.resolved_commodity_id = commodity_id
            # Set high confidence if retrieved successfully
            if query.confidence.commodity_hint < 0.5:
                query.confidence.commodity_hint = round(sim * 0.7, 2)

    return query
