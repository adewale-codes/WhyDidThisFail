"""Fallback diagnosis via Claude, used only when patterns.py has no confident
match. Uses the Messages API's structured-outputs feature (`output_format`
on `messages.parse()`) so the response is schema-validated JSON with the
same shape as a pattern-database result -- no free-text parsing.
"""

import os

import anthropic
from anthropic import Anthropic
from pydantic import BaseModel

from .parsers.base import ParsedSignal

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

_client: Anthropic | None = None


class DiagnosisOutput(BaseModel):
    cause: str
    explanation: str
    fix: str
    commands: list[str]


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _build_prompt(format_: str, signal: ParsedSignal, raw_log: str) -> str:
    context = signal.context or raw_log[-3000:]
    return f"""You are diagnosing a software build/runtime failure. Detected log format: "{format_}".

Extracted error signal:
- error_type: {signal.error_type}
- message: {signal.message}
- file: {signal.file}
- line: {signal.line}

Relevant log context:
```
{context}
```

This error did not match any known pattern in our database, so give your own best-effort
analysis. Identify the specific root cause (not a generic guess), explain briefly why it
happens, and give a concrete fix with the exact commands to run."""


def diagnose_with_llm(format_: str, signal: ParsedSignal, raw_log: str) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set; cannot fall back to the LLM for this diagnosis."
        )

    client = _get_client()
    prompt = _build_prompt(format_, signal, raw_log)

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            output_format=DiagnosisOutput,
        )
    except anthropic.APIStatusError as e:
        message = e.body.get("error", {}).get("message") if isinstance(e.body, dict) else str(e)
        raise RuntimeError(f"LLM diagnosis failed ({e.status_code}): {message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError(f"Could not reach the Anthropic API: {e}") from e

    return response.parsed_output.model_dump()
