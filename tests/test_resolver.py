"""
Comprehensive unit and acceptance tests for the Aavaran Resolver Layer.

Validates Section 4 of BLUEPRINT.md:
- Demo acceptance test: "potato", "cut", 48h elapsed, Mumbai, September
  -> L2 resolution, 80 <= effective respiration <= 200 mg CO2/kg·h, >= 5 ledger rows.
- Full hierarchical ladder degradation (L0 -> L1 -> L2 -> L3 -> L4).
- Conservative-end rule enforcement.
- Priority environment resolution (Measured -> Sensor -> Climatology -> Default).
- Multi-leg journey worst-leg determination.
- State modifier interactions and Q10 shelf-life consumption.
- 2,000-draw Monte Carlo uncertainty propagation and Value of Information.
"""

from __future__ import annotations

from engine.resolver.environment import (
    JourneyLeg,
    resolve_environment,
    resolve_multi_leg_journey,
)
from engine.resolver.hierarchy import (
    ResolutionResult,
    resolve_commodity,
)
from engine.resolver.uncertainty import (
    propagate,
    value_of_information,
)
from engine.types import (
    ResolutionLevel,
    SourceType,
)


class TestDemoAcceptance:
    """The headline acceptance test from Section 4.3 of BLUEPRINT.md."""

    def test_cut_potato_mumbai_september_acceptance(self):
        """
        Scenario: "potato, cut two days ago, sitting in a Mumbai shed"
        Requirements:
        - Resolution level is L2 (commodity species).
        - Modifiers applied (cut modifier x3-7).
        - Effective respiration rate is between 80 and 200 mg CO2/kg·h.
        - Assumptions ledger contains at least 5 entries with source and confidence.
        """
        res: ResolutionResult = resolve_commodity(
            query="potato",
            state="cut",
            hours_since_cut=48,
            location="Mumbai",
            month="September",
            storage_type="shed",
        )

        # 1. Level must be L2
        assert res.level == ResolutionLevel.L2
        assert res.confidence >= 0.80

        # 2. Modifiers must be applied
        assert res.modifier_result is not None
        assert "cut" in res.modifier_result.states_applied
        assert res.modifier_result.respiration_multiplier_range == (3.0, 7.0)
        assert res.modifier_result.requires_antifog is True

        # 3. Effective respiration rate must fall in [80, 200] mg CO2/kg·h
        assert res.effective_respiration_rate is not None
        assert 80.0 <= res.effective_respiration_rate <= 200.0

        # Also check range bounds
        assert res.effective_respiration_range is not None
        low_r, high_r = res.effective_respiration_range
        assert 80.0 <= low_r <= 200.0
        assert 80.0 <= high_r <= 200.0

        # 4. Assumptions ledger must contain at least 5 structured entries
        assert len(res.assumptions) >= 5

        # Check each assumption has provenance fields
        for asm in res.assumptions:
            assert asm.source_id is not None
            assert asm.source_type is not None
            assert asm.confidence is not None
            assert 0.0 <= asm.confidence <= 1.0

        # Verify presence of the core required fields
        source_ids = [a.source_id for a in res.assumptions]
        assert "IFCT-2017" in source_ids
        assert "Open-Meteo-Climatology" in source_ids

        # 5. Elapsed life must be computed
        assert res.elapsed_life is not None
        assert res.elapsed_life.hours_elapsed == 48.0
        assert res.elapsed_life.consumed_equivalent_days > 0.0

        # 6. Conservative adjustments ledger must note respiration conservatism
        assert len(res.conservative_adjustments) >= 1
        assert any("respiration" in adj.lower() for adj in res.conservative_adjustments)


