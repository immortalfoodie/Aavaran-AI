"""
Mandi (APMC) prices for "sell today or store?".

Source: Agmarknet daily prices published on data.gov.in
("Current Daily Price of Various Commodities from Various Markets (Mandi)").
Prices are ₹ per quintal. Set DATA_GOV_IN_API_KEY on the server (free key from data.gov.in).

Aavaran does NOT forecast prices. It reports what the mandi reported, and combines it
with the engine's shelf life to say how long holding is even an option.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

RESOURCE_ID = os.environ.get("DATA_GOV_IN_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
CACHE_TTL_S = 30 * 60
SELL_NOW_BELOW_DAYS = 3.0  # below this, holding is not a real option

# Our commodity ids -> Agmarknet commodity spellings
AGMARK_NAMES: Dict[str, str] = {
    "veg.onion.allium_cepa": "Onion",
    "veg.tomato.solanum_lycopersicum": "Tomato",
    "veg.potato.solanum_tuberosum": "Potato",
    "fruit.banana.musa_acuminata": "Banana",
    "fruit.mango.mangifera_indica": "Mango",
    "veg.okra.abelmoschus_esculentus": "Bhindi(Ladies Finger)",
    "veg.spinach.spinacia_oleracea": "Spinach",
    "veg.green_chilli.capsicum_annuum": "Green Chilli",
    "fruit.guava.psidium_guajava": "Guava",
    "veg.cauliflower.brassica_oleracea_botrytis": "Cauliflower",
    "veg.cabbage.brassica_oleracea_capitata": "Cabbage",
    "fruit.grape.vitis_vinifera": "Grapes",
    "fruit.pomegranate.punica_granatum": "Pomegranate",
    "veg.brinjal.solanum_melongena": "Brinjal",
}


# Districts offered in the app's district picker -> Agmarknet state names, so we can widen
# the search when the farmer's own district has not reported today (common: the feed only
# carries the current day and a few hundred markets).
DISTRICT_STATE: Dict[str, str] = {
    "nashik": "Maharashtra", "pune": "Maharashtra", "ahmednagar": "Maharashtra", "nagpur": "Maharashtra",
    "indore": "Madhya Pradesh", "agra": "Uttar Pradesh", "kolar": "Karnataka",
}


def local_name(commodity_id: str, lang: str, default: str) -> str:
    """Commodity name in the user's language from the KB (falls back to the Agmarknet spelling)."""
    import json
    from pathlib import Path

    base = "hi" if lang == "hi-en" else lang.split("-")[0]
    for path in (Path(__file__).resolve().parents[1] / "kb" / "commodities").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("commodity_id") == commodity_id:
            names = (data.get("names") or {}).get(base) or []
            if lang == "hi-en":
                names = [n for n in names if n.isascii()] or names
            return names[0] if names else default
    return default


class MarketUnavailable(Exception):
    def __init__(self, message: str, code: str = "MARKET_UNAVAILABLE") -> None:
        super().__init__(message)
        self.code = code


_cache: Dict[str, tuple] = {}
_lock = threading.Lock()
_transport: Optional[httpx.BaseTransport] = None


def set_transport(transport: Optional[httpx.BaseTransport]) -> None:
    """Tests inject an httpx.MockTransport here."""
    global _transport
    _transport = transport
    _cache.clear()


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_date(s: Any) -> Optional[str]:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(s), fmt).date().isoformat()
        except (TypeError, ValueError):
            continue
    return None


