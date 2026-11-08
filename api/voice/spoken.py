"""
Spoken-form normaliser for Gnani Timbre.

Timbre's docs ask for numbers, dates and currency to be written as spoken words.
This module rewrites digits, ₹ amounts, decimals, % and film-gauge jargon
("20u BOPP / 40u CPP") into speakable text for Hindi, Marathi and English.
"""

from __future__ import annotations

import re

_HI_0_99 = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस "
    "पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस "
    "सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ "
    "इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर "
    "पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी "
    "अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()

_MR_0_99 = (
    "शून्य एक दोन तीन चार पाच सहा सात आठ नऊ दहा अकरा बारा तेरा चौदा पंधरा सोळा सतरा अठरा एकोणीस "
    "वीस एकवीस बावीस तेवीस चोवीस पंचवीस सव्वीस सत्तावीस अठ्ठावीस एकोणतीस तीस एकतीस बत्तीस तेहतीस "
    "चौतीस पस्तीस छत्तीस सदतीस अडतीस एकोणचाळीस चाळीस एक्केचाळीस बेचाळीस त्रेचाळीस चव्वेचाळीस "
    "पंचेचाळीस सेहेचाळीस सत्तेचाळीस अठ्ठेचाळीस एकोणपन्नास पन्नास एक्कावन्न बावन्न त्रेपन्न चोपन्न "
    "पंचावन्न छप्पन्न सत्तावन्न अठ्ठावन्न एकोणसाठ साठ एकसष्ठ बासष्ठ त्रेसष्ठ चौसष्ठ पासष्ठ सहासष्ठ "
    "सदुसष्ठ अडुसष्ठ एकोणसत्तर सत्तर एकाहत्तर बाहत्तर त्र्याहत्तर चौऱ्याहत्तर पंच्याहत्तर शहात्तर "
    "सत्याहत्तर अठ्ठ्याहत्तर एकोणऐंशी ऐंशी एक्याऐंशी ब्याऐंशी त्र्याऐंशी चौऱ्याऐंशी पंच्याऐंशी "
    "शहाऐंशी सत्याऐंशी अठ्ठ्याऐंशी एकोणनव्वद नव्वद एक्याण्णव ब्याण्णव त्र्याण्णव चौऱ्याण्णव पंच्याण्णव "
    "शहाण्णव सत्याण्णव अठ्ठ्याण्णव नव्व्याण्णव"
).split()

_EN_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

_WORDS = {
    "hi": {"hundred": "सौ", "thousand": "हज़ार", "lakh": "लाख", "point": "दशमलव", "rupee": "रुपये", "paise": "पैसे", "percent": "प्रतिशत", "and": "और", "micron": "माइक्रोन"},
    "mr": {"hundred": "शे", "thousand": "हजार", "lakh": "लाख", "point": "पूर्णांक", "rupee": "रुपये", "paise": "पैसे", "percent": "टक्के", "and": "आणि", "micron": "मायक्रॉन"},
    "en": {"hundred": "hundred", "thousand": "thousand", "lakh": "lakh", "point": "point", "rupee": "rupees", "paise": "paise", "percent": "percent", "and": "and", "micron": "micron"},
}


def _lang(lang: str) -> str:
    l = (lang or "en").lower()
    if l.startswith("mr"):
        return "mr"
    if l.startswith("hi") and not l.endswith("en"):
        return "hi"
    if l == "hi-en":
        return "en"  # Hinglish is spoken in Latin-script words; English numerals read naturally.
    return "en"


def _en_below_100(n: int) -> str:
    if n < 20:
        return _EN_ONES[n]
    tens, ones = divmod(n, 10)
    return _EN_TENS[tens] + ("" if ones == 0 else "-" + _EN_ONES[ones])


