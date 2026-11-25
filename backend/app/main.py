"""FastAPI app: POST /audits, GET /audits, GET /audits/{id}."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.config import get_settings
from app.db import Audit, get_session, init_db
from app.extractor import extract_signals
from app.fetcher import FetchError, fetch_page
from app.llm import LLMError, score_page
from app.schemas import AuditCreate, AuditDetail, AuditList, AuditSummary

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aeo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AEO Page Auditor", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _error(status: int, code: str, message: str, headers: dict | None = None) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message}, headers=headers)


def _to_detail(audit: Audit, cached: bool = False) -> AuditDetail:
    return AuditDetail(
        id=audit.id,
        url=audit.url,
        final_url=audit.final_url,
        overall_score=audit.overall_score,
        model=audit.model,
        created_at=audit.created_at,
        signals=audit.signals,
        report=audit.report,
        input_tokens=audit.input_tokens,
        output_tokens=audit.output_tokens,
        latency_ms=audit.latency_ms,
        llm_latency_ms=audit.llm_latency_ms,
        cached=cached,
    )


@app.post("/audits", response_model=AuditDetail, status_code=201)
async def create_audit(
    body: AuditCreate,
    request: Request,
    response: Response,
    refresh: bool = Query(False, description="Ignore the 24h cache and re-audit."),
    session: AsyncSession = Depends(get_session),
):
    url = str(body.url)
    normalized = cache.normalize_url(url)

    # 1. Cache: same URL audited in the last 24h -> return the saved audit.
    #    Cache hits don't count toward the rate limit; they cost nothing.
    if not refresh:
        cached_id = await cache.get_cached_audit_id(normalized)
        if cached_id and (audit := await session.get(Audit, cached_id)):
            response.status_code = 200
            return _to_detail(audit, cached=True)

    # 2. Rate limit: 10 fresh audits per hour per client IP.
    client_ip = request.client.host if request.client else "unknown"
    try:
        await cache.check_rate_limit(client_ip)
    except cache.RateLimitExceeded as exc:
        raise _error(
            429,
            "rate_limited",
            f"Limit is {get_settings().rate_limit_per_hour} audits per hour. Try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        )

    started = time.perf_counter()

    # 3. Fetch safely, 4. extract signals in code (in a thread: parsing is CPU-bound).
    try:
        page = await fetch_page(url)
    except FetchError as exc:
        raise _error(exc.status_code, exc.code, str(exc))
    signals = await asyncio.to_thread(extract_signals, page.html, page.final_url, page.encoding)

    # 5. Score with the LLM (validated + one retry inside score_page).
    try:
        result = await score_page(signals, page.final_url)
    except LLMError as exc:
        log.warning("LLM scoring failed for %s: %s", url, exc)
        raise _error(exc.status_code, exc.code, str(exc))

    # 6. Persist and cache.
    audit = Audit(
        url=url,
        normalized_url=normalized,
        final_url=page.final_url,
        signals=signals.model_dump(),
        report=result.report.model_dump(),
        overall_score=result.report.overall_score,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=int((time.perf_counter() - started) * 1000),
        llm_latency_ms=result.latency_ms,
    )
    session.add(audit)
    await session.commit()
    await session.refresh(audit)
    await cache.cache_audit_id(normalized, audit.id)
    return _to_detail(audit)


@app.get("/audits", response_model=AuditList)
async def list_audits(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(
        select(Audit).order_by(Audit.created_at.desc()).limit(limit).offset(offset)
    )
    total = await session.scalar(select(func.count()).select_from(Audit))
    items = [
        AuditSummary(
            id=a.id,
            url=a.url,
            final_url=a.final_url,
            overall_score=a.overall_score,
            model=a.model,
            created_at=a.created_at,
        )
        for a in rows
    ]
    return AuditList(items=items, total=total or 0)


@app.get("/audits/{audit_id}", response_model=AuditDetail)
async def get_audit(audit_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    audit = await session.get(Audit, audit_id)
    if not audit:
        raise _error(404, "not_found", "Audit not found.")
    return _to_detail(audit)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = await cache.ping()
    status = 200 if db_ok else 503
    return JSONResponse({"db": db_ok, "redis": redis_ok}, status_code=status)
