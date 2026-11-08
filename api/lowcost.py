"""
Low-cost, no-plastic storage options for smallholders (zero-energy cool chamber,
wet gunny cover, ventilated crates, sorting, curing, clay-pot coolers …).

Data lives in kb/low_cost_storage.json. Every cost and shelf-life figure there carries a
source id; this module never computes or invents a number, it only filters and orders.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

KB_FILE = Path(__file__).resolve().parents[1] / "kb" / "low_cost_storage.json"
TEXT_LANGS = ("en", "hi", "mr")


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    if not KB_FILE.exists():
        return {"options": [], "sources": []}
    try:
        return json.loads(KB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"options": [], "sources": []}


def reload() -> None:
    _load.cache_clear()


def _lang_key(lang: str) -> str:
    base = (lang or "en").lower().split("-")[0]
    if lang == "hi-en":
        return "en"
    return base if base in TEXT_LANGS else "en"


def _pick(d: Optional[Dict[str, str]], lang: str) -> str:
    if not isinstance(d, dict):
        return ""
    return d.get(_lang_key(lang)) or d.get("en") or next(iter(d.values()), "")


def _source_map() -> Dict[str, Dict[str, Any]]:
    return {str(s["id"]): s for s in _load().get("sources", []) if isinstance(s, dict) and s.get("id")}


def _range(v: Any) -> Optional[List[float]]:
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return [float(v[0]), float(v[1])]
    return None


def options_for(commodity_id: str, lang: str = "hi-IN", physical_state: Optional[str] = None) -> List[Dict[str, Any]]:
    """Options that apply to this commodity, best shelf-life gain first.

    Cut produce gets nothing here: no low-cost trick makes cut produce safe at ambient
    temperature (the engine's refusal guidance covers that case).
    """
    if physical_state == "cut":
        return []
    sources = _source_map()
    out: List[Dict[str, Any]] = []
    for opt in _load().get("options", []):
        if commodity_id not in (opt.get("applies_to") or []):
            continue
        benefit = next(
            (b for b in (opt.get("benefit") or []) if b.get("commodity_id") == commodity_id), None
        )
        cost = opt.get("cost_inr") or {}
        src_id = (benefit or {}).get("src") or cost.get("src")
        src = sources.get(src_id, {})
        out.append(
            {
                "id": opt.get("id"),
                "name": _pick(opt.get("names"), lang),
                "how_to": _pick(opt.get("how_to"), lang),
                "cost_low": cost.get("low"),
                "cost_high": cost.get("high"),
                "cost_basis": cost.get("basis"),
                "ambient_days": _range((benefit or {}).get("ambient_days")),
                "with_option_days": _range((benefit or {}).get("with_option_days")),
                "loss_reduction_pct": _range((benefit or {}).get("loss_reduction_pct")),
                "note": (benefit or {}).get("note"),
                "requires": (opt.get("works_when") or {}).get("requires") or [],
                "source_id": src_id,
                "source": src.get("citation") or src_id,
                "source_url": src.get("url"),
                "text_lang": _lang_key(lang),
            }
        )

    def rank(o: Dict[str, Any]) -> tuple:
        # 1) options with a measured before/after pair, by days gained;
        # 2) options with only an "after" figure; 3) options without day figures.
        w, a = o["with_option_days"], o["ambient_days"]
        if w and a:
            return (2, w[0] - a[0])
        if w:
            return (1, w[0])
        return (0, 0.0)

    out.sort(key=rank, reverse=True)
    return out


def spoken_line(commodity_id: str, lang: str, physical_state: Optional[str] = None) -> Optional[str]:
    """One spoken sentence about the single best option, or None.

    Only for languages whose option names/instructions exist in the data (hi, mr, en, Hinglish);
    other languages see the options on screen instead of hearing a mixed-language sentence.
    """
    base = (lang or "").split("-")[0]
    if lang != "hi-en" and base not in TEXT_LANGS:
        return None
    opts = [o for o in options_for(commodity_id, lang, physical_state) if o["with_option_days"]]
    if not opts:
        return None
    from api.voice.texts import t  # local import keeps this module dependency-light

    best = opts[0]
    # Name + days + cost only; the step-by-step how-to is shown on screen (too long to speak).
    parts = [t("lowcost_intro", lang), f"{best['name']},"]
    a, b = best["with_option_days"]
    if int(a) == int(b):
        parts.append(t("lowcost_days_one", lang, a=int(a)))
    else:
        parts.append(t("lowcost_days", lang, a=int(a), b=int(b)))
    low, high = best["cost_low"], best["cost_high"]
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        if high == 0:
            parts.append(t("lowcost_free", lang))
        elif low == high:
            parts.append(t("lowcost_cost_one", lang, low=int(low)))
        else:
            parts.append(t("lowcost_cost", lang, low=int(low), high=int(high)))
    return " ".join(p.strip() for p in parts if p and p.strip())
