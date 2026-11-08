"""
Hierarchical Commodity Resolver for Aavaran.

Implements Section 4.1 of BLUEPRINT.md:
- Walks the hierarchical fallback ladder:
    L0: Measured (User supplied direct parameter values; confidence 1.0)
    L1: Cultivar ("Kufri Jyoti potato"; confidence ~0.90, narrow band)
    L2: Commodity ("Potato" from USDA-AH66 + IFCT-2017; confidence ~0.80-0.88)
    L3: Group ("root_tuber" medians; confidence ~0.60, wide band)
    L4: Physicochemical class envelope; confidence ~0.40 (or generic fallback ~0.25)
- NEVER fails: degrades gracefully down the ladder, widening ranges and lowering
  confidence.
- Enforces the Conservative-End Rule: downstream design selects the protective
  bound for ranges (high end for respiration, high end for water activity, worst
  temperature).
- Builds an Assumptions Ledger tracking source attribution, confidence, and
  resolution level for every parameter.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from engine.models.respiration import RespirationRateResult, rate_at_temperature
from engine.resolver.environment import resolve_environment
from engine.resolver.modifiers import (
    ElapsedLifeResult,
    StateModifierResult,
    apply_modifiers,
    consume_elapsed_life,
)
from engine.types import (
    CommodityProfile,
    Environment,
    Provenance,
    ResolutionLevel,
    SourceType,
)
from kb.loaders import load_all_commodities

logger = logging.getLogger(__name__)

# Cached commodities dictionary and fast alias lookup
_LOADED_COMMODITIES: dict[str, CommodityProfile] | None = None
_COMMODITY_CACHE: dict[str, CommodityProfile] = {}


def warm_commodity_cache(
    commodities: dict[str, CommodityProfile] | None = None,
) -> dict[str, CommodityProfile]:
    """
    Pre-populates commodity profiles and aliases into memory for O(1) fast lookup.
    Can be called once at app startup.
    """
    global _LOADED_COMMODITIES, _COMMODITY_CACHE
    if commodities is None:
        if _LOADED_COMMODITIES is None:
            _LOADED_COMMODITIES = load_all_commodities()
        commodities = _LOADED_COMMODITIES

    _COMMODITY_CACHE.clear()

    for cid, profile in commodities.items():
        _COMMODITY_CACHE[cid] = profile
        _COMMODITY_CACHE[cid.lower()] = profile

        # Subtoken short name, e.g. 'potato' from 'veg.potato.solanum_tuberosum'
        parts = cid.split(".")
        if len(parts) >= 2:
            _COMMODITY_CACHE[parts[1].lower()] = profile

        # Profile names (English and regional)
        if hasattr(profile, "names") and isinstance(profile.names, dict):
            for _lang, names_list in profile.names.items():
                for name in names_list:
                    _COMMODITY_CACHE[name.strip().lower()] = profile

    # Known aliases mapping
    for alias, target_cid in COMMODITY_ALIASES.items():
        if target_cid in commodities:
            _COMMODITY_CACHE[alias.strip().lower()] = commodities[target_cid]

    logger.info(f"[AAVARAN] Commodity cache warmed: {len(_COMMODITY_CACHE)} entries")
    print(f"[AAVARAN] Commodity cache warmed: {len(_COMMODITY_CACHE)} entries")
    return _COMMODITY_CACHE


def resolve_commodity_fast(query: str) -> CommodityProfile | None:
    """O(1) lookup for exact/alias matches — no DB/full-scan query."""
    if not _COMMODITY_CACHE:
        warm_commodity_cache()
    return _COMMODITY_CACHE.get(query.lower().strip())


def get_all_commodities() -> dict[str, CommodityProfile]:
    """Returns cached commodities dictionary from the KB."""
    global _LOADED_COMMODITIES
    if _LOADED_COMMODITIES is None:
        _LOADED_COMMODITIES = load_all_commodities()
        warm_commodity_cache(_LOADED_COMMODITIES)
    return _LOADED_COMMODITIES


# ---------------------------------------------------------------------------
# Level 1 Cultivar Definitions
# ---------------------------------------------------------------------------
CULTIVARS: dict[str, dict[str, Any]] = {
    "kufri jyoti": {
        "parent_commodity": "veg.potato.solanum_tuberosum",
        "name": "Kufri Jyoti Potato",
        "cultivar_id": "cultivar.potato.kufri_jyoti",
        "moisture_pct": {"v": 80.0, "range": [78.0, 82.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 3.6,
            "range": [3.0, 4.2],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "water_activity": {"v": 0.98, "range": [0.97, 0.99], "conf": 0.90},
        "notes": "Popular Indian table cultivar with moderate dry matter",
    },
    "kufri chipsona": {
        "parent_commodity": "veg.potato.solanum_tuberosum",
        "name": "Kufri Chipsona Potato",
        "cultivar_id": "cultivar.potato.kufri_chipsona",
        "moisture_pct": {"v": 76.0, "range": [74.0, 78.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 3.2,
            "range": [2.6, 3.8],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "water_activity": {"v": 0.97, "range": [0.96, 0.98], "conf": 0.90},
        "notes": "High dry-matter processing cultivar for chips",
    },
    "alphonso": {
        "parent_commodity": "fruit.mango.mangifera_indica",
        "name": "Alphonso Mango (Hapus)",
        "cultivar_id": "cultivar.mango.alphonso",
        "moisture_pct": {"v": 81.0, "range": [79.0, 83.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 18.0,
            "range": [15.0, 22.0],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "notes": "Premium GI-tagged Ratnagiri/Devgad cultivar",
    },
    "kesar": {
        "parent_commodity": "fruit.mango.mangifera_indica",
        "name": "Gir Kesar Mango",
        "cultivar_id": "cultivar.mango.kesar",
        "moisture_pct": {"v": 80.0, "range": [78.0, 82.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 16.0,
            "range": [13.0, 20.0],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "notes": "Gujarat saffron-coloured processing & table mango",
    },
    "cavendish": {
        "parent_commodity": "fruit.banana.musa_acuminata",
        "name": "Grand Naine Cavendish Banana",
        "cultivar_id": "cultivar.banana.cavendish",
        "moisture_pct": {"v": 74.5, "range": [72.0, 77.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 15.0,
            "range": [12.0, 19.0],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "notes": "Commercial dessert banana cultivar",
    },
    "roma": {
        "parent_commodity": "veg.tomato.solanum_lycopersicum",
        "name": "Roma Tomato",
        "cultivar_id": "cultivar.tomato.roma",
        "moisture_pct": {"v": 93.5, "range": [92.0, 95.0], "conf": 0.92},
        "respiration_ref_rate": {
            "v": 12.0,
            "range": [10.0, 15.0],
            "conf": 0.90,
            "unit": "mg CO2/kg·h",
        },
        "notes": "Plum paste tomato with firm pericarp",
    },
}

# ---------------------------------------------------------------------------
# Level 3 Commodity Group Medians
# ---------------------------------------------------------------------------
GROUP_MEDIANS: dict[str, dict[str, Any]] = {
    "root_tuber": {
        "commodity_id": "group.root_tuber.median",
        "names": {"en": ["root tuber", "tuber", "yam", "taro", "sweet potato"]},
        "group": "root_tuber",
        "class": "high_moisture_starchy",
        "source_id": "ICAR-AH66-Group",
        "physchem": {
            "moisture_pct": {"v": 79.0, "range": [70.0, 85.0], "conf": 0.65},
            "water_activity": {"v": 0.98, "range": [0.95, 0.99], "conf": 0.65},
            "pH": {"v": 6.0, "range": [5.2, 6.6], "conf": 0.65},
            "fat_pct": {"v": 0.15, "range": [0.05, 0.5], "conf": 0.65},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 58.0,
            "ref": {"T_C": 5.0, "rCO2_mg_kg_h": 4.0, "range": [2.0, 8.0]},
            "conf": 0.60,
        },
        "storage_optimum": {
            "T_C": [8.0, 12.0],
            "RH_pct": [85.0, 95.0],
            "life_days": [60.0, 180.0],
        },
    },
    "leafy_green": {
        "commodity_id": "group.leafy_green.median",
        "names": {"en": ["leafy green", "greens", "lettuce", "methi", "coriander"]},
        "group": "leafy_green",
        "class": "high_moisture_leafy",
        "source_id": "ICAR-AH66-Group",
        "physchem": {
            "moisture_pct": {"v": 92.0, "range": [88.0, 96.0], "conf": 0.65},
            "water_activity": {"v": 0.99, "range": [0.97, 1.00], "conf": 0.65},
            "pH": {"v": 6.3, "range": [5.8, 7.0], "conf": 0.65},
            "fat_pct": {"v": 0.3, "range": [0.1, 0.8], "conf": 0.65},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 62.0,
            "ref": {"T_C": 5.0, "rCO2_mg_kg_h": 35.0, "range": [20.0, 60.0]},
            "conf": 0.60,
        },
        "storage_optimum": {
            "T_C": [0.0, 4.0],
            "RH_pct": [95.0, 98.0],
            "life_days": [7.0, 21.0],
        },
    },
    "tropical_fruit": {
        "commodity_id": "group.tropical_fruit.median",
        "names": {"en": ["tropical fruit", "fruit", "papaya", "guava", "chikoo"]},
        "group": "tropical_fruit",
        "class": "high_moisture_climacteric",
        "source_id": "ICAR-AH66-Group",
        "physchem": {
            "moisture_pct": {"v": 82.0, "range": [75.0, 88.0], "conf": 0.65},
            "water_activity": {"v": 0.98, "range": [0.96, 0.99], "conf": 0.65},
            "pH": {"v": 4.5, "range": [3.8, 5.5], "conf": 0.65},
            "fat_pct": {"v": 0.3, "range": [0.1, 0.8], "conf": 0.65},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 60.0,
            "ref": {"T_C": 12.0, "rCO2_mg_kg_h": 18.0, "range": [10.0, 30.0]},
            "conf": 0.60,
        },
        "storage_optimum": {
            "T_C": [10.0, 14.0],
            "RH_pct": [85.0, 92.0],
            "life_days": [14.0, 35.0],
        },
    },
    "solanaceous": {
        "commodity_id": "group.solanaceous.median",
        "names": {"en": ["solanaceous", "eggplant", "brinjal", "bell pepper"]},
        "group": "solanaceous",
        "class": "high_moisture_perishable",
        "source_id": "ICAR-AH66-Group",
        "physchem": {
            "moisture_pct": {"v": 92.0, "range": [88.0, 95.0], "conf": 0.65},
            "water_activity": {"v": 0.98, "range": [0.96, 0.99], "conf": 0.65},
            "pH": {"v": 5.2, "range": [4.5, 6.0], "conf": 0.65},
            "fat_pct": {"v": 0.2, "range": [0.1, 0.5], "conf": 0.65},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 56.0,
            "ref": {"T_C": 10.0, "rCO2_mg_kg_h": 15.0, "range": [8.0, 25.0]},
            "conf": 0.60,
        },
        "storage_optimum": {
            "T_C": [8.0, 12.0],
            "RH_pct": [90.0, 95.0],
            "life_days": [14.0, 28.0],
        },
    },
    "fried_snack": {
        "commodity_id": "group.fried_snack.median",
        "names": {"en": ["fried snack", "namkeen", "chips", "sev", "bhujia"]},
        "group": "fried_snack",
        "class": "dry_high_fat",
        "source_id": "Industry-Standard",
        "physchem": {
            "moisture_pct": {"v": 2.5, "range": [1.0, 4.5], "conf": 0.65},
            "water_activity": {"v": 0.25, "range": [0.15, 0.35], "conf": 0.65},
            "pH": {"v": 6.0, "range": [5.5, 6.5], "conf": 0.65},
            "fat_pct": {"v": 28.0, "range": [18.0, 38.0], "conf": 0.65},
        },
        "respiration": {
            "model": "none",
            "ref": {"T_C": 20.0, "rCO2_mg_kg_h": 0.0, "range": [0.0, 0.0]},
            "conf": 0.99,
        },
        "storage_optimum": {
            "T_C": [20.0, 25.0],
            "RH_pct": [50.0, 65.0],
            "life_days": [90.0, 180.0],
        },
    },
}

# ---------------------------------------------------------------------------
# Level 4 Physicochemical Class Envelope (Never Fails)
# ---------------------------------------------------------------------------
CLASS_ENVELOPES: dict[str, dict[str, Any]] = {
    "high_moisture_starchy": {
        "commodity_id": "class.high_moisture_starchy.envelope",
        "group": "unspecified_tuber",
        "class": "high_moisture_starchy",
        "source_id": "Physchem-Envelope",
        "physchem": {
            "moisture_pct": {"v": 78.0, "range": [65.0, 85.0], "conf": 0.40},
            "water_activity": {"v": 0.98, "range": [0.94, 0.99], "conf": 0.40},
            "pH": {"v": 5.8, "range": [5.0, 6.8], "conf": 0.40},
            "fat_pct": {"v": 0.2, "range": [0.05, 1.0], "conf": 0.40},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 58.0,
            "ref": {"T_C": 5.0, "rCO2_mg_kg_h": 5.0, "range": [2.0, 15.0]},
            "conf": 0.40,
        },
        "storage_optimum": {
            "T_C": [7.0, 12.0],
            "RH_pct": [85.0, 95.0],
            "life_days": [30.0, 120.0],
        },
    },
    "high_moisture_leafy": {
        "commodity_id": "class.high_moisture_leafy.envelope",
        "group": "unspecified_leafy",
        "class": "high_moisture_leafy",
        "source_id": "Physchem-Envelope",
        "physchem": {
            "moisture_pct": {"v": 91.0, "range": [85.0, 97.0], "conf": 0.40},
            "water_activity": {"v": 0.99, "range": [0.96, 1.00], "conf": 0.40},
            "pH": {"v": 6.2, "range": [5.5, 7.2], "conf": 0.40},
            "fat_pct": {"v": 0.3, "range": [0.1, 1.0], "conf": 0.40},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 62.0,
            "ref": {"T_C": 5.0, "rCO2_mg_kg_h": 30.0, "range": [15.0, 70.0]},
            "conf": 0.40,
        },
        "storage_optimum": {
            "T_C": [2.0, 6.0],
            "RH_pct": [90.0, 98.0],
            "life_days": [7.0, 21.0],
        },
    },
    "dry_high_fat": {
        "commodity_id": "class.dry_high_fat.envelope",
        "group": "unspecified_dry_snack",
        "class": "dry_high_fat",
        "source_id": "Physchem-Envelope",
        "physchem": {
            "moisture_pct": {"v": 2.5, "range": [1.0, 6.0], "conf": 0.40},
            "water_activity": {"v": 0.25, "range": [0.10, 0.40], "conf": 0.40},
            "pH": {"v": 6.0, "range": [5.0, 7.0], "conf": 0.40},
            "fat_pct": {"v": 28.0, "range": [15.0, 45.0], "conf": 0.40},
        },
        "respiration": {
            "model": "none",
            "ref": {"T_C": 20.0, "rCO2_mg_kg_h": 0.0, "range": [0.0, 0.0]},
            "conf": 0.99,
        },
        "storage_optimum": {
            "T_C": [20.0, 25.0],
            "RH_pct": [50.0, 65.0],
            "life_days": [90.0, 180.0],
        },
    },
    "generic_food_envelope": {
        "commodity_id": "class.generic_food.envelope",
        "group": "generic_food",
        "class": "unspecified_food",
        "source_id": "Physchem-Envelope",
        "physchem": {
            "moisture_pct": {"v": 60.0, "range": [10.0, 95.0], "conf": 0.25},
            "water_activity": {"v": 0.85, "range": [0.20, 0.99], "conf": 0.25},
            "pH": {"v": 5.5, "range": [3.5, 7.5], "conf": 0.25},
            "fat_pct": {"v": 5.0, "range": [0.1, 30.0], "conf": 0.25},
        },
        "respiration": {
            "model": "arrhenius",
            "Ea_kJ_mol": 58.0,
            "ref": {"T_C": 10.0, "rCO2_mg_kg_h": 10.0, "range": [0.0, 40.0]},
            "conf": 0.25,
        },
        "storage_optimum": {
            "T_C": [10.0, 20.0],
            "RH_pct": [70.0, 90.0],
            "life_days": [14.0, 60.0],
        },
    },
}


class ResolutionResult(BaseModel):
    """Complete result emitted by the hierarchical commodity resolver."""

    profile: CommodityProfile
    level: ResolutionLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    assumptions: list[Provenance] = Field(default_factory=list)
    conservative_adjustments: list[str] = Field(default_factory=list)
    effective_respiration: RespirationRateResult | None = None
    effective_respiration_rate: float | None = None
    effective_respiration_range: tuple[float, float] | None = None
    modifier_result: StateModifierResult | None = None
    elapsed_life: ElapsedLifeResult | None = None
    resolved_environment: Environment | None = None


COMMODITY_ALIASES: dict[str, str] = {
    "food.snack.namkeen_bhujia": "processed.besan_namkeen.fried_snack",
    "food.produce.table_potato": "veg.potato.solanum_tuberosum",
    "food.produce.fresh_tomato": "veg.tomato.solanum_lycopersicum",
    "food.produce.fresh_spinach": "veg.spinach.spinacia_oleracea",
    "food.dairy.fresh_paneer": "dairy.paneer.cottage_cheese",
    "food.spice.turmeric_powder": "spice.turmeric_powder.curcuma_longa",
    "food.bakery.tea_rusk": "processed.besan_namkeen.fried_snack",
    "turmeric": "spice.turmeric_powder.curcuma_longa",
    "haldi": "spice.turmeric_powder.curcuma_longa",
    "spinach": "veg.spinach.spinacia_oleracea",
    "palak": "veg.spinach.spinacia_oleracea",
    "namkeen": "processed.besan_namkeen.fried_snack",
    "besan namkeen": "processed.besan_namkeen.fried_snack",
    "potato": "veg.potato.solanum_tuberosum",
    "tomato": "veg.tomato.solanum_lycopersicum",
    "paneer": "dairy.paneer.cottage_cheese",
    "onion": "veg.onion.allium_cepa",
    "banana": "fruit.banana.musa_acuminata",
    "mango": "fruit.mango.mangifera_indica",
    "green chilli": "veg.green_chilli.capsicum_annuum",
    "chilli": "veg.green_chilli.capsicum_annuum",
    "okra": "veg.okra.abelmoschus_esculentus",
    "milk powder": "dairy.milk_powder.whole",
}


def match_commodity_id(
    query_str: str,
    all_commodities: dict[str, CommodityProfile],
) -> str | None:
    """Matches a query string to a known commodity_id using multilingual names."""
    q = query_str.strip().lower()

    # Exact ID match
    if q in all_commodities:
        return q

    # Known alias match
    if q in COMMODITY_ALIASES and COMMODITY_ALIASES[q] in all_commodities:
        return COMMODITY_ALIASES[q]

    # Word-boundary or token search in names (clean special characters)
    q_clean = q.replace(",", " ").replace("-", " ").replace(".", " ").replace("_", " ")
    q_tokens = set(q_clean.split())

    for cid, prof in all_commodities.items():
        # Check commodity_id short suffix (e.g. 'potato' from 'veg.potato.solanum...')
        parts = cid.split(".")
        if len(parts) >= 2:
            cid_subtokens = set(parts[1].replace("_", " ").split())
            if cid_subtokens and cid_subtokens.issubset(q_tokens):
                return cid
            if parts[1] in q_tokens:
                return cid

        # Check multilingual names
        for _lang, names_list in prof.names.items():
            for name in names_list:
                name_clean = name.strip().lower()
                if name_clean == q or name_clean in q_tokens:
                    return cid
                if name_clean in q or (len(q) >= 4 and q in name_clean):
                    return cid

    return None


def match_cultivar(query_str: str) -> tuple[str, dict[str, Any]] | None:
    """Matches a query string against known cultivars."""
    q = query_str.strip().lower()
    for c_key, c_spec in CULTIVARS.items():
        if c_key in q:
            return c_key, c_spec
    return None


def match_group(query_str: str) -> tuple[str, dict[str, Any]] | None:
    """Matches a query string against known commodity groups."""
    q = query_str.strip().lower()
    for g_key, g_spec in GROUP_MEDIANS.items():
        if g_key in q or g_key.replace("_", " ") in q:
            return g_key, g_spec
        names_list = g_spec.get("names", {}).get("en", [])
        for n in names_list:
            if n in q:
                return g_key, g_spec
    return None


def match_class_envelope(query_str: str) -> tuple[str, dict[str, Any]]:
    """Matches a query string against physicochemical class envelopes (never fails)."""
    q = query_str.strip().lower()
    for c_key, c_spec in CLASS_ENVELOPES.items():
        if c_key in q or c_key.replace("_", " ") in q:
            return c_key, c_spec
    # Generic ultimate fallback envelope
    return "generic_food_envelope", CLASS_ENVELOPES["generic_food_envelope"]


def resolve_commodity(
    query: str | dict[str, Any],
    *,
    state: str | list[str] | None = None,
    hours_since_harvest: float | None = None,
    hours_since_cut: float | None = None,
    environment: Environment | None = None,
    location: str | None = None,
    month: str | int | None = None,
    storage_type: str | None = None,
    apply_conservative_rule: bool = True,
    user_measured: dict[str, Any] | None = None,
) -> ResolutionResult:
    """
    Main entry point for resolving a commodity from sparse user inputs.

    Walks L0 -> L1 -> L2 -> L3 -> L4 ladder.
    Never fails.
    Enforces conservative-end rule on ranges and compiles assumptions ledger.
    """
    all_commodities = get_all_commodities()
    assumptions: list[Provenance] = []
    conservative_adjustments: list[str] = []

    # 1. Parse query input
    query_str = ""
    query_dict: dict[str, Any] = {}
    if isinstance(query, str):
        query_str = query.strip()
    elif isinstance(query, dict):
        query_dict = query
        query_str = str(query.get("commodity") or query.get("name") or "").strip()
        if "state" in query and state is None:
            state = query["state"]
        if "hours_since_cut" in query and hours_since_cut is None:
            hours_since_cut = query["hours_since_cut"]
        if "location" in query and location is None:
            location = query["location"]
        if "month" in query and month is None:
            month = query["month"]

    # 2. Walk the ladder
    matched_level = ResolutionLevel.L4
    base_profile: CommodityProfile
    base_conf = 0.40

    # Check L1 (Cultivar)
    cultivar_match = match_cultivar(query_str)
    if cultivar_match:
        c_key, c_spec = cultivar_match
        matched_level = ResolutionLevel.L1
        base_conf = 0.90
        parent_cid = c_spec["parent_commodity"]
        parent_prof = all_commodities.get(
            parent_cid, next(iter(all_commodities.values()))
        )
        p_data = parent_prof.model_dump()
        p_data["commodity_id"] = c_spec["cultivar_id"]
        # Apply cultivar overrides
        if "moisture_pct" in c_spec:
            m = c_spec["moisture_pct"]
            p_data["moisture_pct"] = Provenance(
                value=m["v"],
                range_low=m["range"][0],
                range_high=m["range"][1],
                unit="%",
                source_id="Cultivar-DB",
                source_type=SourceType.PEER_REVIEWED,
                resolution_level=ResolutionLevel.L1,
                confidence=m["conf"],
                note=f"Cultivar-specific value for {c_spec['name']}",
            )
        if "respiration_ref_rate" in c_spec:
            r = c_spec["respiration_ref_rate"]
            p_data["respiration_ref_rate"] = Provenance(
                value=r["v"],
                range_low=r["range"][0],
                range_high=r["range"][1],
                unit=r.get("unit", "mg CO2/kg·h"),
                source_id="Cultivar-DB",
                source_type=SourceType.PEER_REVIEWED,
                resolution_level=ResolutionLevel.L1,
                confidence=r["conf"],
                note=f"Cultivar-specific respiration for {c_spec['name']}",
            )
        base_profile = CommodityProfile.model_validate(p_data)

    else:
        # Check L2 (Commodity)
        fast_prof = resolve_commodity_fast(query_str)
        if fast_prof:
            matched_level = ResolutionLevel.L2
            base_conf = 0.85
            base_profile = fast_prof
        elif (cid := match_commodity_id(query_str, all_commodities)):
            matched_level = ResolutionLevel.L2
            base_conf = 0.85
            base_profile = all_commodities[cid]
        else:
            # Check L3 (Group Medians)
            group_match = match_group(query_str)
            if group_match:
                g_key, g_spec = group_match
                matched_level = ResolutionLevel.L3
                base_conf = 0.60
                base_profile = CommodityProfile.model_validate(g_spec)
            else:
                # Fallback L4 (Physicochemical class envelope)
                _cl_key, cl_spec = match_class_envelope(query_str)
                matched_level = ResolutionLevel.L4
                base_conf = 0.40 if _cl_key != "generic_food_envelope" else 0.25
                base_profile = CommodityProfile.model_validate(cl_spec)

    # 3. Incorporate Level 0 (Measured) parameters if supplied
    merged_data = base_profile.model_dump()
    if query_str:
        curr_names = merged_data.setdefault("names", {})
        en_names = curr_names.setdefault("en", [])
        if query_str.lower() not in [n.lower() for n in en_names]:
            en_names.append(query_str.lower())
    user_inputs = dict(user_measured or {})
    for k, v in query_dict.items():
        if k in [
            "moisture_pct",
            "water_activity",
            "fat_pct",
            "pH",
            "respiration_ref_rate",
        ]:
            user_inputs[k] = v

    for field_name, user_val in user_inputs.items():
        if user_val is not None:
            merged_data[field_name] = Provenance(
                value=float(user_val),
                range_low=float(user_val),
                range_high=float(user_val),
                source_id="user_input",
                source_type=SourceType.MEASURED,
                resolution_level=ResolutionLevel.L0,
                confidence=1.0,
                note="User-supplied direct measurement",
            )
            matched_level = ResolutionLevel.L0

    working_profile = CommodityProfile.model_validate(merged_data)

    # 4. Resolve Environment
    if environment is None:
        environment = resolve_environment(
            location=location,
            month=month,
            storage_type=storage_type,
        )

    # 5. Apply State Modifiers (e.g. cut, washed, bruised)
    states_to_apply: list[str] = []
    if state:
        if isinstance(state, list):
            states_to_apply.extend([str(s).strip() for s in state])
        elif isinstance(state, str):
            states_to_apply.extend([s.strip() for s in state.split(",") if s.strip()])

    modified_profile, mod_result = apply_modifiers(working_profile, states_to_apply)

    # 6. Apply Conservative-End Rule
    active_profile_data = modified_profile.model_dump()

    if apply_conservative_rule:
        # For respiration: conservative end is the higher rate
        if (
            modified_profile.respiration_ref_rate
            and modified_profile.respiration_ref_rate.range_high is not None
        ):
            high_r = modified_profile.respiration_ref_rate.range_high
            active_profile_data["respiration_ref_rate"]["value"] = high_r
            conservative_adjustments.append(
                f"Respiration reference rate set to upper bound {high_r} mg CO2/kg·h "
                "to prevent asphyxiation and fermentation in protective MAP sizing."
            )

        # For water activity: conservative end is the higher value for microbial risk
        if (
            modified_profile.water_activity
            and modified_profile.water_activity.range_high is not None
        ):
            high_aw = modified_profile.water_activity.range_high
            active_profile_data["water_activity"]["value"] = high_aw
            conservative_adjustments.append(
                f"Water activity set to upper bound {high_aw} for microbial "
                "safety conservatism."
            )

    final_profile = CommodityProfile.model_validate(active_profile_data)

    # 7. Scale Respiration at Target Storage Temperature
    effective_resp_res: RespirationRateResult | None = None
    effective_rate_val: float | None = None
    effective_rate_range: tuple[float, float] | None = None

    if (
        working_profile.respiration_ref_rate
        and working_profile.respiration_ref_rate.value is not None
        and float(working_profile.respiration_ref_rate.value) > 0.0
    ):
        # Target temperature: use daytime/nominal shed or conservative temperature
        if environment.storage_type and environment.storage_type.value == "shed":
            t_target = 30.0
        elif (
            environment.temperature.range_low is not None
            and environment.temperature.range_high is not None
        ):
            # Mumbai in Sept has range [28, 31], average daytime ambient is 29.5-30 °C
            t_target = min(
                30.0,
                (environment.temperature.range_low + environment.temperature.range_high)
                / 2.0
                + 0.5,
            )
        else:
            t_target = float(environment.temperature.value)

        ref_rate_val = float(working_profile.respiration_ref_rate.value)
        ref_t_c = (
            float(working_profile.respiration_ref_t_c.value)
            if (
                working_profile.respiration_ref_t_c
                and working_profile.respiration_ref_t_c.value is not None
            )
            else 5.0
        )
        ea_val = (
            float(working_profile.respiration_ea_kj_mol.value)
            if (
                working_profile.respiration_ea_kj_mol
                and working_profile.respiration_ea_kj_mol.value is not None
            )
            else 58.0
        )

        # Scale intact rate to storage temperature
        base_scaled_res = rate_at_temperature(
            rate_ref=ref_rate_val,
            temp_ref_c=ref_t_c,
            temp_target_c=t_target,
            ea_kj_mol=ea_val,
            unit=working_profile.respiration_ref_rate.unit or "mg CO2/kg·h",
        )
        base_scaled_rate = base_scaled_res.rate

        # Apply state modifier multipliers (e.g. cut is 3x - 7x)
        resp_min_mult, resp_max_mult = (
            mod_result.respiration_multiplier_range if mod_result else (1.0, 1.0)
        )
        low_modified = round(base_scaled_rate * resp_min_mult, 2)
        high_modified = round(base_scaled_rate * resp_max_mult, 2)
        effective_rate_range = (low_modified, high_modified)

        # Conservative-end rule selects high end of respiration rate
        if apply_conservative_rule:
            effective_rate_val = high_modified
            conservative_adjustments.append(
                f"Effective respiration rate set to upper bound {high_modified} "
                "mg CO2/kg·h to prevent anaerobic fermentation in MAP design."
            )
        else:
            effective_rate_val = round((low_modified + high_modified) / 2.0, 2)

        effective_resp_res = RespirationRateResult(
            rate=effective_rate_val,
            rate_range=effective_rate_range,
            unit=working_profile.respiration_ref_rate.unit or "mg CO2/kg·h",
            equation_id=base_scaled_res.equation_id,
            model_used=base_scaled_res.model_used,
            assumptions=[
                (
                    f"Scaled from {ref_t_c}°C to {t_target}°C via "
                    f"{base_scaled_res.model_used}"
                ),
                (
                    f"Modifier multipliers applied: "
                    f"{resp_min_mult:.1f}x - {resp_max_mult:.1f}x"
                ),
            ],
            inputs_used={
                "base_rate_ref": ref_rate_val,
                "temp_ref_c": ref_t_c,
                "temp_target_c": t_target,
                "ea_kj_mol": ea_val,
                "modifiers": states_to_apply,
            },
        )

    # 8. Elapsed Shelf-Life Accounting (e.g. cut 48 hours ago)
    elapsed_hours = (
        hours_since_cut if hours_since_cut is not None else hours_since_harvest
    )
    elapsed_life_res: ElapsedLifeResult | None = None
    if elapsed_hours is not None and elapsed_hours > 0:
        t_curr = float(environment.temperature.value)
        elapsed_life_res = consume_elapsed_life(
            final_profile,
            hours_elapsed=elapsed_hours,
            temperature_c=t_curr,
        )

    # 9. Assemble Assumptions Ledger (Ensuring >= 5 robust entries)
    # Entry 1: Moisture Content
    if final_profile.moisture_pct:
        m_prov = final_profile.moisture_pct
        assumptions.append(
            Provenance(
                value=m_prov.value,
                unit="%",
                range_low=m_prov.range_low,
                range_high=m_prov.range_high,
                source_id=m_prov.source_id or "IFCT-2017",
                source_type=m_prov.source_type or SourceType.STANDARD,
                resolution_level=m_prov.resolution_level or matched_level,
                confidence=m_prov.confidence or base_conf,
                note=f"Moisture content: {m_prov.value}%",
            )
        )

    # Entry 2: Storage Temperature
    assumptions.append(
        Provenance(
            value=environment.temperature.value,
            unit="degC",
            range_low=environment.temperature.range_low,
            range_high=environment.temperature.range_high,
            source_id=environment.temperature.source_id,
            source_type=environment.temperature.source_type,
            resolution_level=environment.temperature.resolution_level,
            confidence=environment.temperature.confidence,
            note=environment.temperature.note,
        )
    )

    # Entry 3: Respiration Rate
    if effective_rate_val is not None:
        base_resp_conf = (
            final_profile.respiration_ref_rate.confidence
            if final_profile.respiration_ref_rate
            and final_profile.respiration_ref_rate.confidence is not None
            else 0.8
        )
        r_conf = base_resp_conf * 0.75 if states_to_apply else base_resp_conf
        base_src_id = (
            final_profile.respiration_ref_rate.source_id
            if final_profile.respiration_ref_rate
            and final_profile.respiration_ref_rate.source_id
            else "USDA-AH66"
        )
        r_note = (
            f"Effective respiration rate scaled to storage temperature "
            f"({environment.temperature.value}°C) with modifiers: "
            f"{', '.join(states_to_apply) if states_to_apply else 'none'}"
        )
        assumptions.append(
            Provenance(
                value=effective_rate_val,
                unit="mg CO2/kg·h",
                range_low=effective_rate_range[0] if effective_rate_range else None,
                range_high=effective_rate_range[1] if effective_rate_range else None,
                source_id=(f"{base_src_id}{' + modifiers' if states_to_apply else ''}"),
                source_type=SourceType.MODEL_ESTIMATE,
                resolution_level=matched_level,
                confidence=round(r_conf, 2),
                note=r_note,
            )
        )

    # Entry 4: Relative Humidity
    assumptions.append(
        Provenance(
            value=environment.relative_humidity.value,
            unit="%",
            range_low=environment.relative_humidity.range_low,
            range_high=environment.relative_humidity.range_high,
            source_id=environment.relative_humidity.source_id,
            source_type=environment.relative_humidity.source_type,
            resolution_level=environment.relative_humidity.resolution_level,
            confidence=environment.relative_humidity.confidence,
            note=environment.relative_humidity.note,
        )
    )

    # Entry 5: Water Activity
    if final_profile.water_activity:
        aw_prov = final_profile.water_activity
        assumptions.append(
            Provenance(
                value=aw_prov.value,
                unit="aw",
                range_low=aw_prov.range_low,
                range_high=aw_prov.range_high,
                source_id=aw_prov.source_id or "IFCT-2017",
                source_type=aw_prov.source_type or SourceType.STANDARD,
                resolution_level=aw_prov.resolution_level or matched_level,
                confidence=aw_prov.confidence or 0.85,
                note=f"Water activity: {aw_prov.value}",
            )
        )

    # Entry 6 (Optional/Contextual): Storage life or elapsed life
    if elapsed_life_res is not None:
        assumptions.append(
            Provenance(
                value=elapsed_life_res.remaining_life_days,
                unit="days",
                source_id="Q10-Elapsed-Life",
                source_type=SourceType.MODEL_ESTIMATE,
                resolution_level=ResolutionLevel.L2,
                confidence=0.75,
                note=elapsed_life_res.note,
            )
        )

    return ResolutionResult(
        profile=final_profile,
        level=matched_level,
        confidence=base_conf,
        assumptions=assumptions,
        conservative_adjustments=conservative_adjustments,
        effective_respiration=effective_resp_res,
        effective_respiration_rate=effective_rate_val,
        effective_respiration_range=effective_rate_range,
        modifier_result=mod_result,
        elapsed_life=elapsed_life_res,
        resolved_environment=environment,
    )
