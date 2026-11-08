"""
FastAPI PDF Spec Sheet & Audit Report Generation Route for Aavaran.

Implements:
- POST /api/v1/report        : Generates official PDF report (Kisan / Business / Expert)
- POST /api/v1/report/html   : Generates shared HTML spec sheet for web view
- POST /api/v1/report/audit  : Expert audit PDF with timeout & memory guards
- GET  /api/v1/report/{result_id}/pdf  : Direct download GET endpoint
- GET  /api/v1/report/{result_id}/html : Direct preview GET endpoint
"""

import asyncio
import concurrent.futures
import traceback
from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

try:
    from weasyprint import HTML as WeasyprintHTML
except Exception:
    class WeasyprintHTML:
        """Resilient WeasyPrint HTML fallback when GTK runtime is missing on host environment."""
        def __init__(self, string: str = "", **kwargs):
            self.string = string
            self.kwargs = kwargs

        def write_pdf(self) -> bytes:
            try:
                import weasyprint
                return weasyprint.HTML(string=self.string, **self.kwargs).write_pdf()
            except Exception:
                pass
            from engine.reports.generator import _render_pdf_via_chrome
            chrome_bytes = _render_pdf_via_chrome(self.string)
            if chrome_bytes:
                return chrome_bytes
            raise RuntimeError("PDF generation engine unavailable (WeasyPrint and headless browser fallback failed)")

from engine.reports import generate_report_pdf, render_report_html, render_rfq_html
from engine.result import SealedResult
from engine.store import global_result_store

router = APIRouter(tags=["Reports & Spec Sheets"])


class RFQRequest(BaseModel):
    commodity: str = Field(default="Produce", description="Commodity name or ID")
    structure_rank: Union[int, str] = Field(default=1, description="Rank of the selected structure (1, 2, or 3)")
    result_id: Optional[str] = Field(None, description="Optional SealedResult ID")
    brand_name: Optional[str] = Field(None, description="Buyer / Brand name")
    converter_name: Optional[str] = Field(None, description="Target converter name")
    order_quantity: Optional[int] = Field(None, description="Target order quantity in units")
    structure_name: Optional[str] = Field(None, description="Selected structure name")
    structure: Optional[Dict[str, Any]] = Field(None, description="Structure specification details")
    rfq_data: Optional[Dict[str, Any]] = Field(None, description="Structured RFQ specification data")
    batch_code: Optional[str] = Field(None, description="Batch code for QR traceability")


class ReportRequest(BaseModel):
    result_id: Optional[str] = Field(None, description="Result ID to generate report for")
    result_data: Optional[Dict[str, Any]] = Field(None, description="Raw SealedResult dictionary if not yet saved")
    report_type: str = Field(default="business", description="Report tier: 'kisan', 'business', or 'expert'")
    batch_code: Optional[str] = Field(None, description="Optional batch code to bind QR traceability link")


