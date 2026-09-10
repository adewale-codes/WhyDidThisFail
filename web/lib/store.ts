// Server-only. Persistence for shareable diagnosis results, backed by
// Postgres (see lib/db.ts). Same exported function shapes as the
// file-based version this replaced -- saveResult / getResult -- so nothing
// else in the app needed to change.

import crypto from "node:crypto";
import { getPool, StorageNotConfiguredError } from "./db";
import type { DiagnoseResponse, StoredResult } from "./types";

export { StorageNotConfiguredError };

const ID_PATTERN = /^[A-Za-z0-9_-]{6,32}$/;

function generateId(): string {
  return crypto.randomBytes(7).toString("base64url");
}

interface Diagnosis {
  cause: string;
  explanation: string;
  fix: string;
  commands: string[];
  pattern_id: string | null;
}

interface ResultRow {
  id: string;
  format: string;
  source: "pattern" | "llm";
  sanitized_log: string;
  redaction_count: number;
  error_signal: DiagnoseResponse["error_signal"];
  diagnosis: Diagnosis;
  created_at: Date;
}

function rowToStoredResult(row: ResultRow): StoredResult {
  return {
    id: row.id,
    createdAt: row.created_at.toISOString(),
    sanitizedLog: row.sanitized_log,
    redactionCount: row.redaction_count,
    result: {
      detected_format: row.format,
      error_signal: row.error_signal,
      cause: row.diagnosis.cause,
      explanation: row.diagnosis.explanation,
      fix: row.diagnosis.fix,
      commands: row.diagnosis.commands,
      source: row.source,
      pattern_id: row.diagnosis.pattern_id,
    },
  };
}

export async function saveResult(
  data: Omit<StoredResult, "id" | "createdAt">
): Promise<StoredResult> {
  // Throws StorageNotConfiguredError if DATABASE_URL isn't set -- the
  // caller (the /api/diagnose route) turns that into a clear 503 instead
  // of a crash.
  const pool = await getPool();

  let id = generateId();
  for (let attempt = 0; attempt < 5; attempt++) {
    const existing = await pool.query("SELECT 1 FROM results WHERE id = $1", [id]);
    if (existing.rowCount === 0) break;
    id = generateId();
  }

  const { result } = data;
  const diagnosis: Diagnosis = {
    cause: result.cause,
    explanation: result.explanation,
    fix: result.fix,
    commands: result.commands,
    pattern_id: result.pattern_id,
  };

  const inserted = await pool.query<ResultRow>(
    `INSERT INTO results (id, format, source, sanitized_log, redaction_count, error_signal, diagnosis)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     RETURNING *`,
    [
      id,
      result.detected_format,
      result.source,
      data.sanitizedLog,
      data.redactionCount,
      JSON.stringify(result.error_signal),
      JSON.stringify(diagnosis),
    ]
  );

  return rowToStoredResult(inserted.rows[0]);
}

export async function getResult(id: string): Promise<StoredResult | null> {
  // Guards against path traversal / malformed ids before it ever reaches a
  // query (ids are also a plain TEXT primary key, not a file path, but the
  // format check is still the right place to reject garbage input early).
  if (!ID_PATTERN.test(id)) return null;

  let pool;
  try {
    pool = await getPool();
  } catch (err) {
    // No DATABASE_URL configured: the honest answer to "is this id stored"
    // is "no" -- a 404, not a crash.
    if (err instanceof StorageNotConfiguredError) return null;
    throw err;
  }

  const res = await pool.query<ResultRow>("SELECT * FROM results WHERE id = $1", [id]);
  if (res.rowCount === 0) return null;
  return rowToStoredResult(res.rows[0]);
}
