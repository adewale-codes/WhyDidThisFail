export default function SourceBadge({
  source,
  patternId,
}: {
  source: "pattern" | "llm";
  patternId?: string | null;
}) {
  if (source === "pattern") {
    return (
      <div className="inline-flex flex-col gap-0.5">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-pattern-border bg-pattern-bg px-3 py-1 text-sm font-semibold text-pattern-text">
          ✓ Known issue — pattern matched
        </span>
        {patternId && (
          <span className="pl-1 text-xs text-muted">matched pattern: {patternId}</span>
        )}
      </div>
    );
  }

  return (
    <div className="inline-flex flex-col gap-0.5">
      <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-llm-border bg-llm-bg px-3 py-1 text-sm font-semibold text-llm-text">
        ✨ AI analysis — novel issue
      </span>
      <span className="pl-1 text-xs text-muted">
        no known pattern matched — this is Claude&apos;s best-effort diagnosis
      </span>
    </div>
  );
}