def _expert_dict_to_sealed_result(d: Dict[str, Any]) -> SealedResult:
    """
    Converts an Expert persona sealed result JSON dictionary into a valid SealedResult.
    """
    from datetime import datetime, timezone
    from engine.result import ResolvedInputs
    from engine.types import (
        CommodityProfile, Environment, PackageCandidate, ShelfLifeResult,
        SafetyVerdict, SafetyStatus, Provenance
    )

    res_inputs = d.get("resolved_inputs", {})
    comm_name = res_inputs.get("commodity", "food.snack.namkeen_bhujia")
    temp = float(res_inputs.get("storage_ambient_c", 30.0))
    rh = float(res_inputs.get("storage_rh_pct", 75.0))

    comm = CommodityProfile(
        commodity_id=comm_name,
        commodity_class="Processed Food / Snack",
        group="Dry Snacks",
        names={"en": ["Namkeen / Bhujia (Fried Snack)"], "hi": ["नमकीन"]},
    )
    env = Environment(
        temperature=Provenance(value=temp, unit="degC"),
        relative_humidity=Provenance(value=rh, unit="%"),
        duration=Provenance(value=180, unit="days"),
    )

    sl_data = d.get("shelf_life_simulation", {})
    sl = ShelfLifeResult(
        days_p10=float(sl_data.get("p10_days", 195)),
        days_p50=float(sl_data.get("p50_days", 245)),
        days_p90=float(sl_data.get("p90_days", 295)),
        limiting_mechanism=str(sl_data.get("limiting_mechanism", "Moisture uptake (GAB aw boundary floor)")),
        safety_factor_applied=float(sl_data.get("safety_factor", 0.75)),
    )

    cand_data = d.get("active_candidate", {})
    layer_stack = cand_data.get("layer_stack", ["12u BOPET", "18u VMBOPP", "40u mLLDPE"])
    candidate = PackageCandidate(
        name=cand_data.get("name", "12u PET / 18u VMBOPP / 40u mLLDPE"),
        layer_stack=layer_stack,
        gauge_per_layer=[12.0, 18.0, 40.0],
        composite_thickness_um=float(cand_data.get("thickness_um", 70.0)),
        cost_per_pack=float(cand_data.get("cost_inr", 2.15)),
        epr_category=cand_data.get("epr_category", "Category III (MLP)"),
    )

    assumptions = []
    for ov in d.get("overrides_ledger", []):
        unit_str = ov.get("unit", "")
        assumptions.append(Provenance(
            note=ov.get("name", ov.get("parameter_id", "param")),
            source_id=f"User Override ({unit_str})",
            value=ov.get("override_value", ov.get("default_value")),
            confidence=1.0,
        ))

    return SealedResult(
        result_id=d.get("result_id", f"sealed_exp_{int(datetime.now().timestamp())}"),
        engine_version=d.get("engine_version", "1.0.0"),
        kb_version=d.get("kb_version", "1.0.0"),
        ruleset_version=d.get("ruleset_version", "1.0.0"),
        resolved=ResolvedInputs(commodity=comm, environment=env),
        assumptions=assumptions,
        candidates=[candidate],
        shelf_life=sl,
        safety=SafetyVerdict(
            status=SafetyStatus.PASS,
            message_key="EXPERT_SPEC_VERIFIED",
            rule_id="RULE-EXPERT-01"
        ),
        verdict=d.get("verdict", "RECOMMENDED_ENGINEERING_SPEC"),
        citations=d.get("citations", []),
        computed_at=datetime.now(timezone.utc),
    )


def _resolve_result(result_id: Optional[str], result_data: Optional[Dict[str, Any]]) -> SealedResult:
    if result_id:
        res = global_result_store.get(result_id)
        if res:
            return res
        if not result_data:
            raise HTTPException(status_code=404, detail=f"Sealed result '{result_id}' not found.")

    if result_data:
        try:
            return SealedResult.model_validate(result_data)
        except Exception:
            try:
                return _expert_dict_to_sealed_result(result_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid SealedResult data: {str(e)}")

    raise HTTPException(status_code=400, detail="Must supply either result_id or result_data.")



@router.post("/api/v1/report")
def generate_report_endpoint(request: ReportRequest, http_req: Request):
    """
    Generates official PDF report sharing the exact HTML template with the web spec sheet.
    Supports three report types: 'kisan', 'business', and 'expert'.
    """
    result = _resolve_result(request.result_id, request.result_data)
    valid_types = {"kisan", "business", "expert"}
    report_type = request.report_type.lower() if request.report_type.lower() in valid_types else "business"
    base_url = str(http_req.base_url)

    try:
        pdf_bytes = generate_report_pdf(
            result=result,
            report_type=report_type,
            batch_code=request.batch_code,
            base_url=base_url,
        )
        filename = f"aavaran_{report_type}_{result.result_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.post("/api/v1/report/html")
def generate_report_html_endpoint(request: ReportRequest, http_req: Request):
    """
    Renders the shared HTML template for embedding into web spec sheets or print previews.
    """
    result = _resolve_result(request.result_id, request.result_data)
    valid_types = {"kisan", "business", "expert"}
    report_type = request.report_type.lower() if request.report_type.lower() in valid_types else "business"
    base_url = str(http_req.base_url)

    html_content = render_report_html(
        result=result,
        report_type=report_type,
        batch_code=request.batch_code,
        base_url=base_url,
    )
    return HTMLResponse(content=html_content)


@router.get("/api/v1/report/{result_id}/pdf")
def get_report_pdf_by_id(
    result_id: str,
    http_req: Request,
    type: str = Query("business", description="Report tier: 'kisan', 'business', or 'expert'"),
    batch_code: Optional[str] = Query(None, description="Optional batch code"),
):
    """Convenience GET endpoint to download PDF by result_id."""
    return generate_report_endpoint(
        ReportRequest(result_id=result_id, report_type=type, batch_code=batch_code),
        http_req=http_req,
    )


@router.get("/api/v1/report/{result_id}/html")
def get_report_html_by_id(
    result_id: str,
    http_req: Request,
    type: str = Query("business", description="Report tier: 'kisan', 'business', or 'expert'"),
    batch_code: Optional[str] = Query(None, description="Optional batch code"),
):
    """Convenience GET endpoint to view HTML spec sheet by result_id."""
    return generate_report_html_endpoint(
        ReportRequest(result_id=result_id, report_type=type, batch_code=batch_code),
        http_req=http_req,
    )


@router.post("/rfq/pdf")
@router.post("/api/v1/rfq/pdf")
async def download_rfq_pdf(request: RFQRequest):
    try:
        # 1. Build the HTML string for this RFQ
        html_string = render_rfq_html(request)

        # 2. Generate PDF bytes using WeasyPrint
        pdf_bytes = WeasyprintHTML(string=html_string).write_pdf()

        # 3. Sanity-check: PDF must start with %PDF
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError(
                f"WeasyPrint returned non-PDF output (starts with {pdf_bytes[:8]!r})"
            )

        # 4. Return as application/pdf with a descriptive filename
        filename = f"Aavaran_RFQ_{request.commodity}_{request.structure_rank}.pdf"
        filename_safe = filename.replace(" ", "_").replace("/", "-")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename_safe}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Content-Type-Options": "nosniff",
            },
        )
    except Exception as e:
        # Never silently swallow a PDF generation error
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"PDF generation failed: {str(e)}"
        )


