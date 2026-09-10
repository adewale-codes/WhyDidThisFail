'use strict';

const DEFAULT_API_URL = 'http://localhost:8000';

class ToolError extends Error {}

/**
 * Calls the WhyDidThisFail API's POST /diagnose and returns the parsed
 * result. Throws ToolError for anything that means "the CLI itself
 * couldn't get a diagnosis" (unreachable API, bad response shape, API-side
 * error) -- the caller turns that into a non-zero exit code.
 */
async function diagnose(log, { apiUrl, formatHint } = {}) {
  const base = (apiUrl || process.env.WHYFAIL_API_URL || DEFAULT_API_URL).replace(/\/+$/, '');
  const url = `${base}/diagnose`;

  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ log, format_hint: formatHint || undefined }),
    });
  } catch (err) {
    throw new ToolError(`Could not reach the WhyDidThisFail API at ${base}: ${err.message}`);
  }

  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    throw new ToolError(`API at ${base} returned a non-JSON response (HTTP ${res.status}).`);
  }

  if (!res.ok) {
    const detail = (body && body.detail) || `HTTP ${res.status}`;
    throw new ToolError(`Diagnosis failed: ${detail}`);
  }

  return body;
}

module.exports = { diagnose, ToolError, DEFAULT_API_URL };
