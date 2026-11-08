"""
Aavaran FastAPI Application Entrypoint.

Includes:
- Master recommendation and result replay routes (/api/v1/recommend, /api/v1/result)
- Commodity lookup and profile routes (/api/v1/commodities, /api/v1/commodity)
- Regulatory compliance and staleness dashboard routes (/api/v1/compliance, /admin/compliance)
- Shelf-life standalone model (/api/v1/shelf-life)
- Commercial feedback routes (/api/v1/feedback)
- PDF spec sheet report generation (/api/v1/report)
- Public QR traceability resolver (/t/{batch_code})

Cross-cutting Concerns:
- Response headers: X-Engine-Version, X-KB-Version, X-Ruleset-Version, X-Request-ID
- Rate limiting middleware
- Structured JSON logging
- Auto-generated OpenAPI / Swagger documentation
"""

from collections import defaultdict
import json
import logging
import os
import time
from typing import Dict, List
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes.commodity import router as commodity_router
from api.routes.compliance import router as compliance_router
from api.routes.feedback import router as feedback_router
from api.routes.llm import router as llm_router
from api.routes.recommend import router as recommend_router
from api.routes.report import router as report_router
from api.routes.trace import router as trace_router
from api.routes.voice import router as voice_router
from api.routes.insights import router as insights_router
from engine.version import (
    ENGINE_VERSION,
    KB_VERSION,
    RULESET_VERSION,
)

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("aavaran.api")


class AavaranCrossCuttingMiddleware(BaseHTTPMiddleware):
    """
    Handles:
    - X-Request-ID generation / propagation
    - Version stamp headers (X-Engine-Version, X-KB-Version, X-Ruleset-Version)
    - In-memory rate limiting (120 requests/min per IP)
    - Structured JSON request logging
    """

    def __init__(self, app, rate_limit_rpm: int = 120):
        super().__init__(app)
        self.rate_limit_rpm = rate_limit_rpm
        self.ip_request_times: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # 1. Rate Limiting Check
        timestamps = self.ip_request_times[client_ip]
        # Keep only timestamps in the last 60 seconds
        self.ip_request_times[client_ip] = [t for t in timestamps if now - t < 60.0]
        if len(self.ip_request_times[client_ip]) >= self.rate_limit_rpm:
            log_payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "request_id": req_id,
                "client_ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "status_code": 429,
                "error": "Rate limit exceeded",
            }
            logger.warning(json.dumps(log_payload))
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded. Try again in 60 seconds."}),
                status_code=429,
                media_type="application/json",
                headers={
                    "X-Request-ID": req_id,
                    "Retry-After": "60",
                    "X-Engine-Version": ENGINE_VERSION,
                    "X-KB-Version": KB_VERSION,
                    "X-Ruleset-Version": RULESET_VERSION,
                },
            )

        self.ip_request_times[client_ip].append(now)

        # 2. Process Request & Measure Duration
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # 3. Attach Cross-cutting Headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Engine-Version"] = ENGINE_VERSION
        response.headers["X-KB-Version"] = KB_VERSION
        response.headers["X-Ruleset-Version"] = RULESET_VERSION

        # 4. Structured JSON Access Logging
        log_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "request_id": req_id,
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
        }
        logger.info(json.dumps(log_payload))

        return response


app = FastAPI(
    title="Aavaran AI API",
    description=(
        "Aavaran AI: voice-first food packaging decision support. "
        "Speech in and out via Gnani AI Prisma (STT) and Timbre (TTS). "
        "Deterministic, law-as-data regulations (FSSAI/PWM-EPR aware), "
        "multi-failure shelf-life simulation, and cryptographic provenance."
    ),
    version=ENGINE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

cors_origins_env = os.environ.get("CORS_ORIGINS", "*")


def _clean_origin(value: str) -> str:
    """Browsers send origins as scheme://host[:port] with no path or trailing slash.
    Forgive the usual copy-paste mistakes so a stray '/' or quote doesn't block every request."""
    return value.strip().strip("'\"").rstrip("/")


origins = (
    ["*"]
    if cors_origins_env.strip() == "*"
    else [o for o in (_clean_origin(x) for x in cors_origins_env.split(",")) if o]
)
# Optional: also allow e.g. Vercel preview deployments, CORS_ORIGIN_REGEX=https://aavaran-ai-.*\.vercel\.app
cors_origin_regex = os.environ.get("CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=False if "*" in origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-Request-ID",
        "X-Engine-Version",
        "X-KB-Version",
        "X-Ruleset-Version",
    ],
)

app.add_middleware(AavaranCrossCuttingMiddleware)

# Mount all domain routers
app.include_router(recommend_router)
app.include_router(commodity_router)
app.include_router(compliance_router)
app.include_router(report_router)
app.include_router(trace_router)
app.include_router(feedback_router)
app.include_router(llm_router)
app.include_router(voice_router)
app.include_router(insights_router)


@app.on_event("startup")
def startup_event():
    """Warms up commodity cache at application startup."""
    try:
        from engine.resolver.hierarchy import warm_commodity_cache
        warm_commodity_cache()
    except Exception as exc:
        logger.warning(f"Failed to warm commodity cache on startup: {exc}")


@app.get("/")
def root():
    return {
        "status": "online",
        "app": "Aavaran AI API",
        "docs": "/docs",
        "health": "/health",
        "engine_version": ENGINE_VERSION,
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "Aavaran AI API",
        "engine_version": ENGINE_VERSION,
        "kb_version": KB_VERSION,
        "ruleset_version": RULESET_VERSION,
    }
