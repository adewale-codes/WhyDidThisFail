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

## Usage (primary pattern: add as the last step of an existing job)

This is the easiest way to add this to a workflow you already have: one
step, at the end of an existing job, that only runs when something above
it failed.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm test

      # Add this as the last step. It only runs if a previous step failed,
      # and needs no extra permissions beyond what GITHUB_TOKEN already has
      # by default in most repos (see Permissions below).
      - if: failure()
        uses: your-org/whydidthisfail-action@v1
        with:
          website-url: https://whyfail.example.com  # optional, for a shareable link
```

That's it. No second workflow file, no watching for other workflows to
finish -- when this job fails, this step runs, finds its own job's logs,
diagnoses them, and comments.

## Usage (alternative pattern: a separate watcher workflow)

If you'd rather not touch existing workflow files, or you want to diagnose
failures across *every* workflow in the repo from one place, add a second
workflow that watches for `workflow_run` completions:

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
          website-url: https://whyfail.example.com
```

This pattern can diagnose more than one failed job per run (every job that
failed in the watched run gets its own comment), but it requires adding
and maintaining a second workflow file -- prefer the `if: failure()`
pattern above unless you specifically need to watch workflows you don't
want to edit directly.

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
  contents: read
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

**What this does NOT and cannot prove without a real GitHub repo and a
real failing workflow:**
- Whether `downloadJobLogsForWorkflowRun` actually returns complete,
  available logs for a job that is *still in progress* -- the exact
  situation the primary `if: failure()` pattern runs in (prior steps in
  the same job have completed, but the job overall hasn't). This is the
  single biggest open question about this design; everything downstream
  of "we got the log text" is verified.
- The exact response shape of that endpoint in practice (it's documented
  as a redirect; `fetch-logs.js` handles both a direct string body and a
  `{ url }` pointer, but which one a given octokit version actually
  surfaces isn't something this environment can observe).
- Real `listPullRequestsAssociatedWithCommit` behavior across edge cases
  (forked PRs, multiple open PRs on one commit).
- How the posted Markdown actually renders on github.com, or Marketplace
  listing/install behavior.

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
