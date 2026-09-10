# WhyDidThisFail? — Phase 1

Core log-parsing engine and API. Detects the log format, extracts the real
failure signal, matches it against a database of known errors, and falls
back to Claude only when nothing matches confidently.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload
```

## API

`POST /diagnose`

```json
{ "log": "<raw text>", "format_hint": "python | npm | docker (optional)" }
```

Response includes `detected_format`, `error_signal` (the extracted
error/file/line/context), `cause`, `explanation`, `fix`, `commands`, and
`source` (`"pattern"` or `"llm"`) + `pattern_id` when it's a pattern match —
so it's always visible whether an answer is a known, common issue or
Claude's best-effort analysis of something novel.

```bash
curl -s localhost:8000/diagnose -H 'content-type: application/json' \
  -d "$(python -c "import json,sys; print(json.dumps({'log': open('sample_logs/python_modulenotfound.txt').read()}))")"
```

## Layout

- `app/services/detector.py` — classifies raw log text as `python` / `npm` / `docker` / `unknown`.
- `app/services/parsers/` — one parser per format, all returning a common `ParsedSignal`.
- `app/services/patterns.py` — the known-error database (grows over time).
- `app/services/llm_diagnose.py` — Claude fallback, forced structured JSON output via tool use.
- `app/services/diagnose.py` — orchestrates detect → parse → pattern match → (maybe) LLM.

## Manual acceptance check

`python scripts/manual_test.py` runs the three pattern-match paths fully
offline (no API key needed) against real-shaped sample logs in
`sample_logs/`, and confirms the deliberately unusual error
(`unusual_error.txt`, a numpy broadcast `ValueError` that isn't in the
pattern database) correctly finds no pattern match:

- `python_modulenotfound.txt` → detected `python`, matched `py-module-not-found`, no LLM call.
- `npm_eresolve.txt` → detected `npm`, matched `npm-eresolve`, no LLM call.
- `docker_run_fail.txt` (BuildKit `npm ci` failure) → detected `docker`, correctly identifies step `4/7` / command `npm ci`, matched `docker-npm-install`, no LLM call.
- `unusual_error.txt` → detected `python`, no pattern matches, escalates to the LLM path.

This was also verified end-to-end through the actual FastAPI endpoint (not
just the internal functions) via `TestClient` — all three known cases return
`"source": "pattern"` with the right `pattern_id`, and the unusual case
correctly attempts the LLM call (it fails cleanly with a 502 in this
sandbox since no `ANTHROPIC_API_KEY` is configured here). To confirm the LLM
path actually produces a diagnosis end-to-end, set a real key and POST
`sample_logs/unusual_error.txt` to `/diagnose` — the response should have
`"source": "llm"` and a `cause` specific to the shape mismatch, not a
pattern-matched answer.

## Project layout

This repo is built in phases, each a thin layer over the last:

- `app/` — **Phase 1**: this API. All diagnosis logic lives here.
- `cli/` — **Phase 2**: `npx whyfail`, a thin CLI client. See `cli/README.md`.
- `web/` — **Phase 3**: the website (paste box + shareable result pages). See `web/README.md`.
