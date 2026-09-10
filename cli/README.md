# whyfail

A thin CLI client for the WhyDidThisFail? API (see the repo root for the
Phase 1 service). It has no diagnosis logic of its own -- it collects the
failing log text, POSTs it to `/diagnose`, and prints the result.

## Usage

```bash
# Piped input -- the core workflow: pipe a failing command straight in
some-failing-command 2>&1 | npx whyfail

# From a saved log file (e.g. downloaded from a CI run)
npx whyfail ./build.log

# Interactive paste (for a failure you only have in a CI dashboard, Slack, etc.)
npx whyfail --paste
```

## Options

| Flag | Description |
| --- | --- |
| `--json` | print the raw API response as JSON, for scripting |
| `--format <type>` | hint the log format (`python` \| `npm` \| `docker`) instead of auto-detecting |
| `--api-url <url>` | override the API base URL |
| `-h`, `--help` | show usage |

## API URL resolution

`--api-url` flag > `WHYFAIL_API_URL` env var > `http://localhost:8000`.

## Output

Results are visually tagged by where they came from:

- `✓ KNOWN ISSUE — pattern-matched` -- matched a known, common error in the
  API's pattern database. Fast, and the fix has been seen before.
- `✨ AI ANALYSIS — novel issue` -- no known pattern matched; this is
  Claude's best-effort analysis of something new.

Every result shows the detected format, the extracted error signal (so you
can confirm the tool found the right error), cause, explanation, fix, and
copy-pasteable exact commands.

## Exit codes

`0` on any successful diagnosis (pattern-matched or LLM). Non-zero only on
a genuine tool error: the API was unreachable, the input couldn't be read,
or no input was provided at all. There's no pass/fail verdict here, so
exit code doesn't encode one.

## Development

```bash
npm link   # from this directory, to test `whyfail` locally as if installed
```

Zero runtime dependencies -- relies on Node's built-in `fetch` (Node >= 18).
