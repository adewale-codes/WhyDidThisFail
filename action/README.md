# WhyDidThisFail? Action

Automatically diagnoses your own failed CI job and posts the cause,
explanation, and fix as a comment -- no copy-pasting a log anywhere. This
is the distribution surface with the least friction of all: Phase 2's CLI
still needs someone to paste a log in; Phase 3's website still needs
someone to paste a log in; this needs nothing after you add it once.

It does not implement any diagnosis logic itself -- it fetches the failed
job's log, sanitizes it, shells out to the Phase 2 `whyfail` CLI (which
calls the Phase 1 API), and posts the result. See "Sanitization" below for
why the sanitizing step matters even though the CLI is reused.

## Usage (primary pattern: a separate watcher workflow)

Add one workflow file that watches for other workflows completing, and
diagnoses any that failed:

```yaml
# .github/workflows/diagnose-failures.yml
name: Diagnose failures
on:
  workflow_run:
    workflows: ["*"]        # or name specific workflows
    types: [completed]

jobs:
  diagnose:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    steps:
      - uses: your-org/whydidthisfail-action@v1
        with:
          website-url: https://whyfail.example.com   # optional, for a shareable link
```

No changes to any existing workflow file are needed -- this watches
everything (or specific named workflows) from one place, and correctly
handles a run with more than one failed job (each gets its own comment).
This is the only pattern confirmed to work reliably; see below.

## Usage (do NOT use: `if: failure()` self-fetch)

