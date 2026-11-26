import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import cache
from app.config import settings
from app.db import Audit, Session, create_tables
from app.extractor import extract_signals
from app.fetcher import FetchError, fetch_html
from app.llm import MODEL, LLMError, score_page
from app.schemas import AuditListItem, AuditOut, AuditRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="AEO Page Auditor", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.post("/audits", response_model=AuditOut)
async def create_audit(body: AuditRequest, request: Request, refresh: bool = False):
    url = str(body.url)

    if not refresh and (audit_id := await cache.get_cached_audit_id(url)):
        async with Session() as session:
            if audit := await session.get(Audit, uuid.UUID(audit_id)):
                return audit

    if await cache.is_rate_limited(request.client.host):
        raise HTTPException(429, "Rate limit reached: 10 audits per hour. Try again later.")

    start = time.perf_counter()
    try:
        html = await fetch_html(url)
        signals = extract_signals(html, url)
        report, tokens = await score_page(signals)
    except FetchError as exc:
        raise HTTPException(exc.status_code, str(exc))
    except LLMError as exc:
        raise HTTPException(502, str(exc))

    audit = Audit(
        url=url,
        signals=signals.model_dump(),
        report=report.model_dump(),
        model=MODEL,
        tokens_used=tokens,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
    async with Session() as session:
        session.add(audit)
        await session.commit()
        await session.refresh(audit)

    await cache.cache_audit_id(url, str(audit.id))
    return audit


@app.get("/audits")
async def list_audits() -> list[AuditListItem]:
    async with Session() as session:
        audits = await session.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(50))
        return [
            AuditListItem(id=a.id, url=a.url, overall_score=a.report["overall_score"], created_at=a.created_at)
            for a in audits
        ]


@app.get("/audits/{audit_id}", response_model=AuditOut)
async def get_audit(audit_id: uuid.UUID):
    async with Session() as session:
        audit = await session.get(Audit, audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found.")
    return audit
