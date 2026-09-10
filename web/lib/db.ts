// Server-only. Postgres connection pool + schema bootstrap.
//
// Connects via DATABASE_URL, same convention as PackageSafe's backend and
// what Railway's Postgres plugin auto-injects. When it's unset (e.g. local
// dev with no database configured), we don't hard-crash the process --
// callers get a clear, catchable StorageNotConfiguredError instead, and a
// one-time warning is logged so it's obvious *why* saving/sharing isn't
// working, rather than failing silently or throwing an opaque 500.

import { Pool } from "pg";

export class StorageNotConfiguredError extends Error {
  constructor() {
    super(
      "Storage is not configured: DATABASE_URL is not set, so results cannot be saved or retrieved."
    );
    this.name = "StorageNotConfiguredError";
  }
}

export function isStorageConfigured(): boolean {
  return Boolean(process.env.DATABASE_URL);
}

let warned = false;
function warnOnce(): void {
  if (warned) return;
  warned = true;
  console.warn(
    "[whyfail] DATABASE_URL is not set -- result storage is disabled. " +
      "Set DATABASE_URL to enable saving and sharing diagnoses."
  );
}

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    format TEXT NOT NULL,
    source TEXT NOT NULL,
    sanitized_log TEXT NOT NULL,
    redaction_count INTEGER NOT NULL DEFAULT 0,
    error_signal JSONB NOT NULL,
    diagnosis JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );
`;

let pool: Pool | null = null;
let schemaReady: Promise<void> | null = null;

/**
 * Returns a ready-to-query pool with the schema already ensured, or throws
 * StorageNotConfiguredError if DATABASE_URL isn't set. Safe to call on
 * every request -- the pool and the schema-creation query are both
 * memoized for the life of the process.
 */
export async function getPool(): Promise<Pool> {
  if (!isStorageConfigured()) {
    warnOnce();
    throw new StorageNotConfiguredError();
  }

  if (!pool) {
    pool = new Pool({ connectionString: process.env.DATABASE_URL });
  }

  if (!schemaReady) {
    schemaReady = pool.query(SCHEMA_SQL).then(() => undefined);
  }
  await schemaReady;

  return pool;
}
