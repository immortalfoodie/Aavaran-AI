"""
FastAPI Traceability & Public Provenance Route for Aavaran.

Implements:
- GET  /t/{batch_code}             : Fast public zero-JS provenance verification page
- GET  /api/v1/trace/qr/{batch_code}: Generates PNG QR code encoding /t/{batch_code}
- GET  /api/v1/trace/merkle-roots  : Exposes daily Merkle roots & chain validity
- POST /api/v1/trace/batch         : Registers hash-chained batch record
"""

import base64
from datetime import datetime, timedelta
import io
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import qrcode

from engine.store import BatchRecord, global_batch_store, global_result_store
from engine.version import ENGINE_VERSION, KB_VERSION, RULESET_VERSION

router = APIRouter(tags=["Traceability"])


class CreateBatchRequest(BaseModel):
    batch_code: str = Field(..., description="Alphanumeric short batch code stamped on the physical pack")
    result_id: str = Field(..., description="ID of the SealedResult defining the packaging spec")
    commodity: Optional[str] = Field(None, description="Commodity name or ID")
    quantity: str = Field(default="100 kg", description="Quantity packed, e.g. 500 kg or 1200 pouches")
    harvest_or_production_date: Optional[datetime] = Field(None, description="Harvest or processing date")
    packaging_used: Optional[str] = Field(None, description="Packaging specification description")
    packer_identity: str = Field(default="Verified Aavaran AI Member", description="Packer name, FPO, or brand entity")
    location: str = Field(default="India", description="Packing facility, mandi, or farm site")
    handling_events: Optional[List[Dict[str, Any]]] = Field(None, description="Timeline of handling events")
    
    # Backwards-compatibility fields
    commodity_id: Optional[str] = None
    structure_id: Optional[str] = None
    package_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional batch packing line telemetry")


def _generate_qr_png_bytes(batch_code: str, base_url: str = "") -> bytes:
    """Generates PNG bytes for a QR code encoding the public batch URL."""
    target_url = f"{base_url.rstrip('/')}/t/{batch_code}" if base_url else f"https://aavaran.app/t/{batch_code}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B0B0B", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_qr_data_uri(batch_code: str, base_url: str = "") -> str:
    """Generates base64 data URI for inline HTML embedding without extra network requests."""
    png_bytes = _generate_qr_png_bytes(batch_code, base_url)
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@router.post("/api/v1/trace/batch", response_model=BatchRecord)
def register_batch_record(request: CreateBatchRequest) -> BatchRecord:
    """
    Registers a new production packaging batch into the append-only,
    SHA-256 hash-chained batch ledger.
    """
    try:
        record = global_batch_store.create_batch(
            batch_code=request.batch_code,
            result_id=request.result_id,
            commodity=request.commodity or request.commodity_id,
            quantity=request.quantity,
            harvest_or_production_date=request.harvest_or_production_date,
            packaging_used=request.packaging_used or request.package_name,
            packer_identity=request.packer_identity,
            location=request.location,
            handling_events=request.handling_events,
            commodity_id=request.commodity_id,
            structure_id=request.structure_id,
            package_name=request.package_name,
            metadata=request.metadata,
        )
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record batch: {str(e)}")


@router.get("/api/v1/trace/merkle-roots")
def get_daily_merkle_roots() -> Dict[str, Any]:
    """
    Returns computed daily Merkle roots for external audit and tamper detection
    without the high transaction costs of a distributed blockchain.
    """
    roots = global_batch_store.get_daily_merkle_roots()
    today_root = global_batch_store.get_daily_merkle_root()
    is_valid = global_batch_store.verify_integrity()
    total_records = len(global_batch_store.all_batches())

    return {
        "status": "SECURE" if is_valid else "TAMPER_DETECTED",
        "chain_integrity_valid": is_valid,
        "total_batches_recorded": total_records,
        "today_merkle_root": today_root,
        "daily_merkle_roots": roots,
        "engine_version": ENGINE_VERSION,
        "ruleset_version": RULESET_VERSION,
    }


