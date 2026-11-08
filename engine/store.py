"""
In-memory and persistent storage layer for SealedResult audit records,
hash-chained batch traceability, and commercial feedback logs.
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from engine.result import SealedResult


class HandlingEvent(BaseModel):
    name: str = Field(..., description="Action name, e.g. Harvest, Sort & Grade, Wash, Pre-chill, MAP Packing, Dispatch")
    timestamp: datetime = Field(default_factory=datetime.now)
    location: str = Field(..., description="Facility or farm location")
    actor: str = Field(..., description="Operator or organization responsible")
    notes: Optional[str] = None


class BatchRecord(BaseModel):
    batch_code: str = Field(..., description="Short alphanumeric batch code, e.g. PW-2026-NASHIK-9A")
    commodity: str = Field(..., description="Commodity name or ID")
    quantity: str = Field(..., description="Quantity packed, e.g. 500 kg or 1200 pouches")
    harvest_or_production_date: datetime = Field(..., description="Harvest or processing date")
    packaging_used: str = Field(..., description="Packaging specification description")
    result_id: str = Field(..., description="Referenced SealedResult ID")
    packer_identity: str = Field(..., description="Packer name, FPO, or brand entity")
    location: str = Field(..., description="Packing site or farm location")
    handling_events: List[Dict[str, Any]] = Field(default_factory=list, description="Timestamps and telemetry for each handling event")
    created_at: datetime = Field(default_factory=datetime.now)
    prev_hash: str = Field(..., description="SHA-256 hash of preceding batch record")
    sha256_hash: str = Field(..., description="Canonical cryptographic SHA-256 hash")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Backwards-compatibility aliases
    commodity_id: Optional[str] = None
    structure_id: Optional[str] = None
    package_name: Optional[str] = None


class FeedbackRecord(BaseModel):
    result_id: str
    actual_shelf_life_days: float
    spoilage_observed: bool
    limiting_mechanism_observed: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    comments: Optional[str] = None
    logged_at: datetime = Field(default_factory=datetime.now)


def compute_merkle_root(hashes: List[str]) -> str:
    """
    Computes a cryptographic binary Merkle root from a list of SHA-256 leaf hashes.
    If empty, returns 64 zeroes.
    """
    if not hashes:
        return "0" * 64
    if len(hashes) == 1:
        return hashes[0]

    current_level = list(hashes)
    while len(current_level) > 1:
        next_level: List[str] = []
        if len(current_level) % 2 == 1:
            current_level.append(current_level[-1])
        for i in range(0, len(current_level), 2):
            combined = (current_level[i] + current_level[i + 1]).encode("utf-8")
            next_level.append(hashlib.sha256(combined).hexdigest())
        current_level = next_level

    return current_level[0]


class ResultStore:
    """Thread-safe in-memory store for SealedResult objects."""

    def __init__(self) -> None:
        self._results: Dict[str, SealedResult] = {}
        self._explanations: Dict[str, Dict[str, Any]] = {}

    def save(self, result: SealedResult) -> None:
        self._results[result.result_id] = result

    def get(self, result_id: str) -> Optional[SealedResult]:
        return self._results.get(result_id)

    def save_explanation(
        self, result_id: str, explanation: Dict[str, Any], locale: Optional[str] = None
    ) -> None:
        self._explanations[result_id] = explanation
        if locale:
            lang = locale.lower().split("-")[0].split("_")[0]
            self._explanations[f"{result_id}:{lang}"] = explanation
            self._explanations[f"{result_id}:{locale.lower()}"] = explanation

    def get_explanation(
        self, result_id: str, locale: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if locale:
            lang = locale.lower().split("-")[0].split("_")[0]
            if f"{result_id}:{locale.lower()}" in self._explanations:
                return self._explanations[f"{result_id}:{locale.lower()}"]
            if f"{result_id}:{lang}" in self._explanations:
                return self._explanations[f"{result_id}:{lang}"]
            return None
        return self._explanations.get(result_id)

    def count(self) -> int:
        return len(self._results)

    def clear(self) -> None:
        self._results.clear()
        self._explanations.clear()


class BatchStore:
    """
    Append-only store with per-record SHA-256 hash chaining and
    daily Merkle root verification for tamper-evident provenance.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._batches: Dict[str, BatchRecord] = {}
        self._chain: List[BatchRecord] = []

    def compute_record_hash(
        self,
        prev_hash: str,
        batch_code: str,
        commodity: str,
        quantity: str,
        harvest_or_production_date: datetime,
        packaging_used: str,
        result_id: str,
        packer_identity: str,
        location: str,
        handling_events: List[Dict[str, Any]],
        created_at: datetime,
    ) -> str:
        """
        Calculates canonical deterministic SHA-256 hash across all batch record contents.
        """
        # Canonical event representation
        clean_events = []
        for ev in handling_events:
            clean_events.append({
                "name": str(ev.get("name", "")),
                "timestamp": str(ev.get("timestamp", "")),
                "location": str(ev.get("location", "")),
                "actor": str(ev.get("actor", "")),
                "notes": str(ev.get("notes", "")),
            })
        events_str = json.dumps(clean_events, sort_keys=True)
        harvest_str = harvest_or_production_date.isoformat()
        created_str = created_at.isoformat()

        payload = (
            f"{prev_hash}|{batch_code}|{commodity}|{quantity}|{harvest_str}|"
            f"{packaging_used}|{result_id}|{packer_identity}|{location}|"
            f"{events_str}|{created_str}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def create_batch(
        self,
        batch_code: str,
        result_id: str,
        commodity: Optional[str] = None,
        quantity: str = "100 kg",
        harvest_or_production_date: Optional[datetime] = None,
        packaging_used: Optional[str] = None,
        packer_identity: str = "Verified Aavaran Facility",
        location: str = "India",
        handling_events: Optional[List[Dict[str, Any]]] = None,
        commodity_id: Optional[str] = None,
        structure_id: Optional[str] = None,
        package_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BatchRecord:
        resolved_commodity = commodity or commodity_id or "produce"
        resolved_pkg = packaging_used or package_name or structure_id or "Custom Barrier Packaging"
        resolved_harvest = harvest_or_production_date or datetime.now()
        resolved_events = list(handling_events or [])
        if not resolved_events:
            resolved_events = [
                {
                    "name": "Harvest & Primary Sorting",
                    "timestamp": resolved_harvest.isoformat(),
                    "location": location,
                    "actor": packer_identity,
                    "notes": "Farm gate quality verification",
                },
                {
                    "name": "Packaging & Sealing",
                    "timestamp": datetime.now().isoformat(),
                    "location": location,
                    "actor": packer_identity,
                    "notes": f"Sealed per Aavaran result {result_id}",
                },
            ]

        prev_hash = self._chain[-1].sha256_hash if self._chain else self.GENESIS_HASH
        now = datetime.now()

        sha = self.compute_record_hash(
            prev_hash=prev_hash,
            batch_code=batch_code,
            commodity=resolved_commodity,
            quantity=quantity,
            harvest_or_production_date=resolved_harvest,
            packaging_used=resolved_pkg,
            result_id=result_id,
            packer_identity=packer_identity,
            location=location,
            handling_events=resolved_events,
            created_at=now,
        )

        record = BatchRecord(
            batch_code=batch_code,
            commodity=resolved_commodity,
            quantity=quantity,
            harvest_or_production_date=resolved_harvest,
            packaging_used=resolved_pkg,
            result_id=result_id,
            packer_identity=packer_identity,
            location=location,
            handling_events=resolved_events,
            created_at=now,
            prev_hash=prev_hash,
            sha256_hash=sha,
            metadata=metadata or {},
            commodity_id=resolved_commodity,
            structure_id=structure_id,
            package_name=resolved_pkg,
        )
        self._batches[batch_code] = record
        self._chain.append(record)
        return record

    def get_by_code(self, batch_code: str) -> Optional[BatchRecord]:
        return self._batches.get(batch_code)

    def all_batches(self) -> List[BatchRecord]:
        return list(self._chain)

    def verify_integrity(self) -> bool:
        """Verifies the complete append-only SHA-256 hash chain."""
        expected_prev = self.GENESIS_HASH
        for rec in self._chain:
            if rec.prev_hash != expected_prev:
                return False
            computed = self.compute_record_hash(
                prev_hash=rec.prev_hash,
                batch_code=rec.batch_code,
                commodity=rec.commodity,
                quantity=rec.quantity,
                harvest_or_production_date=rec.harvest_or_production_date,
                packaging_used=rec.packaging_used,
                result_id=rec.result_id,
                packer_identity=rec.packer_identity,
                location=rec.location,
                handling_events=rec.handling_events,
                created_at=rec.created_at,
            )
            if rec.sha256_hash != computed:
                return False
            expected_prev = rec.sha256_hash
        return True

    def get_daily_merkle_roots(self) -> Dict[str, str]:
        """
        Groups all batch records by calendar date (YYYY-MM-DD) and computes
        the Merkle root for each day.
        """
        batches_by_day: Dict[str, List[str]] = {}
        for rec in self._chain:
            day_str = rec.created_at.strftime("%Y-%m-%d")
            if day_str not in batches_by_day:
                batches_by_day[day_str] = []
            batches_by_day[day_str].append(rec.sha256_hash)

        roots: Dict[str, str] = {}
        for day_str, hashes in batches_by_day.items():
            roots[day_str] = compute_merkle_root(hashes)
        return roots

    def get_daily_merkle_root(self, day_str: Optional[str] = None) -> str:
        """
        Returns the daily Merkle root for a given date (defaults to today).
        """
        target_day = day_str or datetime.now().strftime("%Y-%m-%d")
        daily_hashes = [
            rec.sha256_hash
            for rec in self._chain
            if rec.created_at.strftime("%Y-%m-%d") == target_day
        ]
        return compute_merkle_root(daily_hashes)

    def clear(self) -> None:
        self._batches.clear()
        self._chain.clear()


class FeedbackStore:
    """Store for commercial feedback logging."""

    def __init__(self) -> None:
        self._feedbacks: List[FeedbackRecord] = []

    def save(self, record: FeedbackRecord) -> None:
        self._feedbacks.append(record)

    def get_for_result(self, result_id: str) -> List[FeedbackRecord]:
        return [f for f in self._feedbacks if f.result_id == result_id]

    def all(self) -> List[FeedbackRecord]:
        return list(self._feedbacks)

    def clear(self) -> None:
        self._feedbacks.clear()


# Global singleton stores
global_result_store = ResultStore()
global_batch_store = BatchStore()
global_feedback_store = FeedbackStore()

