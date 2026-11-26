import json
from types import SimpleNamespace

import pytest

from app import llm
from app.extractor import extract_signals

SIGNALS = extract_signals("<title>T</title><h1>H</h1>", "https://example.com/")
FIX = {"priority": "high", "issue": "No FAQ schema.", "before": "(missing)", "after": '{"@type": "FAQPage"}'}
VALID = {
    "overall_score": 62,
    "sub_scores": {"answerability": 60, "content_structure": 70, "entity_clarity": 65, "schema_markup": 40, "trust_signals": 70},
    "fixes": [FIX] * 5,
}


def fake_gemini(monkeypatch, *texts):
    calls = []

    async def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=texts[len(calls) - 1], usage_metadata=SimpleNamespace(total_token_count=100))

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(llm.genai, "Client", lambda: client)
    return calls


async def test_valid_output(monkeypatch):
    calls = fake_gemini(monkeypatch, json.dumps(VALID))
    report, tokens = await llm.score_page(SIGNALS)
    assert report.overall_score == 62 and tokens == 100 and len(calls) == 1
    assert "<page_signals>" in calls[0]["contents"]


async def test_retries_once_on_invalid_output(monkeypatch):
    out_of_range = {**VALID, "overall_score": 150}
    calls = fake_gemini(monkeypatch, json.dumps(out_of_range), json.dumps(VALID))
    report, tokens = await llm.score_page(SIGNALS)
    assert len(calls) == 2 and tokens == 200


async def test_clean_error_after_two_invalid_outputs(monkeypatch):
    fake_gemini(monkeypatch, "not json", json.dumps({**VALID, "fixes": [FIX] * 3}))
    with pytest.raises(llm.LLMError):
        await llm.score_page(SIGNALS)
