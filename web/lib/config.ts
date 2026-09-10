// Server-only. Never import this from a "use client" component -- it reads
// WHYFAIL_API_URL, which must not be exposed to the browser (no NEXT_PUBLIC_
// prefix), for the same reason PackageSafe's equivalent var is server-side
// only: the API base URL is an internal deployment detail, not something a
// client bundle should carry.

const DEFAULT_API_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const configured = process.env.WHYFAIL_API_URL || DEFAULT_API_URL;
  return configured.replace(/\/+$/, "");
}
