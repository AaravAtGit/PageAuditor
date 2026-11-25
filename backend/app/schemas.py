"""Data shapes: extracted signals, the report the LLM must return, and API responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Signals(BaseModel):
    title: str | None
    meta_description: str | None
    canonical: str | None
    headings: list[str]  # e.g. "H2: Pricing"
    word_count: int
    schema_types: list[str]  # schema.org JSON-LD @types
    faq: list[str]  # questions found on the page
    internal_links: int
    external_links: int
    images: int
    images_with_alt: int
    intro_text: str  # first ~1000 chars of body text, so the LLM can suggest rewrites


Score = Field(ge=0, le=100)


class SubScores(BaseModel):
    answerability: int = Score
    content_structure: int = Score
    entity_clarity: int = Score
    schema_markup: int = Score
    trust_signals: int = Score


class Fix(BaseModel):
    priority: Literal["high", "medium", "low"]
    issue: str
    before: str
    after: str


class Report(BaseModel):
    """The strict JSON the LLM must return."""

    overall_score: int = Score
    sub_scores: SubScores
    summary: str
    fixes: list[Fix] = Field(min_length=5, max_length=5)


class AuditRequest(BaseModel):
    url: HttpUrl


class AuditOut(BaseModel):
    id: uuid.UUID
    url: str
    created_at: datetime
    model: str
    tokens_used: int
    latency_ms: int
    signals: Signals
    report: Report
    cached: bool = False


class AuditListItem(BaseModel):
    id: uuid.UUID
    url: str
    overall_score: int
    created_at: datetime