class TestHierarchyLadder:
    """Test degradation across L0 -> L1 -> L2 -> L3 -> L4."""

    def test_level_0_user_measured_override(self):
        """Supplying direct physical measurements yields L0 with confidence 1.0."""
        res = resolve_commodity(
            query="potato",
            user_measured={
                "moisture_pct": 82.5,
                "water_activity": 0.975,
            },
        )
        assert res.level == ResolutionLevel.L0
        assert res.profile.moisture_pct.value == 82.5
        assert res.profile.moisture_pct.confidence == 1.0
        assert res.profile.moisture_pct.resolution_level == ResolutionLevel.L0
        assert res.profile.moisture_pct.source_type == SourceType.MEASURED

    def test_level_1_cultivar_resolution(self):
        """Recognized cultivars resolve to L1 with confidence ~0.90."""
        res = resolve_commodity(query="kufri jyoti potato")
        assert res.level == ResolutionLevel.L1
        assert res.confidence == 0.90
        assert "kufri_jyoti" in res.profile.commodity_id
        assert res.profile.moisture_pct.value == 80.0

        res_mango = resolve_commodity(query="Alphonso Mango")
        assert res_mango.level == ResolutionLevel.L1
        assert "alphonso" in res_mango.profile.commodity_id

    def test_level_2_multilingual_commodity_resolution(self):
        """Recognized commodity names in English and Indian languages resolve to L2."""
        for name in ["potato", "aloo", "batata", "alu"]:
            res = resolve_commodity(query=name)
            assert res.level == ResolutionLevel.L2
            assert "potato" in res.profile.commodity_id

        res_tomato = resolve_commodity(query="tomato")
        assert res_tomato.level == ResolutionLevel.L2
        assert "tomato" in res_tomato.profile.commodity_id

    def test_level_3_group_median_resolution(self):
        """Uncatalogued species belonging to a known group resolve to L3 medians."""
        res_yam = resolve_commodity(query="yam")
        assert res_yam.level == ResolutionLevel.L3
        assert res_yam.confidence == 0.60
        assert res_yam.profile.group == "root_tuber"

        res_greens = resolve_commodity(query="methi greens")
        assert res_greens.level == ResolutionLevel.L3
        assert res_greens.confidence == 0.60
        assert res_greens.profile.group == "leafy_green"

    def test_level_4_class_envelope_never_fails(self):
        """Completely unknown food strings fall back to L4 envelope and NEVER fail."""
        res = resolve_commodity(query="intergalactic_extraterrestrial_fungus_xyz")
        assert res.level == ResolutionLevel.L4
        assert res.confidence <= 0.40
        assert res.profile is not None
        assert res.profile.moisture_pct is not None
        assert res.profile.water_activity is not None

    def test_conservative_end_rule_flag(self):
        """Conservative-end rule selects upper respiration bound when enabled."""
        res_conservative = resolve_commodity(
            query="potato",
            state="cut",
            location="Mumbai",
            month="September",
            apply_conservative_rule=True,
        )
        res_nominal = resolve_commodity(
            query="potato",
            state="cut",
            location="Mumbai",
            month="September",
            apply_conservative_rule=False,
        )
        assert (
            res_conservative.effective_respiration_rate
            > res_nominal.effective_respiration_rate
        )


class TestEnvironmentResolver:
    """Test the 4-tier environmental priority resolution."""

    def test_priority_1_user_measurement(self):
        env = resolve_environment(temp_c=18.5, rh_pct=55.0)
        assert env.temperature.value == 18.5
        assert env.temperature.confidence == 1.0
        assert env.temperature.source_type == SourceType.MEASURED
        assert env.relative_humidity.value == 55.0
        assert env.relative_humidity.confidence == 1.0

    def test_priority_2_sensor_telemetry(self):
        env = resolve_environment(
            sensor_data={
                "temperature_c": 12.0,
                "temperature_min_c": 10.0,
                "temperature_max_c": 14.0,
                "relative_humidity_pct": 88.0,
            }
        )
        assert env.temperature.value == 12.0
        assert env.temperature.confidence == 0.95
        assert env.temperature.resolution_level == ResolutionLevel.L1

    def test_priority_3_climatology_mumbai_september(self):
        env = resolve_environment(location="Mumbai", month="September")
        assert env.temperature.range_low == 28.0
        assert env.temperature.range_high == 31.0
        assert env.relative_humidity.range_low == 78.0
        assert env.relative_humidity.range_high == 85.0
        assert env.temperature.confidence == 0.55
        assert env.temperature.source_type == SourceType.STANDARD

    def test_priority_4_storage_default(self):
        env_chilled = resolve_environment(storage_type="chilled")
        assert env_chilled.temperature.value == 4.0
        assert env_chilled.temperature.confidence == 0.40

        env_frozen = resolve_environment(storage_type="frozen")
        assert env_frozen.temperature.value == -18.0

    def test_multi_leg_journey_selects_worst_leg(self):
        """Journey with ambient leg and chilled leg chooses ambient as worst."""
        legs = [
            JourneyLeg(
                leg_id="cold_transit",
                storage_type="chilled",
                duration_hours=24.0,
            ),
            JourneyLeg(
                leg_id="mumbai_ambient",
                location="Mumbai",
                month="September",
                storage_type="shed",
                duration_hours=12.0,
            ),
            JourneyLeg(
                leg_id="retail_display",
                temp_c=22.0,
                rh_pct=65.0,
                duration_hours=48.0,
            ),
        ]
        worst_env = resolve_multi_leg_journey(legs)
        # Mumbai ambient / shed (30 °C) is harsher than chilled (4 °C) or retail (22 °C)
        assert worst_env.temperature.value >= 29.0


