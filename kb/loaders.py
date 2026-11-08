"""
Loaders and validators for the Aavaran Knowledge Base layer.

Reads JSON and CSV files, strictly validates them against Pydantic models,
and fails loudly on missing source citations or out-of-range values.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from engine.types import CommodityProfile
from kb.models import (
    CommodityAliasRecord,
    FilmRecord,
    IsothermRecord,
    KnowledgeBaseData,
    MapTargetRecord,
    SourceRecord,
    StateModifierRecord,
    StructureRecord,
)
from kb.version import KB_VERSION

DEFAULT_KB_DIR = Path(__file__).resolve().parent


def _clean_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _clean_float(val: Any, field_name: str, row_id: str) -> Optional[float]:
    s = _clean_str(val)
    if s is None:
        return None
    try:
        return float(s)
    except ValueError as e:
        raise ValueError(f"Row '{row_id}': Invalid float value '{val}' for field '{field_name}'") from e


def _clean_int(val: Any, field_name: str, row_id: str) -> Optional[int]:
    s = _clean_str(val)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError as e:
        raise ValueError(f"Row '{row_id}': Invalid integer value '{val}' for field '{field_name}'") from e


def _clean_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("true", "1", "yes", "t")


def load_sources(file_path: Union[str, Path] = DEFAULT_KB_DIR / "sources.csv") -> Dict[str, SourceRecord]:
    """
    Load primary citations from CSV. Fails loudly on malformed entries.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Sources file not found: {path}")

    sources: Dict[str, SourceRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"sources.csv line {line_num}: Missing source id.")
            try:
                rec = SourceRecord(
                    id=row_id,
                    source_type=_clean_str(row.get("source_type")) or "STANDARD",
                    name=_clean_str(row.get("name")) or row_id,
                    citation=_clean_str(row.get("citation")) or row_id,
                    url=_clean_str(row.get("url")),
                    doi=_clean_str(row.get("doi")),
                    publication_year=_clean_int(row.get("publication_year"), "publication_year", row_id),
                    notes=_clean_str(row.get("notes")),
                )
                sources[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in sources.csv line {line_num} for '{row_id}': {e}") from e

    if not sources:
        raise ValueError(f"No sources loaded from {path}")
    return sources


def load_films(
    file_path: Union[str, Path] = DEFAULT_KB_DIR / "films.csv",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, FilmRecord]:
    """
    Load single-layer films from CSV. Enforces test conditions and source existence.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Films file not found: {path}")

    films: Dict[str, FilmRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"films.csv line {line_num}: Missing film id.")

            source_id = _clean_str(row.get("source_id"))
            if not source_id:
                raise ValueError(f"Film '{row_id}' has no source_id. Un-cited film data is invalid.")
            if sources is not None and source_id not in sources:
                raise ValueError(
                    f"Film '{row_id}' references unknown source '{source_id}'. Known sources: {list(sources.keys())}"
                )

            try:
                rec = FilmRecord(
                    id=row_id,
                    film_name=_clean_str(row.get("film_name")) or row_id,
                    thickness_um=_clean_float(row.get("thickness_um"), "thickness_um", row_id) or 25.0,
                    otr_value=_clean_float(row.get("otr_value"), "otr_value", row_id) or 0.0,
                    otr_min=_clean_float(row.get("otr_min"), "otr_min", row_id),
                    otr_max=_clean_float(row.get("otr_max"), "otr_max", row_id),
                    otr_test_temperature_c=_clean_float(row.get("otr_test_temperature_c"), "otr_test_temperature_c", row_id) or 23.0,
                    otr_test_rh_pct=_clean_float(row.get("otr_test_rh_pct"), "otr_test_rh_pct", row_id) or 0.0,
                    otr_test_method=_clean_str(row.get("otr_test_method")) or "",
                    wvtr_value=_clean_float(row.get("wvtr_value"), "wvtr_value", row_id) or 0.0,
                    wvtr_min=_clean_float(row.get("wvtr_min"), "wvtr_min", row_id),
                    wvtr_max=_clean_float(row.get("wvtr_max"), "wvtr_max", row_id),
                    wvtr_test_temperature_c=_clean_float(row.get("wvtr_test_temperature_c"), "wvtr_test_temperature_c", row_id) or 38.0,
                    wvtr_test_rh_pct=_clean_float(row.get("wvtr_test_rh_pct"), "wvtr_test_rh_pct", row_id) or 90.0,
                    wvtr_test_method=_clean_str(row.get("wvtr_test_method")) or "",
                    barrier_class=_clean_str(row.get("barrier_class")) or "Moderate",
                    typical_use=_clean_str(row.get("typical_use")) or "",
                    epr_category=_clean_str(row.get("epr_category")) or "Cat II",
                    source_id=source_id,
                )
                films[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in films.csv line {line_num} for '{row_id}': {e}") from e

    return films


def load_structures(
    file_path: Union[str, Path] = DEFAULT_KB_DIR / "structures.csv",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, StructureRecord]:
    """
    Load multilayer laminate structures from CSV.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Structures file not found: {path}")

    structures: Dict[str, StructureRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"structures.csv line {line_num}: Missing structure id.")

            source_id = _clean_str(row.get("source_id"))
            if not source_id:
                raise ValueError(f"Structure '{row_id}' has no source_id. Un-cited structure data is invalid.")
            if sources is not None and source_id not in sources:
                raise ValueError(
                    f"Structure '{row_id}' references unknown source '{source_id}'. Known sources: {list(sources.keys())}"
                )

            layers_raw = _clean_str(row.get("layer_stack")) or ""
            if layers_raw.startswith("["):
                layer_stack = json.loads(layers_raw)
            else:
                layer_stack = [s.strip() for s in layers_raw.split(";") if s.strip()]

            gauges_raw = _clean_str(row.get("gauge_per_layer_um")) or ""
            if gauges_raw.startswith("["):
                gauge_per_layer_um = [float(x) for x in json.loads(gauges_raw)]
            else:
                gauge_per_layer_um = [float(s.strip()) for s in gauges_raw.split(";") if s.strip()]

            try:
                rec = StructureRecord(
                    id=row_id,
                    name=_clean_str(row.get("name")) or row_id,
                    layer_stack=layer_stack,
                    gauge_per_layer_um=gauge_per_layer_um,
                    composite_thickness_um=_clean_float(row.get("composite_thickness_um"), "composite_thickness_um", row_id) or sum(gauge_per_layer_um),
                    measured_otr=_clean_float(row.get("measured_otr"), "measured_otr", row_id) or 0.0,
                    measured_wvtr=_clean_float(row.get("measured_wvtr"), "measured_wvtr", row_id) or 0.0,
                    otr_test_conditions=_clean_str(row.get("otr_test_conditions")) or "23 C, 0 % RH",
                    wvtr_test_conditions=_clean_str(row.get("wvtr_test_conditions")) or "38 C, 90 % RH",
                    cost_inr_per_sqm=_clean_float(row.get("cost_inr_per_sqm"), "cost_inr_per_sqm", row_id) or 10.0,
                    indicative_cost_per_pack=_clean_float(row.get("indicative_cost_per_pack"), "indicative_cost_per_pack", row_id),
                    epr_category=_clean_str(row.get("epr_category")) or "Cat III",
                    recyclability_notes=_clean_str(row.get("recyclability_notes")),
                    typical_applications=_clean_str(row.get("typical_applications")),
                    source_id=source_id,
                )
                structures[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in structures.csv line {line_num} for '{row_id}': {e}") from e

    return structures


def load_isotherms(
    file_path: Union[str, Path] = DEFAULT_KB_DIR / "isotherms.csv",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, IsothermRecord]:
    """
    Load moisture sorption isotherms from CSV.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Isotherms file not found: {path}")

    isotherms: Dict[str, IsothermRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"isotherms.csv line {line_num}: Missing isotherm id.")

            source_id = _clean_str(row.get("source_id"))
            if not source_id:
                raise ValueError(f"Isotherm '{row_id}' has no source_id. Un-cited isotherm data is invalid.")
            if sources is not None and source_id not in sources:
                raise ValueError(
                    f"Isotherm '{row_id}' references unknown source '{source_id}'. Known sources: {list(sources.keys())}"
                )

            try:
                rec = IsothermRecord(
                    id=row_id,
                    food_class_or_commodity=_clean_str(row.get("food_class_or_commodity")) or row_id,
                    model_type=_clean_str(row.get("model_type")) or "GAB",
                    temperature_c=_clean_float(row.get("temperature_c"), "temperature_c", row_id) or 25.0,
                    m0=_clean_float(row.get("m0"), "m0", row_id),
                    c_g=_clean_float(row.get("c_g"), "c_g", row_id),
                    k=_clean_float(row.get("k"), "k", row_id),
                    linear_slope_b=_clean_float(row.get("linear_slope_b"), "linear_slope_b", row_id),
                    linear_intercept_c=_clean_float(row.get("linear_intercept_c"), "linear_intercept_c", row_id),
                    aw_min=_clean_float(row.get("aw_min"), "aw_min", row_id),
                    aw_max=_clean_float(row.get("aw_max"), "aw_max", row_id),
                    aw_crit=_clean_float(row.get("aw_crit"), "aw_crit", row_id),
                    source_id=source_id,
                )
                isotherms[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in isotherms.csv line {line_num} for '{row_id}': {e}") from e

    return isotherms


def load_map_targets(
    file_path: Union[str, Path] = DEFAULT_KB_DIR / "map_targets.csv",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, MapTargetRecord]:
    """
    Load Modified Atmosphere Packaging target gas compositions from CSV.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MAP targets file not found: {path}")

    targets: Dict[str, MapTargetRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"map_targets.csv line {line_num}: Missing map target id.")

            source_id = _clean_str(row.get("source_id"))
            if not source_id:
                raise ValueError(f"MAP target '{row_id}' has no source_id. Un-cited MAP data is invalid.")
            if sources is not None and source_id not in sources:
                raise ValueError(
                    f"MAP target '{row_id}' references unknown source '{source_id}'. Known sources: {list(sources.keys())}"
                )

            try:
                rec = MapTargetRecord(
                    id=row_id,
                    product_group=_clean_str(row.get("product_group")) or row_id,
                    target_o2_min=_clean_float(row.get("target_o2_min"), "target_o2_min", row_id) or 0.0,
                    target_o2_max=_clean_float(row.get("target_o2_max"), "target_o2_max", row_id) or 0.0,
                    target_co2_min=_clean_float(row.get("target_co2_min"), "target_co2_min", row_id) or 0.0,
                    target_co2_max=_clean_float(row.get("target_co2_max"), "target_co2_max", row_id) or 0.0,
                    o2_floor=_clean_float(row.get("o2_floor"), "o2_floor", row_id) or 0.0,
                    co2_injury_ceiling=_clean_float(row.get("co2_injury_ceiling"), "co2_injury_ceiling", row_id) or 100.0,
                    balance_gas=_clean_str(row.get("balance_gas")) or "N2",
                    optimum_temp_c_min=_clean_float(row.get("optimum_temp_c_min"), "optimum_temp_c_min", row_id),
                    optimum_temp_c_max=_clean_float(row.get("optimum_temp_c_max"), "optimum_temp_c_max", row_id),
                    notes=_clean_str(row.get("notes")),
                    source_id=source_id,
                )
                targets[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in map_targets.csv line {line_num} for '{row_id}': {e}") from e

    return targets


def load_state_modifiers(
    file_path: Union[str, Path] = DEFAULT_KB_DIR / "state_modifiers.csv",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, StateModifierRecord]:
    """
    Load state modifier multipliers and effects from CSV.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"State modifiers file not found: {path}")

    modifiers: Dict[str, StateModifierRecord] = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):
            row_id = _clean_str(row.get("id"))
            if not row_id:
                raise ValueError(f"state_modifiers.csv line {line_num}: Missing modifier id.")

            source_id = _clean_str(row.get("source_id"))
            if not source_id:
                raise ValueError(f"State modifier '{row_id}' has no source_id. Un-cited modifier data is invalid.")
            if sources is not None and source_id not in sources:
                raise ValueError(
                    f"State modifier '{row_id}' references unknown source '{source_id}'. Known sources: {list(sources.keys())}"
                )

            try:
                rec = StateModifierRecord(
                    id=row_id,
                    modifier_name=_clean_str(row.get("modifier_name")) or row_id,
                    commodity_group=_clean_str(row.get("commodity_group")) or "all",
                    respiration_factor_min=_clean_float(row.get("respiration_factor_min"), "respiration_factor_min", row_id),
                    respiration_factor_max=_clean_float(row.get("respiration_factor_max"), "respiration_factor_max", row_id),
                    ethylene_factor_min=_clean_float(row.get("ethylene_factor_min"), "ethylene_factor_min", row_id),
                    ethylene_factor_max=_clean_float(row.get("ethylene_factor_max"), "ethylene_factor_max", row_id),
                    aw_delta=_clean_float(row.get("aw_delta"), "aw_delta", row_id),
                    microbial_risk_level=_clean_str(row.get("microbial_risk_level")),
                    new_failure_mode=_clean_str(row.get("new_failure_mode")),
                    max_ambient_hours=_clean_float(row.get("max_ambient_hours"), "max_ambient_hours", row_id),
                    life_factor_min=_clean_float(row.get("life_factor_min"), "life_factor_min", row_id),
                    life_factor_max=_clean_float(row.get("life_factor_max"), "life_factor_max", row_id),
                    requires_antifog=_clean_bool(row.get("requires_antifog")),
                    description=_clean_str(row.get("description")),
                    source_id=source_id,
                )
                modifiers[rec.id] = rec
            except ValidationError as e:
                raise ValueError(f"Validation error in state_modifiers.csv line {line_num} for '{row_id}': {e}") from e

    return modifiers


def load_commodity(
    file_path: Union[str, Path],
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> CommodityProfile:
    """
    Load a single commodity profile JSON and validate against CommodityProfile.
    Fails loudly on unresolvable sources or out-of-range physical values.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Commodity file not found: {path}")

    with open(path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    # Citation validation
    primary_source = data.get("source_id")
    if not primary_source:
        # Fallback to respiration or storage or physchem source if defined
        primary_source = (
            data.get("respiration", {}).get("src")
            or data.get("storage_optimum", {}).get("src")
            or data.get("physchem", {}).get("moisture_pct", {}).get("src")
        )
        data["source_id"] = primary_source

    if not primary_source:
        raise ValueError(f"Commodity in '{path.name}' has no resolvable source citation.")

    if sources is not None and primary_source not in sources:
        raise ValueError(
            f"Commodity '{data.get('commodity_id')}' in '{path.name}' cites unknown primary source '{primary_source}'."
        )

    # Validate citations of sub-blocks if sources is provided
    if sources is not None:
        # Check physchem citations
        physchem = data.get("physchem", {})
        for metric, entry in physchem.items():
            if isinstance(entry, dict) and "src" in entry:
                sub_src = entry["src"]
                if sub_src not in sources:
                    raise ValueError(
                        f"Commodity '{data.get('commodity_id')}' physchem.{metric} cites unknown source '{sub_src}'."
                    )

        # Check respiration citation
        resp = data.get("respiration", {})
        if "src" in resp and resp["src"] not in sources:
            raise ValueError(
                f"Commodity '{data.get('commodity_id')}' respiration cites unknown source '{resp['src']}'."
            )

        # Check storage citation
        stg = data.get("storage_optimum", {})
        if "src" in stg and stg["src"] not in sources:
            raise ValueError(
                f"Commodity '{data.get('commodity_id')}' storage_optimum cites unknown source '{stg['src']}'."
            )

    try:
        profile = CommodityProfile.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Validation error in commodity '{path.name}': {e}") from e

    # Out-of-range physical sanity checks
    if profile.moisture_pct and profile.moisture_pct.value is not None:
        m = float(profile.moisture_pct.value)
        if not (0.0 <= m <= 100.0):
            raise ValueError(f"Commodity '{profile.commodity_id}': moisture_pct {m} is out of physical range [0, 100].")

    if profile.water_activity and profile.water_activity.value is not None:
        aw = float(profile.water_activity.value)
        if not (0.0 <= aw <= 1.0):
            raise ValueError(f"Commodity '{profile.commodity_id}': water_activity {aw} is out of physical range [0, 1].")

    if profile.pH and profile.pH.value is not None:
        ph = float(profile.pH.value)
        if not (0.0 <= ph <= 14.0):
            raise ValueError(f"Commodity '{profile.commodity_id}': pH {ph} is out of physical range [0, 14].")

    if profile.fat_pct and profile.fat_pct.value is not None:
        f_val = float(profile.fat_pct.value)
        if not (0.0 <= f_val <= 100.0):
            raise ValueError(f"Commodity '{profile.commodity_id}': fat_pct {f_val} is out of physical range [0, 100].")

    if profile.respiration_ref_rate and profile.respiration_ref_rate.value is not None:
        r = float(profile.respiration_ref_rate.value)
        if r < 0.0:
            raise ValueError(f"Commodity '{profile.commodity_id}': respiration rate {r} cannot be negative.")

    return profile


def load_all_commodities(
    dir_path: Union[str, Path] = DEFAULT_KB_DIR / "commodities",
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> Dict[str, CommodityProfile]:
    """
    Load all JSON commodity profiles from a directory.
    """
    path = Path(dir_path)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Commodities directory not found: {path}")

    commodities: Dict[str, CommodityProfile] = {}
    json_files = sorted(path.glob("*.json"))
    if not json_files:
        raise ValueError(f"No JSON commodity files found in {path}")

    for jf in json_files:
        profile = load_commodity(jf, sources=sources)
        commodities[profile.commodity_id] = profile

    return commodities


def extract_aliases_from_commodities(
    commodities: Dict[str, CommodityProfile],
    sources: Optional[Dict[str, SourceRecord]] = None,
) -> List[CommodityAliasRecord]:
    """
    Extract multilingual alias records with source attribution from commodities.
    """
    aliases: List[CommodityAliasRecord] = []
    idx = 1
    for cid, profile in commodities.items():
        src_id = profile.source_id or "USDA-AH66"
        if sources is not None and src_id not in sources:
            src_id = next(iter(sources.keys()))

        for lang, name_list in profile.names.items():
            for name in name_list:
                aliases.append(
                    CommodityAliasRecord(
                        id=idx,
                        commodity_id=cid,
                        alias=name,
                        language=lang,
                        embedding=None,
                        source_id=src_id,
                    )
                )
                idx += 1
    return aliases


def load_kb(base_dir: Union[str, Path] = DEFAULT_KB_DIR) -> KnowledgeBaseData:
    """
    High-level loader for the complete Aavaran Knowledge Base.
    Loads and cross-validates all sources, films, structures, isotherms,
    MAP targets, state modifiers, and commodities.
    """
    base = Path(base_dir)
    sources = load_sources(base / "sources.csv")
    films = load_films(base / "films.csv", sources=sources)
    structures = load_structures(base / "structures.csv", sources=sources)
    isotherms = load_isotherms(base / "isotherms.csv", sources=sources)
    map_targets = load_map_targets(base / "map_targets.csv", sources=sources)
    state_modifiers = load_state_modifiers(base / "state_modifiers.csv", sources=sources)
    commodities = load_all_commodities(base / "commodities", sources=sources)
    aliases = extract_aliases_from_commodities(commodities, sources=sources)

    return KnowledgeBaseData(
        version=KB_VERSION,
        sources=sources,
        commodities=commodities,
        films=films,
        structures=structures,
        isotherms=isotherms,
        map_targets=map_targets,
        state_modifiers=state_modifiers,
        aliases=aliases,
    )
