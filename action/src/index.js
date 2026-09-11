'use strict';

const core = require('@actions/core');
const github = require('@actions/github');

const { sanitizeLog } = require('./sanitize');
const { findCurrentJob, findFailedJobs, fetchJobLogText } = require('./fetch-logs');
const { runDiagnosis, getShareUrl } = require('./run-diagnosis');
const { buildCommentBody, postComment } = require('./post-comment');

/**
 * Diagnoses a single failed job and posts a comment for it. Shared by both
 * trigger patterns (if: failure() has exactly one job to handle; workflow_run
 * may have several).
 */
async function diagnoseAndPostForJob(octokit, repo, job, sha, options) {
  core.info(`Fetching logs for job "${job.name}" (id ${job.id})...`);
  const rawLog = await fetchJobLogText(octokit, repo, job.id);

  const { sanitized, redactionCount } = sanitizeLog(rawLog);
  if (redactionCount > 0) {
    core.info(`Sanitized ${redactionCount} possible secret(s) out of the fetched log before diagnosis.`);
  }

  const diagnosis = await runDiagnosis(sanitized, {
    cliCommand: options.cliCommand,
    apiUrl: options.apiUrl,
  });

  const shareUrl = await getShareUrl(sanitized, options.websiteUrl);

  const body = buildCommentBody(job, diagnosis, shareUrl);
  const result = await postComment(octokit, repo, sha, body);

  core.info(
    `Posted diagnosis for "${job.name}" as a ${result.target} comment` +
      (result.number ? ` (PR #${result.number}).` : ` (${result.sha}).`)
  );
  return result;
}

/**
 * @param {{ octokit?: object, context?: object }} [overrides] - injection
 *   point for tests (see test/simulate.js): pass a fake octokit/context to
 *   run the exact same orchestration logic without hitting the real GitHub
 *   API. Production use (the `require.main === module` call below) passes
 *   nothing, and gets the real @actions/github client + context.
 */
async function run(overrides = {}) {
  try {
    const token = core.getInput('github-token', { required: true });
    const apiUrl = core.getInput('whyfail-api-url') || undefined;
    const websiteUrl = core.getInput('website-url') || undefined;
    const cliCommand = core.getInput('whyfail-cli') || 'npx --yes whyfail@latest';
    const jobNameFilter = core.getInput('job-name') || undefined;

    const octokit = overrides.octokit || github.getOctokit(token);
    const context = overrides.context || github.context;
    const repo = context.repo;
    const options = { apiUrl, websiteUrl, cliCommand };

    let posted = false;

    if (context.eventName === 'workflow_run') {
      // Separate watcher workflow: the target run has already fully
      // completed, so there may be several failed jobs to diagnose.
      const run = context.payload.workflow_run;
      const failedJobs = await findFailedJobs(octokit, repo, run.id, jobNameFilter);

      if (failedJobs.length === 0) {
        core.info('No failed jobs found on the watched workflow run.');
      }

      for (const job of failedJobs) {
        await diagnoseAndPostForJob(octokit, repo, job, run.head_sha, options);
        posted = true;
      }
    } else {
      // Primary pattern: this step runs with `if: failure()` inside the
      // same job that just failed.
      const jobName = process.env.GITHUB_JOB;
      const job = await findCurrentJob(octokit, repo, context.runId, jobName, process.env.RUNNER_NAME);

      if (!job) {
        core.setFailed(`Could not find the current job ("${jobName}") in this workflow run.`);
        return;
      }

      await diagnoseAndPostForJob(octokit, repo, job, context.sha, options);
      posted = true;
    }

    core.setOutput('posted', String(posted));
  } catch (err) {
    core.setFailed(err instanceof Error ? err.message : String(err));
  }
}

module.exports = { run, diagnoseAndPostForJob };

if (require.main === module) {
  run();
}