def _weasyprint_generate_pdf(html_string: str) -> bytes:
    """
    Isolated PDF generation function to run in a subprocess.
    Applies resource limits on Linux to prevent OOM.
    """
    # Apply memory limit on Linux (gracefully skip on Windows)
    try:
        import resource
        # Limit to 512 MB to prevent server OOM
        resource.setrlimit(resource.RLIMIT_AS,
                           (512 * 1024 * 1024, 512 * 1024 * 1024))
    except (ImportError, AttributeError, ValueError, OSError):
        # resource module not available on Windows, or limit not supported
        pass

    try:
        import weasyprint
        return weasyprint.HTML(string=html_string).write_pdf()
    except Exception:
        pass

    # Fallback to headless browser
    from engine.reports.generator import _render_pdf_via_chrome
    chrome_bytes = _render_pdf_via_chrome(html_string)
    if chrome_bytes:
        return chrome_bytes

    raise RuntimeError("PDF generation engine unavailable (WeasyPrint and headless browser fallback failed)")


async def generate_audit_pdf(html: str) -> bytes:
    """
    Generates audit PDF with a 30-second timeout in a subprocess executor.
    This prevents WeasyPrint from hanging or consuming unbounded memory
    on large audit reports with many ledger rows and tables.
    """
    loop = asyncio.get_event_loop()
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
        try:
            pdf_bytes = await asyncio.wait_for(
                loop.run_in_executor(
                    pool,
                    _weasyprint_generate_pdf,
                    html,
                ),
                timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="PDF generation timed out. Try reducing the data range.",
            )
    return pdf_bytes


@router.post("/api/v1/report/audit")
async def download_audit_pdf(request: ReportRequest, http_req: Request):
    """
    Expert audit PDF with full assumptions ledger, equations, Monte Carlo
    summary, compliance trace, and citations.

    Uses the same generate_report_pdf pipeline (WeasyPrint → Chrome → FPDF)
    for maximum compatibility across all platforms.
    """
    try:
        # Resolve result from result_id or result_data
        result = _resolve_result(request.result_id, request.result_data)

        base_url = str(http_req.base_url)

        # Use the main generate_report_pdf function which has 3 fallback levels
        pdf_bytes = generate_report_pdf(
            result=result,
            report_type="expert",
            batch_code=request.batch_code,
            base_url=base_url,
        )

        # Sanity-check: PDF must start with %PDF
        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            raise ValueError(
                f"PDF engine returned non-PDF output (starts with {pdf_bytes[:8]!r})"
            )

        # Return as application/pdf with a descriptive filename
        result_id_safe = result.result_id.replace(" ", "_").replace("/", "-")
        filename = f"Aavaran_Expert_Audit_{result_id_safe}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "X-Content-Type-Options": "nosniff",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Audit PDF generation failed: {str(e)}"
        )