class TestModifiersAndElapsedLife:
    """Test physiological modifiers and Q10 kinetics."""

    def test_cut_modifier_effects(self):
        res = resolve_commodity(query="potato", state="cut")
        assert res.modifier_result.requires_antifog is True
        assert res.modifier_result.forces_chilled_chain is True
        assert "enzymatic_browning" in res.profile.failure_modes

    def test_bruised_modifier_effects(self):
        res = resolve_commodity(query="potato", state="bruised")
        assert res.modifier_result.respiration_multiplier_range == (1.3, 2.0)
        assert "rot_entry_point" in res.profile.failure_modes

    def test_cured_modifier_extends_life(self):
        res = resolve_commodity(query="potato", state="cured")
        r_min, r_max = res.modifier_result.respiration_multiplier_range
        assert r_min < 1.0 and r_max < 1.0

    def test_blanched_modifier_stops_respiration(self):
        res = resolve_commodity(query="spinach", state="blanched")
        assert res.modifier_result.respiration_multiplier_range == (0.0, 0.0)

    def test_consume_elapsed_life_q10_kinetics(self):
        """Warm abuse (30 °C) vs ref (10 °C) with Q10=2 accelerates consumption 4x."""
        res = resolve_commodity(
            query="potato",
            hours_since_harvest=24.0,
            location="Mumbai",
            month="September",
        )
        assert res.elapsed_life is not None
        assert res.elapsed_life.acceleration_factor > 1.0
        assert res.elapsed_life.consumed_equivalent_days > 1.0


class TestUncertaintyAndVoI:
    """Test 2,000-draw Monte Carlo and sensitivity variance reduction."""

    def test_monte_carlo_propagation_distribution(self):
        res = resolve_commodity(
            query="potato",
            state="cut",
            location="Mumbai",
            month="September",
        )
        unc = propagate(res.profile, res.resolved_environment, n_draws=2000, seed=42)

        assert unc.n_draws == 2000
        assert unc.days_p10 > 0.0
        assert unc.days_p10 <= unc.days_p50 <= unc.days_p90
        assert unc.limiting_mechanism in [
            "microbial_spoilage",
            "physiological_senescence",
        ]

        # Verify conversion to standard ShelfLifeResult
        sl_res = unc.to_shelf_life_result()
        assert sl_res.days_p50 == unc.days_p50
        assert sl_res.limiting_mechanism == unc.limiting_mechanism

    def test_value_of_information_variance_reduction(self):
        res = resolve_commodity(
            query="potato",
            state="cut",
            location="Mumbai",
            month="September",
        )
        voi = value_of_information(
            res.profile, res.resolved_environment, n_draws=1000, seed=42
        )

        assert voi.variance_reduction >= 0.0
        assert voi.field in [
            "storage_temperature",
            "relative_humidity",
            "water_activity",
            "pH",
        ]
        assert "reduce shelf-life uncertainty" in voi.description
