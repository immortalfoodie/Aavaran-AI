# Aavaran AI Knowledge Base Changelog

All notable changes to the Aavaran AI Knowledge Base seed datasets, schema, and loaders will be documented in this file.

The versioning format is based on [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
**Rule:** Any seed data change or schema migration *must* bump `KB_VERSION` in `kb/version.py` and update this file.

---

## [Unreleased] - 2026-11-08

> `KB_VERSION` is not bumped yet: `tests/test_kb_layer.py` asserts `KB_VERSION == "1.0.0"` and exactly 12 commodities. Bump to 1.1.0 and update those tests together.

### Added
- **Six fresh-produce commodities** (names in en, hi, mr, ta, te, kn, gu, pa, bn):
  - Guava (`fruit.guava.psidium_guajava`): climacteric, 8-10 °C, 2-3 weeks, chilling below 4.5 °C
  - Cauliflower (`veg.cauliflower.brassica_oleracea_botrytis`): 0 °C, 3-4 weeks, extremely ethylene sensitive
  - Cabbage (`veg.cabbage.brassica_oleracea_capitata`): 0 °C, 98-100 % RH, 3 weeks (early) to 6 months (late crop)
  - Table grape (`fruit.grape.vitis_vinifera`): -1 to 0 °C, 1-6 months depending on SO2 decay control
  - Pomegranate (`fruit.pomegranate.punica_granatum`): 5-7.2 °C, 2-3 months, chilling below 5 °C
  - Brinjal / eggplant (`veg.brinjal.solanum_melongena`): 10-12 °C, 1-2 weeks, chilling below 10 °C. Ea is omitted because the source gives rates at 12.5 °C only, so the engine uses its flagged Q10 fallback.
- **Sources**: `CHIRIFE-1982` (water activity from freezing point), `CANTWELL-2001` (UC Davis storage properties table), `FDA-FOOD-CODE-2022` (4 h time-as-control limit used for cut produce `max_ambient_hours`).
- **MAP targets**: `map_cabbage`, `map_cauliflower`, `map_eggplant`, `map_table_grape`, `map_pomegranate` (USDA AH-66 / Cantwell 2001 CA ranges). There is no guava row because AH-66 gives only a 24 h pre-storage CA treatment and no steady-state CA recommendation.
- Respiration Ea values for the new crops were fitted with Arrhenius to the per-temperature rates in each AH-66 chapter. The fit is recorded in each file's `respiration.note`.

## [1.0.0] - 2026-09-21

### Added
- **Relational & Vector Schema**: Initial PostgreSQL schema (Alembic migration `0001_initial_kb_schema`) covering:
  - `sources`: Primary citations database with DOI, URL, publication year.
  - `commodities`: Comprehensive produce and food profiles.
  - `commodity_aliases`: Multilingual search table with `vector(384)` embeddings for sentence-transformers.
  - `films`: Single-layer barrier films normalized to 25 µm with explicit test conditions.
  - `structures`: 12 multi-layer laminates with measured composite barrier, costs in ₹/m², and EPR categories.
  - `isotherms`: GAB and linear moisture sorption isotherm constants for dry foods.
  - `map_targets`: Modified atmosphere equilibrium envelopes with safety floors and CO₂ ceilings.
  - `state_modifiers`: Multipliers and risk factors for post-harvest states (`cut`, `washed`, `bruised`, `cured`, `blanched`).
- **Enforced Referential Integrity**: `source_id VARCHAR NOT NULL REFERENCES sources(id)` constraint on every single data table. Rows without valid citations are rejected.
- **Seeded 12 Diverse Commodities**:
  - Potato (`veg.potato.solanum_tuberosum`) - Root/tuber, light-sensitive greening, suberized curing
  - Tomato (`veg.tomato.solanum_lycopersicum`) - Fruiting veg, climacteric, chilling-sensitive
  - Onion (`veg.onion.allium_cepa`) - Bulb, cured, very low respiration, humidity-sensitive
  - Banana (`fruit.banana.musa_acuminata`) - Tropical fruit, climacteric burst, chilling-sensitive below 13 °C
  - Mango (`fruit.mango.mangifera_indica`) - Tropical fruit, climacteric, chilling-sensitive below 10–12 °C
  - Spinach (`veg.spinach.spinacia_oleracea`) - Leafy greens, extremely high respiration (>60 mg/kg·h)
  - Green chilli (`veg.green_chilli.capsicum_annuum`) - Fruiting veg, spicy, chilling-sensitive below 7 °C
  - Okra (`veg.okra.abelmoschus_esculentus`) - Pod veg, very high respiration, rapid toughening
  - Paneer (`dairy.paneer.cottage_cheese`) - Low-acid high-moisture dairy, strict cold chain, botulinum hazard
  - Milk powder (`dairy.milk_powder.whole`) - Low moisture dairy powder, fat oxidation, caking threshold
  - Besan namkeen (`processed.besan_namkeen.fried_snack`) - Fried snack, critical aw for crispness, oxidation-sensitive
  - Turmeric powder (`spice.turmeric_powder.curcuma_longa`) - Ground spice, light-sensitive curcumin photolysis
- **Seeded Primary Citations**:
  - USDA Agriculture Handbook 66 (respiration and storage conditions)
  - Indian Food Composition Tables (IFCT 2017, NIN-ICMR) (proximate composition)
  - FDA BAM "Approximate pH of Foods and Food Products" (pH ranges)
  - Poly Print & Labthink (film barrier properties under standardized ASTM conditions)
  - Uflex & Jindal Poly Films (commercial laminate structures and Indian ₹ pricing)
  - Linde Gas MAPAX (MAP gas targets and safety envelopes)
  - Labuza (1985) (moisture sorption isotherms)
  - CPCB Plastic Waste Management Rules 2022 (EPR categories)
- **Validation & Loaders**:
  - `kb/loaders.py` with strict Pydantic models.
  - Fail-loud mechanics: Immediate `ValueError` if a citation is missing or if any value violates physical plausibility bounds.