def int_to_words(n: int, lang: str = "hi") -> str:
    """Indian-system integer to words (supports up to 99,99,99,999)."""
    lg = _lang(lang)
    if n < 0:
        return ("minus " if lg == "en" else "ऋण ") + int_to_words(-n, lang)
    if lg == "en":
        below = _en_below_100
    else:
        table = _HI_0_99 if lg == "hi" else _MR_0_99
        below = lambda k: table[k]  # noqa: E731
    w = _WORDS[lg]
    if n < 100:
        return below(n)
    parts: list[str] = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    hundred, rest = divmod(n, 100)
    if crore:
        parts.append(f"{int_to_words(crore, lang)} {'crore' if lg == 'en' else 'करोड़'}")
    if lakh:
        parts.append(f"{below(lakh)} {w['lakh']}")
    if thousand:
        parts.append(f"{below(thousand)} {w['thousand']}")
    if hundred:
        if lg == "mr":
            parts.append(f"{below(hundred)}शे" if hundred > 1 else "शंभर")
        else:
            parts.append(f"{below(hundred)} {w['hundred']}")
    if rest:
        parts.append(below(rest))
    return " ".join(parts)


def number_to_words(token: str, lang: str = "hi") -> str:
    token = token.replace(",", "")
    if "." in token:
        whole, frac = token.split(".", 1)
        frac = frac.rstrip("0")
        if not frac:
            return int_to_words(int(whole or 0), lang)
        lg = _lang(lang)
        digits = " ".join(int_to_words(int(d), lang) for d in frac)
        return f"{int_to_words(int(whole or 0), lang)} {_WORDS[lg]['point']} {digits}"
    return int_to_words(int(token), lang)


_RUPEE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*(\d+(?:,\d{3})*(?:\.\d+)?)", re.IGNORECASE)
_GAUGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:u|µm|μm|micron)\b", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def _rupees(amount: str, lang: str) -> str:
    lg = _lang(lang)
    w = _WORDS[lg]
    amount = amount.replace(",", "")
    rupees, _, paise = amount.partition(".")
    r = int(rupees or 0)
    p = int((paise + "00")[:2]) if paise else 0
    if r and p:
        return f"{int_to_words(r, lang)} {w['rupee']} {int_to_words(p, lang)} {w['paise']}"
    if p and not r:
        return f"{int_to_words(p, lang)} {w['paise']}"
    return f"{int_to_words(r, lang)} {w['rupee']}"


# Rupee / micron words for languages without a number-word table yet: digits are kept
# (Timbre reads them in-language) and only symbols are spelled out.
_OTHER_WORDS = {
    "ta": ("ரூபாய்", "மைக்ரான்"), "te": ("రూపాయలు", "మైక్రాన్"), "kn": ("ರೂಪಾಯಿ", "ಮೈಕ್ರಾನ್"),
    "gu": ("રૂપિયા", "માઇક્રોન"), "pa": ("ਰੁਪਏ", "ਮਾਈਕ੍ਰੋਨ"), "bn": ("টাকা", "মাইক্রন"),
}


def to_spoken(text: str, lang: str = "hi-IN") -> str:
    """Rewrite a display string into a TTS-friendly spoken string."""
    if not text:
        return ""
    base = (lang or "").lower().split("-")[0]
    if base in _OTHER_WORDS and lang != "hi-en":
        rupee, micron = _OTHER_WORDS[base]
        out = _RUPEE_RE.sub(lambda m: f"{m.group(1)} {rupee}", text)
        out = _GAUGE_RE.sub(lambda m: f"{m.group(1)} {micron}", out)
        return re.sub(r"\s{2,}", " ", out.replace(" / ", ", ").replace("/", ", ")).strip()
    lg = _lang(lang)
    w = _WORDS[lg]
    out = text
    out = _RUPEE_RE.sub(lambda m: _rupees(m.group(1), lang), out)
    out = _GAUGE_RE.sub(lambda m: f"{number_to_words(m.group(1), lang)} {w['micron']}", out)
    out = _PCT_RE.sub(lambda m: f"{number_to_words(m.group(1), lang)} {w['percent']}", out)
    out = _NUM_RE.sub(lambda m: number_to_words(m.group(0), lang), out)
    out = out.replace(" / ", ", ").replace("/", ", ")
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def round_days_for_speech(days: float | None) -> int | None:
    """Conservative whole-day figure for speech (never round shelf life up)."""
    if days is None:
        return None
    try:
        d = float(days)
    except (TypeError, ValueError):
        return None
    if d != d or d < 0:  # NaN / negative
        return None
    return int(d)
