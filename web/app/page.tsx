import PasteBox from "@/components/PasteBox";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center px-4">
      <div className="flex w-full flex-col items-center pt-16 pb-10 text-center sm:pt-24">
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          WhyDidThisFail?
        </h1>
        <p className="mt-3 max-w-xl text-base text-muted">
          Paste a build, test, or deploy failure. Get the real cause, an explanation, and the
          exact commands to fix it -- not 40 lines of noise.
        </p>
      </div>

      <PasteBox />

      <div className="mt-24 w-full border-t border-border pt-10 pb-20">
        <h2 className="text-lg font-semibold text-foreground">How it works</h2>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div className="rounded-xl border border-pattern-border bg-pattern-bg p-4">
            <p className="text-sm font-semibold text-pattern-text">✓ Known issue</p>
            <p className="mt-1 text-sm text-foreground/80">
              Your log is checked against a curated database of common, well-understood errors
              first -- a ModuleNotFoundError, an ERESOLVE conflict, a failed Docker RUN step. When
              it matches, the fix is instant and it&apos;s been seen before.
            </p>
          </div>
          <div className="rounded-xl border border-llm-border bg-llm-bg p-4">
            <p className="text-sm font-semibold text-llm-text">✨ Novel issue</p>
            <p className="mt-1 text-sm text-foreground/80">
              When nothing in the pattern database confidently matches, the extracted error is
              sent to Claude for a fresh, best-effort diagnosis. Every result says which path it
              took, so you always know what you&apos;re looking at.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
