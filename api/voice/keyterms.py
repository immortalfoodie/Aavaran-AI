"""
Builds the Prisma v3.0 `keyterms` context list from the knowledge base.

Every commodity name in every language (aloo, कांदा, bhindi, फरसाण ...) plus the
mandi / storage vocabulary that Saarthi's slot extractor listens for. Biasing
the recogniser toward these words is what makes short, noisy farmer utterances
land on the right commodity.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

KB_COMMODITY_DIR = Path(__file__).resolve().parents[2] / "kb" / "commodities"
MAX_KEYTERMS = 200

DOMAIN_VOCAB = [
    # storage / handling
    "shed", "cold storage", "godown", "barf", "बर्फ", "शेड", "कोल्ड स्टोरेज", "गोदाम",
    "crate", "क्रेट", "thaili", "थैली", "पिशवी", "bori", "बोरी", "पोते", "mandi", "मंडी",
    # state
    "kaata", "कटा", "कापलेले", "dhoya", "धोया", "sabut", "साबुत", "kharab", "खराब", "दबा",
    # time
    "aaj", "आज", "kal", "कल", "काल", "parso", "परसों", "din", "दिन", "दिवस", "ghante", "घंटे",
    # business
    "gram", "ग्राम", "packet", "पैकेट", "pouch", "पाउच", "shelf life", "महीने", "mahine",
]


@lru_cache(maxsize=1)
def build_keyterms() -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        t = (term or "").strip()
        if not t or "." in t or "_" in t or len(t) > 40:
            return  # skip internal ids like veg.potato.solanum_tuberosum
        key = t.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(t)

    if KB_COMMODITY_DIR.exists():
        for path in sorted(KB_COMMODITY_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            names = data.get("names") or {}
            # Prioritise the languages Saarthi speaks.
            for lang in ("hi", "mr", "en"):
                for name in names.get(lang, []):
                    add(name)
    for word in DOMAIN_VOCAB:
        add(word)
    return tuple(terms[:MAX_KEYTERMS])