An earlier version of this Action recommended adding a step with
`if: failure()` directly inside the job you want diagnosed, so it could
fetch and diagnose its own job's logs with no second workflow file. **This
does not work, and can't be made to work** -- confirmed against a real
GitHub repo and GitHub's actual API behavior, not assumed. See "Why
`if: failure()` doesn't work" below before considering it. The code path
still exists (`fetch-logs.js`'s `findCurrentJob`) but is not a supported or
documented usage; it will reliably fail with a 404, now with a clear
explanation instead of a bare `Unknown error`.

### Why `if: failure()` doesn't work

Fetching job logs via `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`
(`downloadJobLogsForWorkflowRun` in Octokit) requires the job to have
reached `completed` status. GitHub's own docs don't state this explicitly,
but real-world reports do: the API returns a plain `404` while a job is
still `in_progress` ([community report, confirmed 404-while-running,
resolves after completion](https://github.com/orgs/community/discussions/154834)).

That alone would just make this *flaky*. What makes it a hard, unconditional
limitation is a step further: a job can only reach `completed` status after
*every one of its own steps finishes* -- including a diagnosis step running
with `if: failure()` inside that same job. That step is, by definition,
still executing while the job is `in_progress`. So the job it wants its own
logs for can never have reached `completed` yet, at the exact moment it
asks. This isn't timing-sensitive or occasionally unlucky; it fails every
time, for every job, unconditionally, as a direct consequence of how "job
completion" is defined -- not something a retry or a delay works around.

`workflow_run` fires on a *different* run's completion (the one you're
watching, not the watcher's own run), so by the time the watcher job asks
for that run's job logs, they're genuinely finalized. That's the entire
reason it's the primary pattern now.

## Inputs

| Input | Required | Default | Purpose |
| --- | --- | --- | --- |
| `github-token` | no | `${{ github.token }}` | Used to fetch job logs and post comments. |
| `whyfail-api-url` | no | (CLI's own default) | Phase 1 API base URL, if not the public default. |
| `website-url` | no | _(unset)_ | Phase 3 website base URL. When set, the comment includes a link to a full shareable result page. When unset, the comment is posted without one -- this never blocks posting the diagnosis itself. |
| `whyfail-cli` | no | `npx --yes whyfail@latest` | How to invoke the CLI. Override for local/dogfood testing against an unpublished CLI, e.g. `node /path/to/cli/bin/cli.js`. |
| `job-name` | no | _(unset, = all)_ | `workflow_run` pattern only: restrict diagnosis to a specific job name. |

## Outputs

| Output | Description |
| --- | --- |
| `posted` | `"true"` if at least one comment was posted, `"false"` otherwise. |

## Permissions

The default `GITHUB_TOKEN` needs:

```yaml
permissions:
  contents: write        # read for checkout; write is needed for the commit-comment fallback
  actions: read          # to fetch job logs
  pull-requests: write   # to post PR comments
  issues: write          # PR comments are posted via the issues API
```

If you don't set `permissions:` explicitly, most repos' defaults already
cover this; private repos with restrictive default token permissions may
need to add the block above.

## Sanitization

Real CI logs frequently contain real secrets by accident. This is worth
stating explicitly rather than assuming it's inherited for free: **neither
the Phase 2 CLI nor the Phase 1 API sanitize anything.** The CLI is a thin
client (Phase 2's whole design point), and the API's job is diagnosis, not
data hygiene -- sanitization was built once, in Phase 3, as a step the
*website's* own submission route runs before persisting anything.

This action does not go through the website's submission route to get its
primary diagnosis (it shells out to the CLI directly, per the no-duplicated-
diagnosis-logic principle). So it carries its own copy of the same
sanitization rules (`src/sanitize.js`, a straight port of
`web/lib/sanitize.ts` -- same rule set, kept in sync deliberately) and runs
it on every fetched log **before** that log touches the CLI, the Phase 1
API, or (if `website-url` is set) the website submission used to build the
share link. Nothing fetched by this action reaches any of those three
places unsanitized.

`test/simulate.js` proves this isn't just an assumption: it feeds a log
containing a fake AWS key and a fake token through the real pipeline (real
sanitizer, real CLI subprocess, real local Phase 1 API) and asserts the
posted comment's error-signal snippet shows `[REDACTED]`, not the secret.

## Testing

GitHub Actions' own APIs (job logs, PR/commit comments) can't be exercised
against a real repo from this environment. `test/simulate.js` mocks the
octokit client (and the relevant `GITHUB_*`/`INPUT_*` env vars) and
exercises the *entire rest of the pipeline for real*: real sanitization,
a real `whyfail` CLI subprocess, a real (locally running) Phase 1 API,
real comment-body formatting, and the real PR-vs-commit-comment routing
decision.

Run it yourself (needs the Phase 1 API running locally -- see the repo
root README):

```bash
cd action
npm install
node test/simulate.js
```

**What this proves:**
- The action correctly identifies its own job from a run's job list (by
  name, and by runner name when a matrix build reuses a job name).
- A fetched log is sanitized before it reaches the CLI -- verified by
  inspecting the actual diagnosis response's error-signal content, not
  just the final comment text.
- The CLI subprocess integration genuinely works end-to-end against a real
  API, for both a pattern-matched and (separately, in the Phase 1/2/4
  test suites) an LLM-escalated result.
- Comment routing: PR comment when a PR is associated with the commit,
  commit comment otherwise.
- The `workflow_run` pattern correctly uses the *watched* run's id, not
  its own watcher run's id.
- The website share-link integration builds the right URL on success and
  degrades to no link (never a crash) on failure or when unconfigured.
- A 404 from `downloadJobLogsForWorkflowRun` during self-fetch gets turned
  into the "confirmed GitHub API limitation, use workflow_run" explanation,
  not left as a bare `Unknown error` or misapplied to the `workflow_run`
  path where a 404 would mean something else entirely.

**Resolved by a real GitHub repo test (was previously an open question in
this section):** whether `if: failure()` self-fetch actually works. It
does not, unconditionally -- confirmed by an actual run against a real
repo (which surfaced the `Unknown error` this section used to be vague
about) plus GitHub API research (see "Why `if: failure()` doesn't work"
above). This is why `workflow_run` is now the primary pattern instead of
an alternative.

**What simulation still does NOT and cannot prove, and needs a real repo
run of the `workflow_run` pattern specifically to confirm** (see "Plan for
re-testing" below -- this hasn't been done yet):
- That `downloadJobLogsForWorkflowRun` returns complete, correctly-shaped
  logs for a job in a run that a *watcher* workflow observes -- the
  mocked octokit in `test/simulate.js` returns a canned string for this
  call, it doesn't confirm the real response shape (documented as a
  redirect; `fetch-logs.js` handles both a direct string body and a
  `{ url }` pointer, but which one Octokit actually surfaces in practice
  is still unconfirmed).
- That `workflow_run` actually fires promptly and reliably for a
  `workflow_dispatch`-triggered target run, and that `filter: 'latest'`
  picks the right attempt.
- Real `listPullRequestsAssociatedWithCommit` behavior across edge cases
  (forked PRs, multiple open PRs on one commit).
- How the posted Markdown actually renders on github.com, or Marketplace
  listing/install behavior.

## Plan for re-testing `workflow_run` against a real repo

Same rigor as the test that found the `if: failure()` problem -- an actual
failure, not a simulation:

1. `.github/workflows/test-action-target.yml`: the same deliberately-failing
   job as before, but with no diagnosis step at all (just the failure).
2. `.github/workflows/test-action-watcher.yml`: `on: workflow_run` watching
   that target workflow by name, `if: conclusion == 'failure'`, running
   `uses: ./action` (with the same `npm ci` + local-CLI-path overrides the
   previous test needed) against the target run's id.
3. Trigger the target workflow manually, wait for it to fail and fully
   complete, then confirm the watcher run fires, fetches real logs from
   the now-completed target run, and posts a real comment -- on the commit
   (no PR exists for a manually-dispatched branch push) with the correct
   diagnosis content.
4. If that succeeds: delete or keep both files (they're harmless, manual-
   trigger-only). If it surfaces another gap, apply the same
   diagnose-with-real-detail-first discipline this round did rather than
   guessing at a fix.

## Publishing

Structurally ready for the Marketplace (`action.yml` has `branding`, typed
inputs/outputs, `runs.using: node20`), but not yet bundled for
distribution. Before publishing:

1. `cd action && npm install --omit=dev` (already has no dev dependencies)
   and either commit `node_modules/`, or bundle with
   `npx @vercel/ncc build src/index.js -o dist` and point `action.yml`'s
   `runs.main` at `dist/index.js` instead -- Marketplace actions must be
   self-contained, since nothing runs `npm install` for you.
2. Tag a release (`v1`, plus a floating major tag per GitHub's convention).
3. Publish via the repo's Releases page with "Publish this Action to the
   GitHub Marketplace" checked.
