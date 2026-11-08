"""
Environment resolver for Aavaran.

Resolves ambient storage and transit conditions in strict priority order:
1. User-supplied direct measurement (L0, confidence 1.0, MEASURED)
2. Attached sensor or telemetry logger data (L1, confidence 0.95, MEASURED)
3. Geolocation + month climatology (L2/L3, confidence 0.55, STANDARD)
4. Storage-type baseline default (L4, confidence 0.40, CLASS_DEFAULT)

Supports multi-leg journeys by selecting the harshest (worst) leg to ensure
conservative, food-safe package design.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from engine.types import (
    Environment,
    Provenance,
    ResolutionLevel,
    SourceType,
)

logger = logging.getLogger(__name__)

# Month name / abbreviation normalization to integer 1-12
MONTH_LOOKUP: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

CITY_ALIASES: dict[str, str] = {
    "bombay": "mumbai",
    "mumbai": "mumbai",
    "new delhi": "delhi",
    "delhi": "delhi",
    "ncr": "delhi",
    "bangalore": "bengaluru",
    "bengaluru": "bengaluru",
    "calcutta": "kolkata",
    "kolkata": "kolkata",
    "chennai": "chennai",
    "madras": "chennai",
    "hyderabad": "hyderabad",
    "pune": "pune",
    "poona": "pune",
    "nashik": "nashik",
    "nasik": "nashik",
    "shimla": "shimla",
    "simla": "shimla",
    "ahmedabad": "ahmedabad",
    "nagpur": "nagpur",
    "chandigarh": "chandigarh",
}

# Cached Open-Meteo / ERA5 / IMD 10-year monthly climatology:
# (temp_mean, temp_min, temp_max, rh_mean, rh_min, rh_max)
CLIMATOLOGY_DB: dict[
    str, dict[int, tuple[float, float, float, float, float, float]]
] = {
    "mumbai": {
        1: (24.0, 19.0, 31.0, 62.0, 52.0, 72.0),
        2: (25.5, 20.0, 32.0, 64.0, 53.0, 74.0),
        3: (28.0, 22.5, 33.5, 68.0, 56.0, 78.0),
        4: (30.0, 25.0, 34.5, 72.0, 60.0, 81.0),
        5: (31.5, 27.0, 35.0, 74.0, 63.0, 83.0),
        6: (30.5, 26.5, 33.5, 82.0, 75.0, 88.0),
        7: (28.5, 25.5, 31.0, 87.0, 82.0, 92.0),
        8: (28.0, 25.0, 30.5, 86.0, 80.0, 91.0),
        # September: 28-31 °C (mean 29.0), 78-85% RH (mean 82.0%)
        9: (29.0, 28.0, 31.0, 82.0, 78.0, 85.0),
        10: (29.5, 24.5, 34.0, 75.0, 65.0, 84.0),
        11: (27.5, 22.0, 33.5, 66.0, 55.0, 76.0),
        12: (25.0, 20.0, 32.0, 63.0, 52.0, 73.0),
    },
    "delhi": {
        1: (14.0, 8.0, 21.0, 75.0, 55.0, 92.0),
        2: (18.0, 11.0, 25.0, 65.0, 45.0, 85.0),
        3: (24.0, 16.0, 31.0, 52.0, 35.0, 70.0),
        4: (31.0, 22.0, 38.0, 36.0, 22.0, 50.0),
        5: (35.0, 26.0, 42.0, 35.0, 20.0, 52.0),
        6: (34.0, 28.0, 40.0, 55.0, 38.0, 72.0),
        7: (31.0, 27.0, 36.0, 75.0, 60.0, 88.0),
        8: (30.0, 26.0, 34.0, 78.0, 65.0, 90.0),
        9: (29.0, 24.0, 34.0, 68.0, 52.0, 82.0),
        10: (26.0, 19.0, 33.0, 55.0, 38.0, 72.0),
        11: (20.0, 13.0, 28.0, 60.0, 42.0, 78.0),
        12: (15.0, 8.0, 22.0, 72.0, 52.0, 90.0),
    },
    "bengaluru": {
        1: (21.0, 16.0, 28.0, 60.0, 45.0, 75.0),
        2: (24.0, 18.0, 31.0, 52.0, 38.0, 68.0),
        3: (27.0, 20.0, 34.0, 48.0, 32.0, 65.0),
        4: (28.0, 22.0, 34.0, 58.0, 42.0, 74.0),
        5: (27.0, 21.0, 33.0, 68.0, 52.0, 82.0),
        6: (24.5, 20.0, 29.5, 78.0, 65.0, 88.0),
        7: (24.0, 19.5, 28.5, 80.0, 68.0, 90.0),
        8: (24.0, 19.5, 28.5, 80.0, 68.0, 90.0),
        9: (24.5, 19.5, 29.0, 78.0, 64.0, 88.0),
        10: (24.0, 19.5, 28.5, 76.0, 62.0, 87.0),
        11: (22.5, 18.0, 27.5, 72.0, 58.0, 84.0),
        12: (21.0, 16.5, 26.5, 68.0, 52.0, 80.0),
    },
    "chennai": {
        1: (25.0, 21.0, 30.0, 74.0, 60.0, 85.0),
        2: (26.5, 22.0, 32.0, 72.0, 58.0, 84.0),
        3: (29.0, 24.0, 34.0, 72.0, 58.0, 84.0),
        4: (32.0, 27.0, 36.5, 73.0, 60.0, 85.0),
        5: (34.0, 28.5, 39.0, 66.0, 52.0, 80.0),
        6: (33.0, 27.5, 38.0, 62.0, 48.0, 75.0),
        7: (31.0, 26.0, 36.0, 68.0, 54.0, 80.0),
        8: (30.5, 25.5, 35.0, 70.0, 56.0, 82.0),
        9: (30.0, 25.5, 34.5, 75.0, 62.0, 86.0),
        10: (28.5, 24.5, 32.5, 80.0, 68.0, 90.0),
        11: (26.5, 23.0, 30.5, 82.0, 70.0, 92.0),
        12: (25.0, 22.0, 29.5, 78.0, 65.0, 88.0),
    },
    "kolkata": {
        1: (19.5, 13.0, 26.0, 68.0, 50.0, 85.0),
        2: (24.0, 17.0, 30.5, 62.0, 45.0, 80.0),
        3: (28.5, 22.0, 34.5, 62.0, 45.0, 80.0),
        4: (31.0, 25.0, 36.5, 70.0, 55.0, 84.0),
        5: (31.5, 26.0, 36.0, 76.0, 62.0, 88.0),
        6: (30.5, 26.5, 34.0, 82.0, 72.0, 92.0),
        7: (29.5, 26.0, 32.5, 86.0, 78.0, 94.0),
        8: (29.5, 26.0, 32.5, 86.0, 78.0, 94.0),
        9: (29.5, 25.5, 33.0, 83.0, 74.0, 91.0),
        10: (28.0, 23.5, 32.5, 75.0, 62.0, 87.0),
        11: (24.0, 18.5, 29.5, 68.0, 52.0, 82.0),
        12: (20.0, 14.0, 26.5, 68.0, 50.0, 84.0),
    },
    "pune": {
        1: (21.0, 13.0, 30.0, 52.0, 38.0, 68.0),
        2: (23.5, 15.0, 33.0, 45.0, 30.0, 60.0),
        3: (27.5, 18.0, 36.5, 38.0, 24.0, 52.0),
        4: (30.5, 21.5, 38.5, 42.0, 28.0, 58.0),
        5: (31.0, 23.0, 38.0, 55.0, 40.0, 70.0),
        6: (27.5, 22.5, 32.5, 74.0, 60.0, 86.0),
        7: (25.0, 21.5, 29.0, 84.0, 74.0, 92.0),
        8: (24.5, 21.0, 28.0, 84.0, 74.0, 92.0),
        9: (25.5, 21.0, 30.0, 80.0, 68.0, 90.0),
        10: (26.0, 19.0, 32.0, 65.0, 50.0, 80.0),
        11: (23.5, 16.0, 30.5, 58.0, 42.0, 72.0),
        12: (21.0, 13.0, 29.0, 55.0, 40.0, 70.0),
    },
    "nashik": {
        1: (20.0, 11.0, 29.0, 52.0, 36.0, 68.0),
        2: (22.5, 13.0, 32.0, 42.0, 28.0, 58.0),
        3: (26.5, 16.5, 36.0, 36.0, 22.0, 50.0),
        4: (30.0, 20.5, 38.5, 40.0, 26.0, 56.0),
        5: (31.0, 22.5, 38.5, 52.0, 36.0, 68.0),
        6: (27.5, 22.0, 32.5, 74.0, 60.0, 86.0),
        7: (24.5, 21.0, 28.0, 85.0, 75.0, 94.0),
        8: (24.0, 20.5, 27.5, 86.0, 76.0, 94.0),
        9: (25.0, 20.5, 29.5, 80.0, 68.0, 90.0),
        10: (25.5, 18.0, 32.0, 62.0, 48.0, 78.0),
        11: (23.0, 14.5, 30.5, 55.0, 40.0, 70.0),
        12: (20.5, 11.5, 29.0, 52.0, 36.0, 68.0),
    },
    "shimla": {
        1: (6.0, 2.0, 10.0, 65.0, 45.0, 82.0),
        2: (7.5, 3.0, 12.0, 64.0, 42.0, 82.0),
        3: (12.0, 7.0, 16.5, 55.0, 35.0, 75.0),
        4: (16.5, 11.5, 21.0, 48.0, 30.0, 68.0),
        5: (20.0, 15.0, 24.5, 50.0, 32.0, 70.0),
        6: (21.0, 16.5, 25.0, 65.0, 48.0, 82.0),
        7: (19.0, 15.5, 22.0, 88.0, 78.0, 96.0),
        8: (18.5, 15.0, 21.5, 90.0, 80.0, 98.0),
        9: (17.5, 13.5, 21.0, 78.0, 62.0, 90.0),
        10: (15.0, 11.0, 19.0, 58.0, 40.0, 75.0),
        11: (11.5, 7.5, 15.5, 52.0, 35.0, 70.0),
        12: (8.0, 4.0, 12.0, 58.0, 40.0, 75.0),
    },
}

# Storage type standard fallbacks (L4)
STORAGE_DEFAULTS: dict[str, dict[str, Any]] = {
    "ambient": {
        "t_mean": 25.0,
        "t_min": 20.0,
        "t_max": 35.0,
        "rh_mean": 65.0,
        "rh_min": 50.0,
        "rh_max": 80.0,
        "note": "Standard tropical ambient baseline storage",
    },
    "shed": {
        "t_mean": 30.0,
        "t_min": 25.0,
        "t_max": 38.0,
        "rh_mean": 70.0,
        "rh_min": 50.0,
        "rh_max": 85.0,
        "note": "Uninsulated shed / warehouse ambient condition",
    },
    "chilled": {
        "t_mean": 4.0,
        "t_min": 2.0,
        "t_max": 8.0,
        "rh_mean": 85.0,
        "rh_min": 80.0,
        "rh_max": 95.0,
        "note": "Commercial chilled refrigeration regime (2-8 °C)",
    },
    "refrigerated": {
        "t_mean": 4.0,
        "t_min": 2.0,
        "t_max": 8.0,
        "rh_mean": 85.0,
        "rh_min": 80.0,
        "rh_max": 95.0,
        "note": "Refrigerated transport / display case regime",
    },
    "cold_storage": {
        "t_mean": 8.0,
        "t_min": 4.0,
        "t_max": 12.0,
        "rh_mean": 90.0,
        "rh_min": 85.0,
        "rh_max": 95.0,
        "note": "Produce cold storage facility (high humidity)",
    },
    "frozen": {
        "t_mean": -18.0,
        "t_min": -22.0,
        "t_max": -15.0,
        "rh_mean": 90.0,
        "rh_min": 85.0,
        "rh_max": 95.0,
        "note": "Deep freeze distribution regime (-18 °C)",
    },
}


class JourneyLeg(BaseModel):
    """Specification of an individual journey segment."""

    leg_id: str = Field(default="leg_1")
    location: str | None = None
    month: str | int | None = None
    storage_type: str | None = None
    temp_c: float | None = None
    rh_pct: float | None = None
    duration_hours: float = 24.0
    transport_mode: str | None = None
    sensor_data: dict[str, Any] | None = None


def normalize_month(month: str | int | None) -> int | None:
    """Parses month name, abbreviation, or integer into month number 1-12."""
    if month is None:
        return None
    if isinstance(month, int):
        return month if 1 <= month <= 12 else None
    m_clean = str(month).strip().lower()
    if m_clean.isdigit():
        val = int(m_clean)
        return val if 1 <= val <= 12 else None
    return MONTH_LOOKUP.get(m_clean)


def lookup_climatology(
    location: str | None,
    month: str | int | None,
) -> tuple[tuple[float, float, float], tuple[float, float, float], str] | None:
    """
    Looks up monthly climatology for a known location and month.
    Returns ((t_mean, t_min, t_max), (rh_mean, rh_min, rh_max), city_key) or None.
    """
    if not location or not month:
        return None

    m_num = normalize_month(month)
    if not m_num:
        return None

    loc_clean = str(location).strip().lower()
    city_key = CITY_ALIASES.get(loc_clean, loc_clean)

    # Partial match if direct alias fails (e.g. 'mumbai (19.08 n, 72.88 e)')
    if city_key not in CLIMATOLOGY_DB:
        for alias, mapped_key in CITY_ALIASES.items():
            if alias in loc_clean:
                city_key = mapped_key
                break

    if city_key in CLIMATOLOGY_DB and m_num in CLIMATOLOGY_DB[city_key]:
        t_mean, t_min, t_max, rh_mean, rh_min, rh_max = CLIMATOLOGY_DB[city_key][m_num]
        return (t_mean, t_min, t_max), (rh_mean, rh_min, rh_max), city_key

    return None


def resolve_environment(
    *,
    temp_c: float | None = None,
    rh_pct: float | None = None,
    duration_hours: float | None = None,
    duration_days: float | None = None,
    location: str | None = None,
    month: str | int | None = None,
    storage_type: str | None = None,
    sensor_data: dict[str, Any] | None = None,
    transport_mode: str | None = None,
    legs: list[dict[str, Any] | JourneyLeg] | None = None,
) -> Environment:
    """
    Resolves storage and transit environment obeying the 4-tier priority ladder.

    If multiple journey legs are supplied, selects the harshest (worst) leg to
    prevent package under-design.
    """
    if legs and len(legs) > 0:
        return resolve_multi_leg_journey(legs)

    # 1. Resolve duration
    dur_h = 48.0
    dur_conf = 0.5
    dur_src = "default"
    dur_note = "Default assumed transit/storage duration"

    if duration_hours is not None:
        dur_h = float(duration_hours)
        dur_conf = 1.0
        dur_src = "user_input"
        dur_note = f"User-specified duration: {dur_h:.1f} hours"
    elif duration_days is not None:
        dur_h = float(duration_days) * 24.0
        dur_conf = 1.0
        dur_src = "user_input"
        dur_note = f"User-specified duration: {float(duration_days):.1f} days"

    dur_prov = Provenance(
        value=dur_h,
        unit="hours",
        source_id=dur_src,
        source_type=SourceType.MEASURED
        if dur_conf == 1.0
        else SourceType.CLASS_DEFAULT,
        resolution_level=ResolutionLevel.L0 if dur_conf == 1.0 else ResolutionLevel.L4,
        confidence=dur_conf,
        note=dur_note,
    )

    # 2. Priority 1: User-supplied direct measurement (L0)
    t_prov: Provenance | None = None
    rh_prov: Provenance | None = None

    if temp_c is not None:
        val = float(temp_c)
        t_prov = Provenance(
            value=val,
            range_low=val,
            range_high=val,
            unit="degC",
            source_id="user_input",
            source_type=SourceType.MEASURED,
            resolution_level=ResolutionLevel.L0,
            confidence=1.0,
            note="User-supplied direct temperature measurement",
        )

    if rh_pct is not None:
        val = float(rh_pct)
        rh_prov = Provenance(
            value=val,
            range_low=val,
            range_high=val,
            unit="%",
            source_id="user_input",
            source_type=SourceType.MEASURED,
            resolution_level=ResolutionLevel.L0,
            confidence=1.0,
            note="User-supplied direct relative humidity measurement",
        )

    # 3. Priority 2: Sensor / Logger telemetry data (L1)
    if sensor_data:
        if t_prov is None and "temperature_c" in sensor_data:
            s_val = float(sensor_data["temperature_c"])
            s_low = float(sensor_data.get("temperature_min_c", s_val))
            s_high = float(sensor_data.get("temperature_max_c", s_val))
            t_prov = Provenance(
                value=s_val,
                range_low=s_low,
                range_high=s_high,
                unit="degC",
                source_id="sensor_logger",
                source_type=SourceType.MEASURED,
                resolution_level=ResolutionLevel.L1,
                confidence=0.95,
                note="Attached data logger / telemetry reading",
            )
        if rh_prov is None and "relative_humidity_pct" in sensor_data:
            s_val = float(sensor_data["relative_humidity_pct"])
            s_low = float(sensor_data.get("rh_min_pct", s_val))
            s_high = float(sensor_data.get("rh_max_pct", s_val))
            rh_prov = Provenance(
                value=s_val,
                range_low=s_low,
                range_high=s_high,
                unit="%",
                source_id="sensor_logger",
                source_type=SourceType.MEASURED,
                resolution_level=ResolutionLevel.L1,
                confidence=0.95,
                note="Attached humidity logger / telemetry reading",
            )

    # 4. Priority 3: Geolocation + month climatology (L2/L3)
    climatology = lookup_climatology(location, month)
    if climatology is not None:
        (t_mean, t_min, t_max), (rh_mean, rh_min, rh_max), city_key = climatology
        m_num = normalize_month(month) or 1
        m_name = [k for k, v in MONTH_LOOKUP.items() if v == m_num and len(k) > 3][0]

        if t_prov is None:
            t_prov = Provenance(
                value=t_mean,
                range_low=t_min,
                range_high=t_max,
                unit="degC",
                source_id="Open-Meteo-Climatology",
                source_type=SourceType.STANDARD,
                resolution_level=ResolutionLevel.L2,
                confidence=0.55,
                note=f"{city_key.title()}, {m_name.title()} average",
            )

        if rh_prov is None:
            rh_prov = Provenance(
                value=rh_mean,
                range_low=rh_min,
                range_high=rh_max,
                unit="%",
                source_id="Open-Meteo-Climatology",
                source_type=SourceType.STANDARD,
                resolution_level=ResolutionLevel.L2,
                confidence=0.55,
                note=f"{city_key.title()}, {m_name.title()} average",
            )

    # 5. Priority 4: Storage-type baseline default (L4)
    st_clean = str(storage_type).strip().lower() if storage_type else "ambient"
    st_spec = STORAGE_DEFAULTS.get(st_clean, STORAGE_DEFAULTS["ambient"])

    if t_prov is None:
        t_prov = Provenance(
            value=st_spec["t_mean"],
            range_low=st_spec["t_min"],
            range_high=st_spec["t_max"],
            unit="degC",
            source_id="storage_default",
            source_type=SourceType.CLASS_DEFAULT,
            resolution_level=ResolutionLevel.L4,
            confidence=0.40,
            note=st_spec["note"],
        )

    if rh_prov is None:
        rh_prov = Provenance(
            value=st_spec["rh_mean"],
            range_low=st_spec["rh_min"],
            range_high=st_spec["rh_max"],
            unit="%",
            source_id="storage_default",
            source_type=SourceType.CLASS_DEFAULT,
            resolution_level=ResolutionLevel.L4,
            confidence=0.40,
            note=st_spec["note"],
        )

    st_prov = Provenance(
        value=st_clean,
        source_id="storage_type",
        source_type=SourceType.STANDARD,
        resolution_level=ResolutionLevel.L2,
        confidence=0.90,
        note=f"Storage type regime: {st_clean}",
    )

    tm_prov: Provenance | None = None
    if transport_mode:
        tm_prov = Provenance(
            value=str(transport_mode).strip().lower(),
            source_id="transport_mode",
            source_type=SourceType.STANDARD,
            resolution_level=ResolutionLevel.L2,
            confidence=0.90,
            note=f"Transport mode: {transport_mode}",
        )

    return Environment(
        temperature=t_prov,
        relative_humidity=rh_prov,
        duration=dur_prov,
        transport_mode=tm_prov,
        storage_type=st_prov,
    )


def resolve_multi_leg_journey(
    legs: list[dict[str, Any] | JourneyLeg],
) -> Environment:
    """
    Evaluates all segments of a multi-leg supply chain journey and returns
    the worst (harshest) leg environment to govern protective packaging design.

    Selection ranking:
    1. Highest maximum temperature (range_high or value)
    2. Highest relative humidity driving force
    3. Longest duration
    """
    if not legs:
        return resolve_environment()

    resolved_legs: list[Environment] = []
    for leg in legs:
        if isinstance(leg, JourneyLeg):
            env = resolve_environment(
                temp_c=leg.temp_c,
                rh_pct=leg.rh_pct,
                duration_hours=leg.duration_hours,
                location=leg.location,
                month=leg.month,
                storage_type=leg.storage_type,
                sensor_data=leg.sensor_data,
                transport_mode=leg.transport_mode,
            )
        elif isinstance(leg, dict):
            env = resolve_environment(**leg)
        elif isinstance(leg, Environment):
            env = leg
        else:
            raise TypeError(f"Invalid leg type: {type(leg)}")
        resolved_legs.append(env)

    # Score each leg for harshness
    def harshness_score(env: Environment) -> tuple[float, float, float]:
        t_val = (
            env.temperature.range_high
            if env.temperature.range_high is not None
            else float(env.temperature.value)
        )
        rh_val = (
            env.relative_humidity.range_high
            if env.relative_humidity.range_high is not None
            else float(env.relative_humidity.value)
        )
        dur = float(env.duration.value) if env.duration.value is not None else 0.0
        return (t_val, rh_val, dur)

    worst = max(resolved_legs, key=harshness_score)
    return worst
