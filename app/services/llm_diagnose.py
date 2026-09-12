"""Fallback diagnosis via Claude, used only when patterns.py has no confident
match. Uses the Messages API's structured-outputs feature (`output_format`
on `messages.parse()`) so the response is schema-validated JSON with the
same shape as a pattern-database result -- no free-text parsing.
"""

import logging
import os

import anthropic
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from .parsers.base import ParsedSignal

logger = logging.getLogger(__name__)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# Confirmed empirically against the live API (see the investigation for the
# production 500 this replaced): with claude-opus-5, a real diagnosis for a
# non-trivial log runs ~900-1024+ output tokens, and adaptive thinking draws
# from the *same* budget -- at max_tokens=1024 the response hit stop_reason
# "max_tokens" and got cut off mid-JSON-string, which is exactly what broke
# structured-output parsing in production. 4096 leaves ~4x headroom over
# observed real usage (confirmed stop_reason="end_turn" well under budget).
MAX_TOKENS = 4096

TRUNCATED_MESSAGE = "The AI analysis didn't complete successfully (its response was incomplete). Please try again."

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
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            output_format=DiagnosisOutput,
        )
    except anthropic.APIStatusError as e:
        message = e.body.get("error", {}).get("message") if isinstance(e.body, dict) else str(e)
        raise RuntimeError(f"LLM diagnosis failed ({e.status_code}): {message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError(f"Could not reach the Anthropic API: {e}") from e
    except ValidationError as e:
        # The API call itself succeeded, but the response text wasn't
        # complete/valid JSON -- almost always a truncated response.
        # Never let this reach the client as a raw pydantic/JSON stack
        # trace -- same fail-visibly rule as every other LLM failure mode
        # here (see the except clauses above).
        logger.warning("LLM structured output failed to parse (likely a truncated response): %s", e)
        raise RuntimeError(TRUNCATED_MESSAGE) from e

    if response.parsed_output is None:
        # A second, distinct truncation shape: at a severe enough cutoff
        # the model can be stopped before emitting *any* text block at all
        # (e.g. fully consumed by adaptive thinking), so .parse() returns
        # successfully with nothing to parse rather than raising -- calling
        # .model_dump() on that blindly raises a raw AttributeError instead
        # of the ValidationError case above. response.stop_reason is
        # genuinely available here (unlike in the except block above),
        # so it's worth actually logging: this confirms whether it really
        # was max_tokens or something else, not just an assumption.
        logger.warning(
            "LLM response had no parsed output at all (stop_reason=%s) -- treating as truncated.",
            response.stop_reason,
        )
        raise RuntimeError(TRUNCATED_MESSAGE)

    return response.parsed_output.model_dump()
