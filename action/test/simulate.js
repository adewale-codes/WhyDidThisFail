'use strict';

/**
 * Simulates the Action's environment locally: mocks the GITHUB_ and INPUT_
 * env vars GitHub Actions provides, and injects a fake octokit client (so
 * no real GitHub API calls happen) into the same run() the real action
 * entry point calls.
 *
 * What this DOES prove: log fetching -> sanitization -> diagnosis (via the
 * real Phase 2 CLI, hitting a real, locally-running Phase 1 API -- not
 * mocked) -> comment formatting -> the PR-vs-commit-comment routing
 * decision -> which octokit method gets called with what body.
 *
 * What this does NOT and CANNOT prove (see action/README.md's Testing
 * section for the full list): whether GitHub's real API actually returns
 * complete logs for a job that's still in progress (the exact situation
 * `if: failure()` runs in), the real shape of `downloadJobLogsForWorkflowRun`'s
 * redirect-following response, real PR-association lookup behavior, or
 * how the comment actually renders on github.com. Those need a real repo.
 *
 * Requires the Phase 1 API running locally (see repo root README) --
 * this intentionally does NOT mock that part, since it already exists and
 * actually running it is a stronger test than mocking it.
 */

const assert = require('node:assert');
const path = require('node:path');

const FAKE_SECRET = 'AKIAIOSFODNN7EXAMPLE';
const FAKE_TOKEN_SECRET = 'sk-abc123def456ghi789jklmno';

const LOG_WITH_SECRET = `npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR!
npm ERR! While resolving: my-app@0.1.0
npm ERR! Found: react@18.2.0
npm ERR! peer react@"^17.0.0" from react-beautiful-dnd@13.1.1
npm ERR!
npm ERR! Environment dump for debugging:
npm ERR!   AWS_ACCESS_KEY_ID=${FAKE_SECRET}
npm ERR!   DEPLOY_TOKEN=${FAKE_TOKEN_SECRET}
npm ERR!
npm ERR! Fix the upstream dependency conflict, or retry
npm ERR! this command with --force or --legacy-peer-deps.
`;

const JOB = { id: 999, name: 'build', runner_name: 'GitHub Actions 1', conclusion: 'failure' };

/**
 * A fake octokit implementing exactly the methods the action calls.
 * Records every call so tests can assert on them.
 */
function makeFakeOctokit({ associatedPrs = [] } = {}) {
  const calls = [];

  return {
    calls,
    rest: {
      actions: {
        async listJobsForWorkflowRun(params) {
          calls.push({ method: 'listJobsForWorkflowRun', params });
          return { data: { jobs: [JOB] } };
        },
        async downloadJobLogsForWorkflowRun(params) {
          calls.push({ method: 'downloadJobLogsForWorkflowRun', params });
          return { data: LOG_WITH_SECRET };
        },
      },
      repos: {
        async listPullRequestsAssociatedWithCommit(params) {
          calls.push({ method: 'listPullRequestsAssociatedWithCommit', params });
          return { data: associatedPrs };
        },
        async createCommitComment(params) {
          calls.push({ method: 'createCommitComment', params });
          return { data: { id: 1 } };
        },
      },
      issues: {
        async createComment(params) {
          calls.push({ method: 'createComment', params });
          return { data: { id: 1 } };
        },
      },
    },
  };
}

function setCommonEnv() {
  // @actions/core's getInput() maps an input name to INPUT_<NAME> by
  // uppercasing and turning *spaces* into underscores -- hyphens are left
  // as literal hyphens. Getting this wrong silently reads an empty string
  // (getInput falls back to '' rather than throwing), so it's an easy
  // mistake to not notice; verified directly against node_modules/@actions/core.
  process.env['INPUT_GITHUB-TOKEN'] = 'fake-token';
  process.env['INPUT_WHYFAIL-API-URL'] = 'http://localhost:8000';
  process.env['INPUT_WEBSITE-URL'] = ''; // exercised separately below
  process.env['INPUT_WHYFAIL-CLI'] = `node ${path.join(__dirname, '..', '..', 'cli', 'bin', 'cli.js')}`;
  process.env['INPUT_JOB-NAME'] = '';
  process.env.GITHUB_JOB = 'build';
  process.env.RUNNER_NAME = 'GitHub Actions 1';
  process.env.GITHUB_REPOSITORY = 'my-org/my-repo';
}