def fetch_records(commodity: str, state: Optional[str], district: Optional[str], market_name: Optional[str]) -> List[Dict[str, Any]]:
    key = os.environ.get("DATA_GOV_IN_API_KEY", "")
    if not key:
        raise MarketUnavailable("Mandi prices are not configured on this server (DATA_GOV_IN_API_KEY).", "NOT_CONFIGURED")
    params: Dict[str, Any] = {"api-key": key, "format": "json", "limit": 200, "filters[commodity]": commodity}
    if state:
        params["filters[state]"] = state
    if district:
        params["filters[district]"] = district
    if market_name:
        params["filters[market]"] = market_name
    cache_key = repr(sorted((k, v) for k, v in params.items() if k != "api-key"))
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]
    try:
        with httpx.Client(transport=_transport, timeout=45.0) as client:
            # data.gov.in stalls on httpx's default User-Agent; any explicit UA is served promptly.
            resp = client.get(
                API_URL,
                params=params,
                headers={"User-Agent": "Aavaran-AI/1.0 (mandi price lookup)", "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise MarketUnavailable(f"Could not reach data.gov.in: {exc}", "NETWORK_ERROR") from exc
    if resp.status_code != 200:
        raise MarketUnavailable(f"data.gov.in returned HTTP {resp.status_code}", "UPSTREAM_ERROR")
    records = (resp.json() or {}).get("records") or []
    with _lock:
        _cache[cache_key] = (time.time(), records)
    return records


def price_insight(
    commodity_id: str,
    state: Optional[str] = None,
    district: Optional[str] = None,
    market_name: Optional[str] = None,
    shelf_life_days: Optional[float] = None,
    lang: str = "hi-IN",
) -> Dict[str, Any]:
    commodity = AGMARK_NAMES.get(commodity_id)
    if not commodity:
        raise MarketUnavailable("Mandi prices are not tracked for this item.", "UNSUPPORTED_COMMODITY")

    # Widen step by step: market/district -> state -> all India.
    if not state and district:
        state = DISTRICT_STATE.get(district.strip().lower())
    attempts = []
    if market_name or district:
        attempts.append(("district", state, district, market_name))
    if state:
        attempts.append(("state", state, None, None))
    attempts.append(("india", None, None, None))
    records: List[Dict[str, Any]] = []
    scope = "india"
    for scope, st, dist, mkt in attempts:
        records = fetch_records(commodity, st, dist, mkt)
        if records:
            break

    rows = []
    for r in records:
        modal = _to_float(r.get("modal_price"))
        if modal is None or modal <= 0:
            continue
        rows.append(
            {
                "state": r.get("state"),
                "district": r.get("district"),
                "market": str(r.get("market") or "").strip(),
                "variety": r.get("variety"),
                "date": _parse_date(r.get("arrival_date")) or r.get("arrival_date"),
                "min_price": _to_float(r.get("min_price")),
                "max_price": _to_float(r.get("max_price")),
                "modal_price": modal,
            }
        )
    # Use only the most recent reporting day, then the MEDIAN market as the headline price:
    # picking the highest-priced mandi would bias the advice toward "hold".
    if rows:
        newest = max(r["date"] or "" for r in rows)
        rows = [r for r in rows if (r["date"] or "") == newest]
    rows.sort(key=lambda x: float(x["modal_price"] or 0.0), reverse=True)
    latest = rows[len(rows) // 2] if rows else None
    advice: Optional[str] = None
    hold_days: Optional[int] = None
    if shelf_life_days is not None:
        hold_days = int(shelf_life_days)
        advice = "sell_now" if shelf_life_days < SELL_NOW_BELOW_DAYS else "can_hold"

    spoken = None
    if latest:
        from api.voice.dialogue import normalize_lang
        from api.voice.texts import t

        sl = normalize_lang(lang)
        parts = [t("price_today", sl, market=latest["market"], comm=local_name(commodity_id, sl, commodity),
                   price=int(latest["modal_price"]))]
        if advice == "sell_now":
            parts.append(t("sell_now", sl))
        elif advice == "can_hold":
            parts.append(t("can_hold", sl, days=hold_days))
        spoken = " ".join(parts)

    return {
        "commodity_id": commodity_id,
        "agmarknet_commodity": commodity,
        "unit": "INR per quintal",
        "scope": scope,
        "latest": latest,
        "markets": rows[:20],
        "advice": advice,
        "hold_days": hold_days,
        "spoken": spoken,
        "source": "Agmarknet, Government of India (data.gov.in)",
        "note": "Today's prices as reported by mandis (the feed has no history); Aavaran does not forecast prices.",
    }
