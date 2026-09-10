# WhyDidThisFail? — web

The Phase 3 website: a landing page with a paste box, and a shareable
result page per diagnosis (`/r/[id]`). Calls the Phase 1 API for all
diagnosis logic -- nothing here re-implements detection, parsing, pattern
matching, or the LLM fallback.

## Setup

```bash
npm install
cp .env.local.example .env.local   # point WHYFAIL_API_URL and DATABASE_URL at your setup
```

The Phase 1 API must be running separately (see the repo root README):

```bash
# from the repo root
uvicorn app.main:app --port 8000
```

You also need a Postgres database (`DATABASE_URL`) -- see Storage below.

## Run

```bash
npm run dev
```

## How a submission becomes a shareable link

1. The paste box (client) POSTs the raw log to `/api/diagnose` (this app's
   own route, not the Phase 1 API directly).
2. `app/api/diagnose/route.ts` sanitizes the log first (`lib/sanitize.ts`
   strips secret-shaped patterns -- API keys, tokens, passwords, connection
   strings, private key blocks -- before anything else happens to it),
   then sends the *sanitized* log to the Phase 1 API, then persists the
   sanitized log + diagnosis under a short generated id.
3. The client is redirected to `/r/{id}`, which server-renders the stored
   record.

## Storage

Results are stored in Postgres, one row per id, in a single `results` table
(`lib/db.ts` creates it automatically on first use if it doesn't exist --
no separate migration step). This replaced an earlier file-based store:
a JSON file per id doesn't survive a deploy or restart on a platform with
an ephemeral filesystem (Railway included), which defeats the point of a
*shareable* link.

Connects via `DATABASE_URL`, same convention as PackageSafe's backend and
what Railway's Postgres plugin auto-injects. If it's unset, storage is
disabled rather than crashing the process: `saveResult` throws a catchable
`StorageNotConfiguredError` that the API route turns into a clear 503, and
a one-time warning is logged so it's obvious why. `getResult` treats an
unconfigured store the same way a GET path should: no result found, a
normal 404, not an error.

To verify sanitization actually happened before storage, inspect the row
directly:

```bash
psql "$DATABASE_URL" -c "SELECT sanitized_log, error_signal FROM results WHERE id = '<id>';"
```

## Env vars

| Var | Where read | Purpose |
| --- | --- | --- |
| `WHYFAIL_API_URL` | server only | Phase 1 API base URL. Never `NEXT_PUBLIC_` -- same reasoning as the CLI's `WHYFAIL_API_URL`: it's a deployment detail, not something the client bundle should carry. |
| `DATABASE_URL` | server only | Postgres connection string for stored results. Same convention as PackageSafe. |
| `SITE_URL` | server only | Absolute base URL for share links and OG metadata. Optional; falls back to the incoming request's host. |

## Design system

Light-theme only (no dark mode), sharing conventions with sibling
portfolio projects: a single indigo brand accent, and the same
green/violet pattern-matched vs. LLM-analyzed color coding used in the
Phase 2 CLI, carried through consistently here (badges, OG image).
