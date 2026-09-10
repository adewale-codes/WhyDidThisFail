# WhyDidThisFail? — Phase 1 (+ Phase 4 format coverage)

Core log-parsing engine and API. Detects the log format, extracts the real
failure signal, matches it against a database of known errors, and falls
back to Claude only when nothing matches confidently.

Six formats are supported: Python tracebacks, npm/pnpm, Docker build
output, GitHub Actions job logs, TypeScript compiler output, and Terraform
plan/apply failures (the last three added in Phase 4, testing that the
Phase 1 parser interface actually generalizes to formats with genuinely
different shapes -- see `app/services/parsers/`).

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
{ "log": "<raw text>", "format_hint": "python | npm | docker | github_actions | typescript | terraform (optional)" }
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

- `app/services/detector.py` — classifies raw log text as one of the six formats, or `unknown`. Order matters: a format that *wraps* another (Docker wrapping npm, a GitHub Actions job wrapping anything) is checked before the format it wraps.
- `app/services/parsers/` — one parser per format, all returning a common `ParsedSignal`.
- `app/services/patterns.py` — the known-error database (28 patterns across 6 formats; grows over time).
- `app/services/llm_diagnose.py` — Claude fallback, structured JSON output via `messages.parse()`.
- `app/services/diagnose.py` — orchestrates detect → parse → pattern match → (maybe) LLM.

## Manual acceptance check

`python scripts/manual_test.py` runs all six pattern-match paths fully
offline (no API key needed) against real-shaped sample logs in
`sample_logs/`, and confirms a deliberately unusual error per format
correctly finds no pattern match:

- `python_modulenotfound.txt` → detected `python`, matched `py-module-not-found`, no LLM call.
- `npm_eresolve.txt` → detected `npm`, matched `npm-eresolve`, no LLM call.
- `docker_run_fail.txt` (BuildKit `npm ci` failure) → detected `docker`, correctly identifies step `4/7` / command `npm ci`, matched `docker-npm-install`, no LLM call.
- `github_actions_failed_step.txt` (5 successful steps, one failing `github-script` step) → detected `github_actions`, correctly identifies the failing step (`actions/github-script@v7`) rather than just "something failed", matched `gh-resource-not-accessible`, no LLM call.
- `typescript_cascade.txt` (1 root cause cascading into 3 downstream errors across 2 files) → detected `typescript`, surfaces the *first* diagnostic (`TS2307` in `src/types/user.ts`) as the primary signal rather than one of the 3 downstream `TS2339` errors it caused, matched `ts-cannot-find-module`, no LLM call.
- `terraform_state_lock.txt` → detected `terraform`, matched `tf-state-lock`, no LLM call.
- `unusual_error.txt`, `github_actions_unusual.txt`, `typescript_unusual.txt`, `terraform_unusual.txt` → each correctly finds no pattern match and would escalate to the LLM path.

This was also verified end-to-end through the running FastAPI server (not
just the internal functions) via real HTTP requests -- all six known cases
return `"source": "pattern"` with the right `pattern_id`, and all four
unusual cases correctly reach the LLM call (each fails cleanly with a 502
in this environment because the configured `ANTHROPIC_API_KEY`'s account
has an empty credit balance -- an account issue, not a code issue; the
request/auth/detection/escalation pipeline is confirmed working up to and
including the actual model call). To confirm a full LLM diagnosis
end-to-end, use a key with available credit and POST any of the `*_unusual.txt`
logs to `/diagnose` -- the response should have `"source": "llm"` and a
`cause` specific to that log, not a pattern-matched answer.

## Project layout

This repo is built in phases, each a thin layer over the last:

- `app/` — **Phase 1**: this API. All diagnosis logic lives here.
- `cli/` — **Phase 2**: `npx whyfail`, a thin CLI client. See `cli/README.md`.
- `web/` — **Phase 3**: the website (paste box + shareable result pages). See `web/README.md`.