async function testPrCommentPath() {
  console.log('--- Test: if: failure() pattern, PR context -> PR comment ---');
  setCommonEnv();

  const { run } = require('../src/index.js');
  const octokit = makeFakeOctokit({ associatedPrs: [{ number: 42, state: 'open' }] });
  const context = {
    eventName: 'push',
    runId: 12345,
    sha: 'abc123def456',
    repo: { owner: 'my-org', repo: 'my-repo' },
    payload: {},
  };

  await run({ octokit, context });

  const fetchCall = octokit.calls.find((c) => c.method === 'downloadJobLogsForWorkflowRun');
  assert.ok(fetchCall, 'FAIL: expected the action to fetch job logs');
  assert.strictEqual(fetchCall.params.job_id, JOB.id, 'FAIL: fetched the wrong job');
  console.log(`  fetched logs for job_id=${fetchCall.params.job_id} (correctly resolved from GITHUB_JOB="build")`);

  const commentCall = octokit.calls.find((c) => c.method === 'createComment');
  assert.ok(commentCall, 'FAIL: expected a PR comment to be posted (a PR was associated with the commit)');
  assert.strictEqual(commentCall.params.issue_number, 42, 'FAIL: posted to the wrong PR');
  console.log(`  posted PR comment on #${commentCall.params.issue_number}`);

  const body = commentCall.params.body;
  assert.ok(!body.includes(FAKE_SECRET), 'FAIL: raw AWS key leaked into the posted comment');
  assert.ok(!body.includes(FAKE_TOKEN_SECRET), 'FAIL: raw token leaked into the posted comment');
  assert.ok(body.includes('[REDACTED]'), 'FAIL: expected [REDACTED] markers in the comment');
  console.log('  confirmed: no raw secret in the posted comment body, [REDACTED] present');

  assert.ok(body.includes('ERESOLVE'), 'FAIL: expected the real diagnosis (ERESOLVE) in the comment');
  assert.ok(body.includes('Known issue'), 'FAIL: expected the pattern-matched badge');
  assert.ok(body.includes('npm-eresolve'), 'FAIL: expected the specific pattern id');
  console.log('  confirmed: correct diagnosis content (pattern-matched npm-eresolve) in the comment');

  const noCommitComment = octokit.calls.find((c) => c.method === 'createCommitComment');
  assert.ok(!noCommitComment, 'FAIL: should not have posted a commit comment when a PR was found');

  console.log('PASS\n');
}

async function testCommitCommentFallback() {
  console.log('--- Test: if: failure() pattern, no PR context -> commit comment fallback ---');
  setCommonEnv();

  const { run } = require('../src/index.js');
  const octokit = makeFakeOctokit({ associatedPrs: [] });
  const context = {
    eventName: 'push',
    runId: 12345,
    sha: 'deadbeef',
    repo: { owner: 'my-org', repo: 'my-repo' },
    payload: {},
  };

  await run({ octokit, context });

  const commitCommentCall = octokit.calls.find((c) => c.method === 'createCommitComment');
  assert.ok(commitCommentCall, 'FAIL: expected a commit comment when no PR is associated with the commit');
  assert.strictEqual(commitCommentCall.params.commit_sha, 'deadbeef');
  console.log(`  posted commit comment on ${commitCommentCall.params.commit_sha}`);

  const noPrComment = octokit.calls.find((c) => c.method === 'createComment');
  assert.ok(!noPrComment, 'FAIL: should not have posted a PR comment when none is associated');

  console.log('PASS\n');
}

async function testWorkflowRunPattern() {
  console.log('--- Test: workflow_run trigger pattern (separate watcher workflow) ---');
  setCommonEnv();

  const { run } = require('../src/index.js');
  const octokit = makeFakeOctokit({ associatedPrs: [{ number: 7, state: 'open' }] });
  const context = {
    eventName: 'workflow_run',
    runId: 99999,
    sha: 'unused-for-this-trigger',
    repo: { owner: 'my-org', repo: 'my-repo' },
    payload: { workflow_run: { id: 12345, head_sha: 'run-head-sha' } },
  };

  await run({ octokit, context });

  const listJobsCall = octokit.calls.find((c) => c.method === 'listJobsForWorkflowRun');
  assert.ok(listJobsCall, 'FAIL: expected the action to list jobs for the watched run');
  assert.strictEqual(listJobsCall.params.run_id, 12345, 'FAIL: listed jobs for the wrong run');

  const commentCall = octokit.calls.find((c) => c.method === 'createComment');
  assert.ok(commentCall, 'FAIL: expected a comment for the failed job in the watched run');
  assert.strictEqual(commentCall.params.issue_number, 7);

  console.log('  correctly used workflow_run.id (not the watcher run\'s own id) and posted on the associated PR');
  console.log('PASS\n');
}

async function testShareLink() {
  console.log('--- Test: website share-link integration (fetch mocked, no real website/DB needed) ---');
  const { getShareUrl } = require('../src/run-diagnosis.js');

  const realFetch = global.fetch;
  try {
    global.fetch = async (url, opts) => {
      assert.strictEqual(url, 'https://whyfail.example.com/api/diagnose');
      const body = JSON.parse(opts.body);
      assert.ok(!body.log.includes(FAKE_SECRET), 'FAIL: raw secret would have been sent to the website');
      return { ok: true, json: async () => ({ id: 'abc123' }) };
    };
    const url = await getShareUrl('sanitized log with [REDACTED]', 'https://whyfail.example.com/');
    assert.strictEqual(url, 'https://whyfail.example.com/r/abc123');
    console.log('  correctly built the share URL from the website\'s response');

    global.fetch = async () => {
      throw new Error('network down');
    };
    const urlOnFailure = await getShareUrl('some log', 'https://whyfail.example.com/');
    assert.strictEqual(urlOnFailure, null, 'FAIL: should degrade to null, not throw, on a website error');
    console.log('  correctly degrades to no share link (not a crash) when the website is unreachable');

    let fetchCalled = false;
    global.fetch = async () => {
      fetchCalled = true;
    };
    const urlWhenUnset = await getShareUrl('some log', undefined);
    assert.strictEqual(urlWhenUnset, null);
    assert.strictEqual(fetchCalled, false, 'FAIL: should not call the website at all when website-url is unset');
    console.log('  correctly skips the website call entirely when website-url is not configured');
  } finally {
    global.fetch = realFetch;
  }

  console.log('PASS\n');
}

async function main() {
  await testPrCommentPath();
  await testCommitCommentFallback();
  await testWorkflowRunPattern();
  await testShareLink();
  console.log('All simulated tests passed.');
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
