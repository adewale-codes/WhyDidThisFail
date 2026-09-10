import type { ReactNode } from "react";
import type { StoredResult } from "@/lib/types";
import SourceBadge from "./SourceBadge";
import CommandBlock from "./CommandBlock";
import ShareButtons from "./ShareButtons";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h2 className="text-sm font-semibold tracking-wide text-muted uppercase">{title}</h2>
      <div className="text-base leading-relaxed text-foreground">{children}</div>
    </section>
  );
}

export default function ResultView({
  record,
  shareUrl,
}: {
  record: StoredResult;
  shareUrl: string;
}) {
  const { result } = record;
  const { error_signal: signal } = result;
  const errorLine = [signal.error_type, signal.message].filter(Boolean).join(": ");

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <SourceBadge source={result.source} patternId={result.pattern_id} />
        <ShareButtons shareUrl={shareUrl} format={result.detected_format} cause={result.cause} />
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-pattern-border bg-pattern-bg px-4 py-3 text-sm text-pattern-text">
        <span aria-hidden="true">🔒</span>
        <span>
          This log was sanitized on our server before anything was stored -- common secret
          patterns (API keys, tokens, passwords, connection strings) were stripped and replaced
          with <code className="font-mono">[REDACTED]</code> before this page ever existed.
          {record.redactionCount > 0 && (
            <>
              {" "}
              <strong>{record.redactionCount}</strong> possible secret
              {record.redactionCount === 1 ? " was" : "s were"} redacted from this submission.
            </>
          )}
        </span>
      </div>

      <Section title="Detected format">
        <span className="inline-block rounded-md border border-border bg-surface px-2.5 py-1 font-mono text-sm">
          {result.detected_format}
        </span>
      </Section>

      <Section title="Error signal">
        <div className="space-y-2">
          <p className="font-mono text-sm break-words">{errorLine || "(no message extracted)"}</p>
          {signal.file && (
            <p className="text-sm text-muted">
              {signal.file}
              {signal.line ? `:${signal.line}` : ""}
            </p>
          )}
          {signal.context && (
            <pre className="max-h-64 overflow-auto rounded-lg border border-code-border bg-code-bg p-3 font-mono text-xs whitespace-pre-wrap break-words text-foreground/90">
              {signal.context}
            </pre>
          )}
        </div>
      </Section>

      <Section title="Cause">
        <p>{result.cause}</p>
      </Section>

      <Section title="Explanation">
        <p>{result.explanation}</p>
      </Section>

      <Section title="Fix">
        <p>{result.fix}</p>
      </Section>

      {result.commands.length > 0 && (
        <Section title="Commands">
          <CommandBlock commands={result.commands} />
        </Section>
      )}
    </div>
  );
}
