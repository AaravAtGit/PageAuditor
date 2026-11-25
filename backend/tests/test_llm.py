import json
from types import SimpleNamespace

import pytest

from google.genai import types

from app import llm
from app.extractor import extract_signals

SIGNALS = extract_signals("<html><head><title>T</title></head><body><h1>H</h1></body></html>", "https://e.com/")

VALID = {
    "overall_score": 62,
    "sub_scores": {
        "answerability": 60, "content_structure": 70, "entity_clarity": 65,
        "schema_markup": 40, "trust_signals": 70,
    },
    "summary": "A reasonable page with weak schema markup.",
    "fixes": [
        {
            "priority": "high", "category": "schema_markup", "title": f"Fix {i}",
            "issue": "No Organization schema.", "before": "(missing)", "after": '{"@type": "Organization"}',
        }
        for i in range(5)
    ],
}


def _response(text, finish=types.FinishReason.STOP):
    """Shaped like google-genai's GenerateContentResponse (only the fields we read)."""
    return SimpleNamespace(
        text=text,
        model_version="gemini-3.8-flash",
        usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=30, thoughts_token_count=20),
        candidates=[SimpleNamespace(finish_reason=finish)],
    )


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(*responses):
        client = FakeClient(responses)
        monkeypatch.setattr(llm, "_client", lambda: client)
        return client

    return install


async def test_valid_first_try(fake):
    client = fake(_response(json.dumps(VALID)))
    result = await llm.score_page(SIGNALS, "https://e.com/")
    assert result.report.overall_score == 62
    assert result.attempts == 1
    assert (result.input_tokens, result.output_tokens) == (100, 50)  # 30 answer + 20 thinking
    assert result.model == "gemini-3.8-flash"
    assert len(client.calls) == 1


async def test_retries_once_on_invalid_then_succeeds(fake):
    bad = {**VALID, "overall_score": 150}  # out of range: only Pydantic catches this
    client = fake(_response(json.dumps(bad)), _response(json.dumps(VALID)))
    result = await llm.score_page(SIGNALS, "https://e.com/")
    assert result.attempts == 2
    assert result.input_tokens == 200  # tokens from both attempts are counted
    retry_prompt = client.calls[1]["contents"]
    assert "previous answer was rejected" in retry_prompt


async def test_fails_cleanly_after_two_invalid(fake):
    fake(_response("not json"), _response(json.dumps({**VALID, "fixes": VALID["fixes"][:3]})))
    with pytest.raises(llm.LLMError, match="2 attempts"):
        await llm.score_page(SIGNALS, "https://e.com/")


async def test_empty_or_blocked_response_is_retried(fake):
    fake(_response(None, finish=types.FinishReason.SAFETY), _response(json.dumps(VALID)))
    result = await llm.score_page(SIGNALS, "https://e.com/")
    assert result.attempts == 2


async def test_signals_are_sent_as_untrusted_data_not_html(fake):
    client = fake(_response(json.dumps(VALID)))
    await llm.score_page(SIGNALS, "https://e.com/")
    content = client.calls[0]["contents"]
    assert "<page_signals>" in content and "<html>" not in content
    assert "untrusted" in client.calls[0]["config"].system_instruction


async def test_truncated_output_is_retried(fake):
    fake(_response('{"overall', finish=types.FinishReason.MAX_TOKENS), _response(json.dumps(VALID)))
    result = await llm.score_page(SIGNALS, "https://e.com/")
    assert result.attempts == 2


def test_schema_is_flat_and_strict():
    schema = llm.report_json_schema()
    dumped = json.dumps(schema)
    assert "$ref" not in dumped and "minLength" not in dumped
    assert schema["properties"]["overall_score"]["maximum"] == 100
    assert schema["properties"]["fixes"]["minItems"] == 5
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"overall_score", "sub_scores", "summary", "fixes"}
