import { NextRequest, NextResponse } from "next/server";
import { sanitizeLog } from "@/lib/sanitize";
import { callDiagnoseApi, DiagnoseApiError } from "@/lib/diagnose";
import { saveResult, StorageNotConfiguredError } from "@/lib/store";

const MAX_LOG_LENGTH = 200_000;

export async function POST(req: NextRequest) {
  let body: { log?: unknown; format_hint?: unknown };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const rawLog = typeof body.log === "string" ? body.log : "";
  if (!rawLog.trim()) {
    return NextResponse.json({ error: "`log` must not be empty." }, { status: 400 });
  }
  if (rawLog.length > MAX_LOG_LENGTH) {
    return NextResponse.json(
      { error: `Log is too large (max ${MAX_LOG_LENGTH.toLocaleString()} characters).` },
      { status: 400 }
    );
  }
  const formatHint = typeof body.format_hint === "string" ? body.format_hint : undefined;

  // Sanitize before this log touches anything else -- the diagnosis call
  // included. See lib/sanitize.ts.
  const { sanitized, redactionCount } = sanitizeLog(rawLog);

  let result;
  try {
    result = await callDiagnoseApi(sanitized, formatHint);
  } catch (err) {
    if (err instanceof DiagnoseApiError) {
      return NextResponse.json({ error: err.message }, { status: 502 });
    }
    throw err;
  }

  let record;
  try {
    record = await saveResult({
      sanitizedLog: sanitized,
      redactionCount,
      result,
    });
  } catch (err) {
    if (err instanceof StorageNotConfiguredError) {
      return NextResponse.json({ error: err.message }, { status: 503 });
    }
    throw err;
  }

  return NextResponse.json({ id: record.id });
}
