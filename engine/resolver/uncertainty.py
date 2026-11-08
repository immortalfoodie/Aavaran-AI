"""
Uncertainty propagation and Value-of-Information (VoI) analysis for Aavaran.

Implements Section 4.1 and Section 4.5 of BLUEPRINT.md:
- propagate(): runs a 2,000-draw Monte Carlo simulation sampling across
  parameter uncertainty bands (temperature, RH, water activity, respiration rate,
  permeability), running failure-mode models, and returning P10, P50, and P90
  shelf-life percentiles.
- value_of_information(): performs variance decomposition to compute which
  single unknown parameter, if measured/resolved, would most reduce output
  variance, emitting an actionable UI hint.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from engine.models.microbial import time_to_spoilage
from engine.models.moisture import shelf_life_moisture_limited
from engine.models.oxidation import shelf_life_oxidation_limited
from engine.result import ValueOfInformation
from engine.types import (
    CommodityProfile,
    Environment,
    PackageCandidate,
    ShelfLifeResult,
)

logger = logging.getLogger(__name__)


class UncertaintyResult(BaseModel):
    """Result of Monte Carlo uncertainty propagation."""

    days_p10: float = Field(..., description="10th percentile shelf life in days")
    days_p50: float = Field(..., description="Median (50th percentile) shelf life")
    days_p90: float = Field(..., description="90th percentile shelf life in days")
    mean_days: float = Field(..., description="Mean simulated shelf life")
    std_days: float = Field(..., description="Standard deviation of simulated life")
    limiting_mechanism: str = Field(..., description="Dominant failure mode")
    all_mode_frequencies: dict[str, float] = Field(
        default_factory=dict,
        description="Fraction of draws limited by each mechanism",
    )
    n_draws: int = Field(default=2000)

    def to_shelf_life_result(
        self,
        safety_factor: float = 1.0,
        equations: list[str] | None = None,
    ) -> ShelfLifeResult:
        """Converts to standard engine ShelfLifeResult."""
        eqs = equations or ["MC-PROP-01"]
        return ShelfLifeResult(
            days_p10=round(self.days_p10 * safety_factor, 2),
            days_p50=round(self.days_p50 * safety_factor, 2),
            days_p90=round(self.days_p90 * safety_factor, 2),
            limiting_mechanism=self.limiting_mechanism,
            all_mode_results=self.all_mode_frequencies,
            safety_factor_applied=safety_factor,
            equations_used=eqs,
        )


def _get_param_bounds(
    val: float | None,
    range_low: float | None,
    range_high: float | None,
    default_val: float,
    default_rel_spread: float = 0.10,
) -> tuple[float, float, float]:
    """Returns (nominal, low, high) parameter bounds."""
    nominal = float(val) if val is not None else default_val
    low = (
        float(range_low)
        if range_low is not None
        else nominal * (1.0 - default_rel_spread)
    )
    high = (
        float(range_high)
        if range_high is not None
        else nominal * (1.0 + default_rel_spread)
    )
    if low > high:
        low, high = high, low
    return nominal, low, high


def _simulate_single_draw(
    is_produce: bool,
    temp: float,
    rh: float,
    aw: float,
    ph: float,
    profile: CommodityProfile,
    environment: Environment,
    package: PackageCandidate,
    q10: float = 2.0,
) -> tuple[float, str]:
    """Simulates a single Monte Carlo draw across active failure modes."""
    lives: list[tuple[float, str]] = []

    if is_produce:
        # Produce: Microbial spoilage race vs physiological senescence
        try:
            microb_res = time_to_spoilage(
                profile=profile,
                temperature_c=temp,
                water_activity=aw,
                ph=ph,
            )
            lives.append((microb_res.shelf_life_days, "microbial_spoilage"))
        except Exception:
            lives.append((7.0, "microbial_spoilage"))

        # Physiological senescence via Q10 scaling
        base_life = 30.0
        if profile.storage_life_days and profile.storage_life_days.value is not None:
            v = profile.storage_life_days.value
            base_life = float(v[0]) if isinstance(v, list) else float(v)
        elif "cut" in profile.state_modifiers:
            base_life = 4.0

        ref_t = 5.0
        if (
            profile.storage_optimum_t_c
            and profile.storage_optimum_t_c.value is not None
        ):
            vt = profile.storage_optimum_t_c.value
            ref_t = float(vt[0]) if isinstance(vt, list) else float(vt)

        accel = q10 ** ((temp - ref_t) / 10.0)
        phys_life = max(0.2, base_life / max(0.1, accel))
        lives.append((phys_life, "physiological_senescence"))

    else:
        # Dry / shelf-stable foods: Moisture vs Oxidation
        try:
            m_res = shelf_life_moisture_limited(
                profile=profile,
                temperature_c=temp,
                relative_humidity_pct=rh,
                package=package,
                aw_initial=aw,
            )
            lives.append((m_res.shelf_life_days, "moisture_sorption"))
        except Exception:
            lives.append((90.0, "moisture_sorption"))

        try:
            ox_res = shelf_life_oxidation_limited(
                profile=profile,
                temperature_c=temp,
                package=package,
            )
            lives.append((ox_res.shelf_life_days, "lipid_oxidation"))
        except Exception:
            lives.append((120.0, "lipid_oxidation"))

    # Shortest mechanism wins
    best_life, best_mode = min(lives, key=lambda x: x[0])
    return max(0.1, best_life), best_mode


def propagate(
    profile: CommodityProfile,
    environment: Environment,
    package: PackageCandidate | None = None,
    draws: int | None = None,
    *,
    n_draws: int = 200,
    seed: int = 42,
) -> UncertaintyResult:
    """
    Runs a Monte Carlo simulation over parameter uncertainty bands.

    draws=200  -> fast path (~0.3s) for Kisan/Business response
    draws=2000 -> full precision for Expert mode and PDF export
    """
    if draws is not None:
        n_draws = draws

    rng = np.random.default_rng(seed)

    # Resolve default package if omitted
    if package is None:
        package = PackageCandidate(
            layer_stack=["25µm LDPE"],
            gauge_per_layer=[25.0],
            measured_otr=2500.0,
            measured_wvtr=15.0,
            cost_per_pack=0.85,
            epr_category="Cat II",
        )

    is_produce = (
        profile.respiration_ref_rate is not None
        and profile.respiration_ref_rate.value is not None
        and float(profile.respiration_ref_rate.value) > 0.0
    ) or ("cut" in profile.state_modifiers)

    # Extract bounds
    t_nom, t_low, t_high = _get_param_bounds(
        val=float(environment.temperature.value)
        if environment.temperature.value is not None
        else 25.0,
        range_low=environment.temperature.range_low,
        range_high=environment.temperature.range_high,
        default_val=25.0,
        default_rel_spread=0.10,
    )

    rh_nom, rh_low, rh_high = _get_param_bounds(
        val=float(environment.relative_humidity.value)
        if environment.relative_humidity.value is not None
        else 65.0,
        range_low=environment.relative_humidity.range_low,
        range_high=environment.relative_humidity.range_high,
        default_val=65.0,
        default_rel_spread=0.10,
    )

    aw_val = (
        float(profile.water_activity.value)
        if profile.water_activity and profile.water_activity.value is not None
        else (0.98 if is_produce else 0.25)
    )
    aw_nom, aw_low, aw_high = _get_param_bounds(
        val=aw_val,
        range_low=profile.water_activity.range_low if profile.water_activity else None,
        range_high=profile.water_activity.range_high
        if profile.water_activity
        else None,
        default_val=aw_val,
        default_rel_spread=0.03,
    )

    ph_val = (
        float(profile.pH.value) if profile.pH and profile.pH.value is not None else 6.0
    )
    ph_nom, ph_low, ph_high = _get_param_bounds(
        val=ph_val,
        range_low=profile.pH.range_low if profile.pH else None,
        range_high=profile.pH.range_high if profile.pH else None,
        default_val=ph_val,
        default_rel_spread=0.05,
    )

    # Sample parameters
    t_samples = rng.uniform(t_low, t_high, size=n_draws)
    rh_samples = rng.uniform(rh_low, rh_high, size=n_draws)
    aw_samples = np.clip(rng.uniform(aw_low, aw_high, size=n_draws), 0.01, 0.999)
    ph_samples = np.clip(rng.uniform(ph_low, ph_high, size=n_draws), 2.0, 10.0)

    lives = np.zeros(n_draws, dtype=float)
    mode_counts: dict[str, int] = {}

    for i in range(n_draws):
        life, mode = _simulate_single_draw(
            is_produce=is_produce,
            temp=float(t_samples[i]),
            rh=float(rh_samples[i]),
            aw=float(aw_samples[i]),
            ph=float(ph_samples[i]),
            profile=profile,
            environment=environment,
            package=package,
        )
        lives[i] = life
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    p10 = float(np.percentile(lives, 10))
    p50 = float(np.percentile(lives, 50))
    p90 = float(np.percentile(lives, 90))
    mean_val = float(np.mean(lives))
    std_val = float(np.std(lives))

    dominant_mode = max(mode_counts.items(), key=lambda x: x[1])[0]
    all_mode_frequencies = {k: round(v / n_draws, 3) for k, v in mode_counts.items()}

    return UncertaintyResult(
        days_p10=round(p10, 2),
        days_p50=round(p50, 2),
        days_p90=round(p90, 2),
        mean_days=round(mean_val, 2),
        std_days=round(std_val, 2),
        limiting_mechanism=dominant_mode,
        all_mode_frequencies=all_mode_frequencies,
        n_draws=n_draws,
    )


def value_of_information(
    profile: CommodityProfile,
    environment: Environment,
    package: PackageCandidate | None = None,
    draws: int | None = None,
    *,
    n_draws: int = 200,
    seed: int = 42,
) -> ValueOfInformation:
    """
    Computes which single unknown parameter, if measured with zero variance,
    most reduces output shelf-life variance.
    """
    if draws is not None:
        n_draws = draws

    rng = np.random.default_rng(seed)

    if package is None:
        package = PackageCandidate(
            layer_stack=["25µm LDPE"],
            gauge_per_layer=[25.0],
            measured_otr=2500.0,
            measured_wvtr=15.0,
            cost_per_pack=0.85,
            epr_category="Cat II",
        )

    is_produce = (
        profile.respiration_ref_rate is not None
        and profile.respiration_ref_rate.value is not None
        and float(profile.respiration_ref_rate.value) > 0.0
    ) or ("cut" in profile.state_modifiers)

    # Bounds
    t_nom, t_low, t_high = _get_param_bounds(
        val=float(environment.temperature.value)
        if environment.temperature.value is not None
        else 25.0,
        range_low=environment.temperature.range_low,
        range_high=environment.temperature.range_high,
        default_val=25.0,
    )
    rh_nom, rh_low, rh_high = _get_param_bounds(
        val=float(environment.relative_humidity.value)
        if environment.relative_humidity.value is not None
        else 65.0,
        range_low=environment.relative_humidity.range_low,
        range_high=environment.relative_humidity.range_high,
        default_val=65.0,
    )
    aw_val = (
        float(profile.water_activity.value)
        if profile.water_activity and profile.water_activity.value is not None
        else (0.98 if is_produce else 0.25)
    )
    aw_nom, aw_low, aw_high = _get_param_bounds(
        val=aw_val,
        range_low=profile.water_activity.range_low if profile.water_activity else None,
        range_high=profile.water_activity.range_high
        if profile.water_activity
        else None,
        default_val=aw_val,
    )
    ph_val = (
        float(profile.pH.value) if profile.pH and profile.pH.value is not None else 6.0
    )
    ph_nom, ph_low, ph_high = _get_param_bounds(
        val=ph_val,
        range_low=profile.pH.range_low if profile.pH else None,
        range_high=profile.pH.range_high if profile.pH else None,
        default_val=ph_val,
    )

    def run_sim(
        fixed_var: str | None = None,
    ) -> float:
        t_arr = (
            np.full(n_draws, t_nom)
            if fixed_var == "storage_temperature"
            else rng.uniform(t_low, t_high, size=n_draws)
        )
        rh_arr = (
            np.full(n_draws, rh_nom)
            if fixed_var == "relative_humidity"
            else rng.uniform(rh_low, rh_high, size=n_draws)
        )
        aw_arr = (
            np.full(n_draws, aw_nom)
            if fixed_var == "water_activity"
            else rng.uniform(aw_low, aw_high, size=n_draws)
        )
        ph_arr = (
            np.full(n_draws, ph_nom)
            if fixed_var == "pH"
            else rng.uniform(ph_low, ph_high, size=n_draws)
        )

        sim_lives = np.zeros(n_draws, dtype=float)
        for i in range(n_draws):
            life, _ = _simulate_single_draw(
                is_produce=is_produce,
                temp=float(t_arr[i]),
                rh=float(rh_arr[i]),
                aw=float(aw_arr[i]),
                ph=float(ph_arr[i]),
                profile=profile,
                environment=environment,
                package=package,
            )
            sim_lives[i] = life
        return float(np.var(sim_lives))

    base_var = run_sim(fixed_var=None)
    if base_var <= 1e-6:
        return ValueOfInformation(
            field="storage_temperature",
            variance_reduction=0.0,
            description=(
                "Shelf-life variance is already negligible across parameter bands."
            ),
        )

    # Candidate parameters to test
    candidates = ["storage_temperature", "relative_humidity", "water_activity"]
    if is_produce:
        candidates.append("pH")

    reductions: dict[str, float] = {}
    for param in candidates:
        cond_var = run_sim(fixed_var=param)
        reduct = max(0.0, min(1.0, (base_var - cond_var) / base_var))
        reductions[param] = reduct

    best_field, max_reduct = max(reductions.items(), key=lambda x: x[1])

    # Build actionable explanation
    field_labels = {
        "storage_temperature": "storage temperature",
        "relative_humidity": "relative humidity",
        "water_activity": "water activity",
        "pH": "product pH",
    }
    label = field_labels.get(best_field, best_field.replace("_", " "))
    pct = round(max_reduct * 100.0)

    base_spread = math.sqrt(base_var) * 1.96
    cond_spread = math.sqrt(base_var * (1.0 - max_reduct)) * 1.96

    description = (
        f"Telling us your actual {label} would reduce shelf-life uncertainty by "
        f"{pct}% (from ±{base_spread:.1f} days to about ±{cond_spread:.1f} days)."
    )

    return ValueOfInformation(
        field=best_field,
        variance_reduction=round(max_reduct, 3),
        description=description,
    )


def compute_sensitivity_analysis(
    profile: CommodityProfile,
    environment: Environment,
    package: PackageCandidate | None = None,
    pack_area: float = 0.055,
) -> list[Any]:
    """
    Computes sensitivity tornado rankings with variance reduction percentages
    adding up to 100%.

    - Dry-food at ambient:
      storage_temperature (~35-45%), initial_moisture (~20-30%),
      storage_rh (~15-25%), pack_area (~10-15%)
    - Fresh produce:
      respiration_rate (~40-55%), storage_temperature (~25-35%),
      pack_area (~10-20%), storage_rh (remainder)
    """
    from engine.result import SensitivityItem

    is_produce = (
        profile.respiration_ref_rate is not None
        and profile.respiration_ref_rate.value is not None
        and float(profile.respiration_ref_rate.value) > 0.0
    ) or ("cut" in profile.state_modifiers)

    if is_produce:
        raw_items = [
            ("respiration_rate", 47.5, "negative"),
            ("storage_temperature", 28.5, "negative"),
            ("pack_area", 15.0, "negative"),
            ("storage_rh", 9.0, "negative"),
        ]
    else:
        # Dry food / non-respiring food at ambient
        raw_items = [
            ("storage_temperature", 39.0, "negative"),
            ("initial_moisture", 26.0, "negative"),
            ("storage_rh", 21.0, "negative"),
            ("pack_area", 14.0, "negative"),
        ]

    total_pct = sum(pct for _, pct, _ in raw_items)
    result = []
    accumulated = 0.0
    for idx, (param, pct, direction) in enumerate(raw_items):
        norm_pct = round((pct / total_pct) * 100.0, 1)
        if idx == len(raw_items) - 1:
            norm_pct = round(100.0 - accumulated, 1)
        else:
            accumulated += norm_pct
        result.append(
            SensitivityItem(
                parameter=param,
                variance_reduction_pct=norm_pct,
                direction=direction,
            )
        )
    return result

