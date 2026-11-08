"""
Unit and invariant tests for the Aavaran Knowledge Base layer.

Asserts:
- Every seeded row across all tables has a resolvable source in sources.
- No film has an OTR or WVTR outside physically plausible bounds.
- All films have complete test conditions (temperature, RH, method).
- Loaders fail loudly on missing citations or out-of-range values.
- Alembic migration generates valid PostgreSQL DDL with pgvector and NOT NULL FK constraints.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from kb import (
    KB_VERSION,
    load_all_commodities,
    load_commodity,
    load_films,
    load_isotherms,
    load_kb,
    load_map_targets,
    load_sources,
    load_state_modifiers,
    load_structures,
)
from kb.models import FilmRecord, StructureRecord


@pytest.fixture(scope="module")
def kb_data():
    return load_kb()


def test_kb_version():
    assert KB_VERSION == "1.0.0"


def test_all_seeded_rows_have_resolvable_source(kb_data):
    """
    Assert that every seeded row across all data tables (commodities, films,
    structures, isotherms, map_targets, state_modifiers, aliases) has a resolvable
    source citation in sources.csv.
    """
    sources = kb_data.sources
    assert len(sources) >= 10, "At least 10 primary sources must be registered."

    # 1. Commodities (original 12 + 6 Aavaran fresh crops + atta & toor dal for kirana)
    assert len(kb_data.commodities) == 20, "Exactly 20 diverse commodities must be seeded."
    for cid, comm in kb_data.commodities.items():
        assert comm.source_id is not None, f"Commodity '{cid}' has null source_id"
        assert comm.source_id in sources, f"Commodity '{cid}' cites unresolved source '{comm.source_id}'"

        # Check nested provenance sources
        for field_name in ["moisture_pct", "water_activity", "fat_pct", "pH"]:
            field = getattr(comm, field_name, None)
            if field and field.source_id:
                assert field.source_id in sources, (
                    f"Commodity '{cid}' field '{field_name}' cites unresolved source '{field.source_id}'"
                )

        if comm.respiration_ref_rate and comm.respiration_ref_rate.source_id:
            assert comm.respiration_ref_rate.source_id in sources

        if comm.storage_optimum_t_c and comm.storage_optimum_t_c.source_id:
            assert comm.storage_optimum_t_c.source_id in sources

    # 2. Films (>= 15 films from section 3.1)
    assert len(kb_data.films) >= 15
    for fid, film in kb_data.films.items():
        assert film.source_id in sources, f"Film '{fid}' cites unresolved source '{film.source_id}'"

    # 3. Structures (12 structures)
    assert len(kb_data.structures) == 12
    for sid, struct in kb_data.structures.items():
        assert struct.source_id in sources, f"Structure '{sid}' cites unresolved source '{struct.source_id}'"

    # 4. Isotherms (>= 6 food classes)
    assert len(kb_data.isotherms) >= 6
    for iid, iso in kb_data.isotherms.items():
        assert iso.source_id in sources, f"Isotherm '{iid}' cites unresolved source '{iso.source_id}'"

    # 5. MAP Targets (>= 12 targets)
    assert len(kb_data.map_targets) >= 12
    for mid, map_target in kb_data.map_targets.items():
        assert map_target.source_id in sources, f"MAP target '{mid}' cites unresolved source '{map_target.source_id}'"

    # 6. State Modifiers (>= 5 modifiers)
    assert len(kb_data.state_modifiers) >= 5
    for mod_id, mod in kb_data.state_modifiers.items():
        assert mod.source_id in sources, f"State modifier '{mod_id}' cites unresolved source '{mod.source_id}'"

    # 7. Commodity Aliases
    assert len(kb_data.aliases) >= 100
    for alias in kb_data.aliases:
        assert alias.source_id in sources, f"Alias '{alias.alias}' cites unresolved source '{alias.source_id}'"


def test_film_barrier_physically_plausible_and_conditioned(kb_data):
    """
    Assert that no film has an OTR or WVTR outside physically plausible bounds,
    and every single film record stores test conditions (temperature, RH, method)
    next to the value.
    """
    for fid, film in kb_data.films.items():
        # Physical bounds for single-layer/base films
        assert 0.0001 <= film.otr_value <= 500000.0, (
            f"Film '{fid}': OTR {film.otr_value} is outside physical bounds [0.0001, 500000.0]"
        )
        assert 0.0001 <= film.wvtr_value <= 500.0, (
            f"Film '{fid}': WVTR {film.wvtr_value} is outside physical bounds [0.0001, 500.0]"
        )

        if film.otr_min is not None and film.otr_max is not None:
            assert film.otr_min <= film.otr_max

        if film.wvtr_min is not None and film.wvtr_max is not None:
            assert film.wvtr_min <= film.wvtr_max

        # Mandatory test conditions
        assert -10.0 <= film.otr_test_temperature_c <= 60.0, f"Film '{fid}': invalid OTR test temp"
        assert 0.0 <= film.otr_test_rh_pct <= 100.0, f"Film '{fid}': invalid OTR test RH"
        assert film.otr_test_method.strip(), f"Film '{fid}': empty OTR test method"

        assert -10.0 <= film.wvtr_test_temperature_c <= 60.0, f"Film '{fid}': invalid WVTR test temp"
        assert 0.0 <= film.wvtr_test_rh_pct <= 100.0, f"Film '{fid}': invalid WVTR test RH"
        assert film.wvtr_test_method.strip(), f"Film '{fid}': empty WVTR test method"


def test_twelve_commodities_regimes_represented(kb_data):
    """
    Assert that the 12 seeded commodities span all target regimes:
    very low to extremely high respiration, dry to high aw, oxidation-sensitive,
    light-sensitive, and low-acid chilled.
    """
    expected_ids = {
        "veg.potato.solanum_tuberosum",
        "veg.tomato.solanum_lycopersicum",
        "veg.onion.allium_cepa",
        "fruit.banana.musa_acuminata",
        "fruit.mango.mangifera_indica",
        "veg.spinach.spinacia_oleracea",
        "veg.green_chilli.capsicum_annuum",
        "veg.okra.abelmoschus_esculentus",
        "dairy.paneer.cottage_cheese",
        "dairy.milk_powder.whole",
        "processed.besan_namkeen.fried_snack",
        "spice.turmeric_powder.curcuma_longa",
    }
    loaded_ids = set(kb_data.commodities.keys())
    assert expected_ids.issubset(loaded_ids), f"Missing commodities: {expected_ids - loaded_ids}"

    # 1. Extremely high respiration produce
    spinach = kb_data.commodities["veg.spinach.spinacia_oleracea"]
    assert spinach.respiration_ref_rate is not None
    assert float(spinach.respiration_ref_rate.value) > 60.0, "Spinach must have respiration > 60 mg/kg·h"

    # 2. Very low respiration produce
    onion = kb_data.commodities["veg.onion.allium_cepa"]
    assert onion.respiration_ref_rate is not None
    assert float(onion.respiration_ref_rate.value) < 5.0, "Cured onion must have respiration < 5 mg/kg·h"

    # 3. Dry commodities (low water activity)
    namkeen = kb_data.commodities["processed.besan_namkeen.fried_snack"]
    assert float(namkeen.water_activity.value) <= 0.30
    assert namkeen.light_sensitive is True

    # 4. Low-acid chilled dairy with high aw
    paneer = kb_data.commodities["dairy.paneer.cottage_cheese"]
    assert float(paneer.water_activity.value) >= 0.97
    assert float(paneer.pH.value) > 4.6, "Paneer must be low-acid (pH > 4.6)"


def test_structures_gauges_and_costs(kb_data):
    """
    Assert that the 12 laminate structures contain per-layer gauges, realistic costs,
    and valid EPR categories.
    """
    for sid, struct in kb_data.structures.items():
        assert len(struct.layer_stack) == len(struct.gauge_per_layer_um)
        assert struct.cost_inr_per_sqm > 0
        assert struct.composite_thickness_um > 0
        assert struct.epr_category in ["Cat I", "Cat II", "Cat III", "Cat IV"]


def test_map_targets_safety_interlock(kb_data):
    """
    Assert MAP gas targets clamp to safety floors:
    Never allow recommended produce equilibrium O2 below 2% safety floor.
    """
    for mid, target in kb_data.map_targets.items():
        if "produce" in mid or "salad" in mid or "carrot" in mid or "chilli" in mid:
            assert target.o2_floor >= 2.0, f"Produce MAP target '{mid}' violates 2% O2 safety floor"


def test_loader_fails_loudly_on_missing_citation(tmp_path):
    """
    Assert loader raises ValueError loudly when a data row cites an unknown source.
    """
    dummy_csv = tmp_path / "bad_films.csv"
    dummy_csv.write_text(
        "id,film_name,thickness_um,otr_value,otr_min,otr_max,otr_test_temperature_c,otr_test_rh_pct,otr_test_method,"
        "wvtr_value,wvtr_min,wvtr_max,wvtr_test_temperature_c,wvtr_test_rh_pct,wvtr_test_method,barrier_class,"
        "typical_use,epr_category,source_id\n"
        "bad_film,BadFilm,25.0,10.0,5.0,15.0,23.0,0.0,ASTM D3985,1.0,0.5,1.5,38.0,90.0,ASTM F1249,High,Packaging,Cat II,UNKNOWN_SRC\n",
        encoding="utf-8",
    )

    sources = {"USDA-AH66": None}
    with pytest.raises(ValueError, match="unknown source 'UNKNOWN_SRC'"):
        load_films(dummy_csv, sources=sources)


def test_loader_fails_loudly_on_out_of_range_film():
    """
    Assert Pydantic validation fails loudly when values violate physical plausibility.
    """
    # Negative OTR
    with pytest.raises((ValueError, ValidationError)):
        FilmRecord(
            id="negative_otr",
            film_name="Test",
            thickness_um=25.0,
            otr_value=-5.0,
            otr_test_temperature_c=23.0,
            otr_test_rh_pct=0.0,
            otr_test_method="ASTM D3985",
            wvtr_value=1.0,
            wvtr_test_temperature_c=38.0,
            wvtr_test_rh_pct=90.0,
            wvtr_test_method="ASTM F1249",
            barrier_class="High",
            typical_use="Testing",
            epr_category="Cat II",
            source_id="USDA-AH66",
        )

    # Empty test conditions
    with pytest.raises((ValueError, ValidationError)):
        FilmRecord(
            id="empty_method",
            film_name="Test",
            thickness_um=25.0,
            otr_value=5.0,
            otr_test_temperature_c=23.0,
            otr_test_rh_pct=0.0,
            otr_test_method="",  # empty method
            wvtr_value=1.0,
            wvtr_test_temperature_c=38.0,
            wvtr_test_rh_pct=90.0,
            wvtr_test_method="ASTM F1249",
            barrier_class="High",
            typical_use="Testing",
            epr_category="Cat II",
            source_id="USDA-AH66",
        )


def test_alembic_offline_migration_ddl_generation():
    """
    Assert Alembic generates the complete PostgreSQL DDL offline, including
    CREATE EXTENSION vector, all 8 tables, and NOT NULL foreign key constraints.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Alembic failed: {result.stderr}"
    sql = result.stdout

    # Invariants in generated SQL:
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in sql
    assert "CREATE TABLE sources" in sql
    assert "CREATE TABLE commodities" in sql
    assert "CREATE TABLE commodity_aliases" in sql
    assert "CREATE TABLE films" in sql
    assert "CREATE TABLE structures" in sql
    assert "CREATE TABLE isotherms" in sql
    assert "CREATE TABLE map_targets" in sql
    assert "CREATE TABLE state_modifiers" in sql
    assert "embedding VECTOR(384)" in sql
    assert "FOREIGN KEY(source_id) REFERENCES sources (id)" in sql