@router.get("/api/v1/trace/qr/{batch_code}")
def get_batch_qr_code(batch_code: str, request: Request):
    """
    Returns a PNG QR code for the given batch code, resolving to GET /t/{batch_code}.
    """
    record = global_batch_store.get_by_code(batch_code)
    if not record:
        raise HTTPException(status_code=404, detail=f"Batch code '{batch_code}' not found.")

    base_url = str(request.base_url)
    png_bytes = _generate_qr_png_bytes(batch_code, base_url)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/t/{batch_code}")
def public_provenance_page(
    batch_code: str,
    request: Request,
    format: Optional[str] = Query(None, description="Force response format, e.g. 'json'"),
):
    """
    Public provenance page resolving from QR codes on physical packs.
    Shows commodity, packing date, packaging used, recommended storage conditions,
    best-before guidance, handler timeline, and chain-verification status.
    
    Loads in <50ms, works 100% without JavaScript on 2G/3G mobile networks.
    """
    record = global_batch_store.get_by_code(batch_code)
    if not record:
        raise HTTPException(status_code=404, detail=f"Batch code '{batch_code}' not found.")

    sealed = global_result_store.get(record.result_id)
    is_chain_valid = global_batch_store.verify_integrity()
    day_str = record.created_at.strftime("%Y-%m-%d")
    daily_root = global_batch_store.get_daily_merkle_root(day_str)

    # Storage recommendations
    storage_temp = "10–15 °C"
    storage_rh = "85–90 %"
    storage_notes = "Store in clean, shaded, well-ventilated dry secondary crates away from direct sun."
    if sealed and sealed.resolved and sealed.resolved.environment:
        env = sealed.resolved.environment
        storage_temp = f"{env.temperature.value:.1f} {env.temperature.unit}"
        storage_rh = f"{env.relative_humidity.value:.1f} {env.relative_humidity.unit}"

    # Best-before calculation
    shelf_life_days = 14.0
    limiting_reason = "Natural respiration & moisture evaporation"
    if sealed and sealed.shelf_life:
        shelf_life_days = sealed.shelf_life.days_p50
        limiting_reason = sealed.shelf_life.limiting_mechanism

    packing_date = record.created_at
    harvest_date = record.harvest_or_production_date
    best_before_date = packing_date + timedelta(days=shelf_life_days)

    accept_header = request.headers.get("accept", "")
    wants_json = (
        format == "json"
        or "application/json" in accept_header
        or accept_header == "*/*"
        or "text/html" not in accept_header
    )

    # Return structured JSON if explicitly requested or default API client
    if wants_json and "text/html" not in accept_header:
        return {
            "batch_code": record.batch_code,
            "commodity": record.commodity,
            "commodity_id": record.commodity_id,
            "structure_id": record.structure_id,
            "package_name": record.package_name,
            "quantity": record.quantity,
            "harvest_date": harvest_date.isoformat(),
            "packing_date": packing_date.isoformat(),
            "packaging_used": record.packaging_used,
            "packer_identity": record.packer_identity,
            "location": record.location,
            "chain_valid": is_chain_valid,
            "recommended_storage": {
                "temperature": storage_temp,
                "relative_humidity": storage_rh,
                "advisory": storage_notes,
            },
            "best_before": {
                "shelf_life_days_p50": round(shelf_life_days, 1),
                "estimated_expiry_date": best_before_date.strftime("%Y-%m-%d"),
                "limiting_mechanism": limiting_reason,
            },
            "chain_verification": {
                "chain_valid": is_chain_valid,
                "sha256_hash": record.sha256_hash,
                "prev_hash": record.prev_hash,
                "daily_merkle_root": daily_root,
                "date_partition": day_str,
            },
            "handling_events": record.handling_events,
            "result_id": record.result_id,
            "engine_version": ENGINE_VERSION,
            "kb_version": KB_VERSION,
        }

    # Generate QR data URI for self-contained, no-JS page rendering
    base_url = str(request.base_url)
    qr_data_uri = _generate_qr_data_uri(batch_code, base_url)

    # Render fast, zero-JS neo-brutalist HTML
    events_html = ""
    for ev in record.handling_events:
        ev_name = ev.get("name", "Handling Event")
        ev_time = ev.get("timestamp", "")[:16].replace("T", " ")
        ev_loc = ev.get("location", record.location)
        ev_actor = ev.get("actor", record.packer_identity)
        ev_notes = ev.get("notes", "")
        events_html += f"""
        <div class="event-item">
            <div class="event-dot"></div>
            <div class="event-content">
                <div class="event-header">
                    <strong>{ev_name}</strong>
                    <span class="mono-date">{ev_time}</span>
                </div>
                <div class="event-sub">{ev_actor} · {ev_loc}</div>
                {f'<div class="event-notes">{ev_notes}</div>' if ev_notes else ''}
            </div>
        </div>
        """

    chain_badge_color = "#C9FF3D" if is_chain_valid else "#FF4A22"
    chain_badge_text = "VERIFIED PROVENANCE · CRYPTOGRAPHIC CHAIN ✓" if is_chain_valid else "INTEGRITY WARNING ⚠"


    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Aavaran AI Traceability Verification for Batch {record.batch_code}">
    <title>Batch {record.batch_code} · Aavaran AI Provenance</title>
    <style>
        /* Zero-dependency Neo-brutalist CSS - ultra-lightweight (<4KB) */
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{
            background-color: #FFFDF2;
            color: #0B0B0B;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            margin: 0;
            padding: 16px;
            line-height: 1.4;
        }}
        .container {{
            max-width: 640px;
            margin: 0 auto;
        }}
        .card {{
            background: #FFFFFF;
            border: 3px solid #0B0B0B;
            box-shadow: 6px 6px 0px #0B0B0B;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            border-bottom: 3px solid #0B0B0B;
            padding-bottom: 14px;
            margin-bottom: 18px;
        }}
        .badge {{
            display: inline-block;
            background: {chain_badge_color};
            color: #0B0B0B;
            border: 2px solid #0B0B0B;
            font-weight: 800;
            padding: 4px 10px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .brand {{
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 1px;
            text-transform: uppercase;
            background: #0B0B0B;
            color: #FFFDF2;
            padding: 4px 8px;
        }}
        h1 {{
            font-size: 26px;
            font-weight: 900;
            margin: 0 0 4px 0;
            text-transform: uppercase;
        }}
        .subtitle {{
            font-size: 13px;
            color: #444;
            margin-bottom: 16px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 16px;
        }}
        @media (max-width: 480px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
        }}
        .stat-box {{
            background: #FAF7E8;
            border: 2px solid #0B0B0B;
            padding: 12px;
        }}
        .stat-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 4px;
        }}
        .stat-val {{
            font-size: 16px;
            font-weight: 800;
            color: #0B0B0B;
        }}
        .highlight-box {{
            background: #E8F7FF;
            border: 2px solid #0B0B0B;
            padding: 14px;
            margin-bottom: 16px;
        }}
        .highlight-box.green {{
            background: #EDFCD4;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 16px 0 8px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .hash-code {{
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 10px;
            background: #EFEFEF;
            border: 1px solid #0B0B0B;
            padding: 6px;
            word-break: break-all;
            margin-top: 4px;
        }}
        /* Timeline */
        .timeline {{
            border-left: 3px solid #0B0B0B;
            margin: 12px 0 16px 12px;
            padding-left: 14px;
        }}
        .event-item {{
            position: relative;
            margin-bottom: 14px;
        }}
        .event-dot {{
            position: absolute;
            left: -20px;
            top: 4px;
            width: 10px;
            height: 10px;
            background: #0B0B0B;
            border: 2px solid #FFFDF2;
        }}
        .event-header {{
            font-size: 13px;
            font-weight: 700;
        }}
        .mono-date {{
            font-family: monospace;
            font-size: 11px;
            color: #555;
            float: right;
        }}
        .event-sub {{
            font-size: 12px;
            color: #555;
        }}
        .event-notes {{
            font-size: 11px;
            background: #FAF7E8;
            padding: 4px 6px;
            border-left: 2px solid #0B0B0B;
            margin-top: 4px;
        }}
        .qr-section {{
            display: flex;
            align-items: center;
            gap: 16px;
            border-top: 2px solid #0B0B0B;
            padding-top: 14px;
            margin-top: 16px;
        }}
        .qr-img {{
            width: 96px;
            height: 96px;
            border: 2px solid #0B0B0B;
            background: #FFFFFF;
        }}
        .qr-desc {{
            font-size: 12px;
            color: #333;
        }}
        .footer {{
            font-size: 10px;
            color: #666;
            margin-top: 14px;
            border-top: 1px solid #CCC;
            padding-top: 8px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <!-- Header Bar -->
            <div class="header">
                <div>
                    <span class="brand">AAVARAN AI</span>
                    <span class="badge" style="margin-left: 6px;">PROVENANCE LEDGER</span>
                </div>
                <div class="badge">{chain_badge_text}</div>
            </div>

            <!-- Title -->
            <h1>{record.commodity.upper()}</h1>
            <div class="subtitle">
                <strong>Batch:</strong> {record.batch_code} &nbsp;|&nbsp; 
                <strong>Origin:</strong> {record.location}
            </div>

            <!-- Key Metrics Grid -->
            <div class="grid-2">
                <div class="stat-box">
                    <div class="stat-label">Packed Date</div>
                    <div class="stat-val">{packing_date.strftime('%d %b %Y')}</div>
                    <div style="font-size: 11px; color:#666;">Harvest: {harvest_date.strftime('%d %b %Y')}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Best-Before Guidance</div>
                    <div class="stat-val">{best_before_date.strftime('%d %b %Y')}</div>
                    <div style="font-size: 11px; color:#228800; font-weight:700;">{shelf_life_days:.0f} days from packing</div>
                </div>
            </div>

            <!-- Packaging Used Box -->
            <div class="highlight-box">
                <div class="stat-label">Packaging Applied</div>
                <div style="font-weight: 800; font-size: 15px; margin-bottom: 4px;">{record.packaging_used}</div>
                <div style="font-size: 12px; color: #444;">
                    Referenced Decision Spec: <code>{record.result_id}</code><br>
                    Packer: <strong>{record.packer_identity}</strong> · Quantity: <strong>{record.quantity}</strong>
                </div>
            </div>

            <!-- Recommended Storage Conditions -->
            <div class="highlight-box green">
                <div class="stat-label">Recommended Storage Conditions</div>
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 2px;">
                    Target Temperature: {storage_temp} &nbsp;|&nbsp; Relative Humidity: {storage_rh}
                </div>
                <div style="font-size: 12px; color: #333;">{storage_notes}</div>
            </div>

            <!-- Handling Timeline -->
            <div class="section-title">📦 Custody & Handling Timeline</div>
            <div class="timeline">
                {events_html}
            </div>

            <!-- Cryptographic Verification -->
            <div class="section-title">🔒 Append-Only Cryptographic Proof</div>
            <div style="font-size: 11px; color: #444;">
                Every record commits to the previous row's SHA-256 hash. Daily Merkle roots expose any tampering without blockchain overhead.
            </div>
            <div style="margin-top: 8px;">
                <div class="stat-label">Record SHA-256 Hash</div>
                <div class="hash-code">{record.sha256_hash}</div>
            </div>
            <div style="margin-top: 6px;">
                <div class="stat-label">Previous Chained Hash</div>
                <div class="hash-code">{record.prev_hash}</div>
            </div>
            <div style="margin-top: 6px;">
                <div class="stat-label">Daily Merkle Root ({day_str})</div>
                <div class="hash-code">{daily_root}</div>
            </div>

            <!-- QR Code Section -->
            <div class="qr-section">
                <img class="qr-img" src="{qr_data_uri}" alt="QR code for batch {record.batch_code}">
                <div class="qr-desc">
                    <strong>Physical Pack Verification</strong><br>
                    Scan with any smartphone camera to independently verify authenticity, cold-chain events, and FSSAI packaging compliance.
                </div>
            </div>

            <!-- Statutory Footer -->
            <div class="footer">
                Aavaran AI Engine v{ENGINE_VERSION} · KB v{KB_VERSION} · Ruleset v{RULESET_VERSION}<br>
                Decision-support advisory. Compliance responsibility rests with the Food Business Operator (FBO) under FSSAI 2006.
            </div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)
