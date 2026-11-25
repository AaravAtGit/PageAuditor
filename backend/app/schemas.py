"""Pydantic models: extracted signals, the LLM report contract, and API responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

# ---------------------------------------------------------------- signals ---


class Heading(BaseModel):
    level: Literal[1, 2, 3]
    text: str


class FAQItem(BaseModel):
    question: str
    answer: str
    source: Literal["jsonld", "details", "heading", "definition_list"]


class LinkCounts(BaseModel):
    internal: int
    external: int


class ImageAltCoverage(BaseModel):
    total: int
    with_alt: int  # non-empty alt text
    empty_alt: int  # alt="" (valid for decorative images)
    missing_alt: int  # no alt attribute at all
    coverage: float  # with_alt / total, 1.0 when there are no images


class Signals(BaseModel):
    title: str | None
    meta_description: str | None
    canonical: str | None
    headings: list[Heading]
    word_count: int
    jsonld_types: list[str]
    jsonld_invalid_blocks: int
    faq: list[FAQItem]
    links: LinkCounts
    images: ImageAltCoverage
    lang: str | None
    # A short plain-text excerpt of the opening content. Not raw HTML: it lets the
    # model judge answerability and write concrete before/after rewrites.
    lead_excerpt: str


# ------------------------------------------------------- LLM report contract ---

SubScoreName = Literal[
    "answerability", "content_structure", "entity_clarity", "schema_markup", "trust_signals"
]


class SubScores(BaseModel):
    answerability: int = Field(ge=0, le=100)
    content_structure: int = Field(ge=0, le=100)
    entity_clarity: int = Field(ge=0, le=100)
    schema_markup: int = Field(ge=0, le=100)
    trust_signals: int = Field(ge=0, le=100)


class Fix(BaseModel):
    priority: Literal["high", "medium", "low"]
    category: SubScoreName
    title: str = Field(min_length=3)
    issue: str = Field(min_length=3, description="What is wrong and why it hurts AI citation.")
    before: str = Field(min_length=1, description="The current text/markup, or '(missing)'.")
    after: str = Field(min_length=1, description="A concrete rewritten version.")


class AuditReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    sub_scores: SubScores
    summary: str = Field(min_length=10)
    fixes: list[Fix] = Field(min_length=5, max_length=5)


# ------------------------------------------------------------ API models ---


class AuditCreate(BaseModel):
    url: HttpUrl


class AuditSummary(BaseModel):
    id: uuid.UUID
    url: str
    final_url: str
    overall_score: int
    model: str
    created_at: datetime


class AuditDetail(AuditSummary):
    signals: Signals
    report: AuditReport
    input_tokens: int
    output_tokens: int
    latency_ms: int
    llm_latency_ms: int
    cached: bool = False


class AuditList(BaseModel):
    items: list[AuditSummary]
    total: int
