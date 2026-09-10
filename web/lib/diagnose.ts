// Server-only. Thin client for the Phase 1 WhyDidThisFail? API -- no
// diagnosis logic lives here, same rule as the Phase 2 CLI.

import { getApiBaseUrl } from "./config";
import type { DiagnoseResponse } from "./types";

export class DiagnoseApiError extends Error {}

export async function callDiagnoseApi(
  log: string,
  formatHint?: string | null
): Promise<DiagnoseResponse> {
  const base = getApiBaseUrl();

  let res: Response;
  try {
    res = await fetch(`${base}/diagnose`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ log, format_hint: formatHint || undefined }),
      cache: "no-store",
    });
  } catch (err) {
    throw new DiagnoseApiError(
      `Could not reach the diagnosis API at ${base}: ${(err as Error).message}`
    );
  }

  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    throw new DiagnoseApiError(`API at ${base} returned a non-JSON response (HTTP ${res.status}).`);
  }

  if (!res.ok) {
    const detail =
      (body as { detail?: string } | null)?.detail || `HTTP ${res.status}`;
    throw new DiagnoseApiError(`Diagnosis failed: ${detail}`);
  }

  return body as DiagnoseResponse;
}
