"use client";

import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import { EXAMPLE_LOGS } from "@/lib/examples";

export default function PasteBox() {
  const [log, setLog] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const submit = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        setError("Paste or drop a log first.");
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/diagnose", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ log: trimmed }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.error || "Diagnosis failed. Please try again.");
        }
        router.push(`/r/${data.id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
        setLoading(false);
      }
    },
    [router]
  );

  function readFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => setLog(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) readFile(file);
  }

  function handleFileInput(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) readFile(file);
    e.target.value = "";
  }

  function tryExample(exampleLog: string) {
    setLog(exampleLog);
    submit(exampleLog);
  }

  return (
    <div className="w-full max-w-3xl">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`relative rounded-2xl border-2 border-dashed p-2 transition-colors ${
          dragActive ? "border-brand bg-brand/5" : "border-border bg-white"
        }`}
      >
        <textarea
          value={log}
          onChange={(e) => setLog(e.target.value)}
          placeholder={`Paste your build/test/deploy failure here...\n\nsome-failing-command 2>&1 | pbcopy   # then paste`}
          rows={12}
          className="w-full resize-y rounded-xl border-0 bg-transparent p-4 font-mono text-sm leading-relaxed text-foreground placeholder:text-muted focus:outline-none"
        />
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.log,text/plain"
        onChange={handleFileInput}
        className="hidden"
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="text-sm font-medium text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
        >
          or drop a file / click to browse
        </button>

        <button
          type="button"
          onClick={() => submit(log)}
          disabled={loading}
          className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Diagnosing…" : "Diagnose it"}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-6 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Don&apos;t have a failure handy? Try one:</span>
        {EXAMPLE_LOGS.map((ex) => (
          <button
            key={ex.id}
            type="button"
            onClick={() => tryExample(ex.log)}
            disabled={loading}
            className="rounded-full border border-border bg-surface px-3 py-1 font-medium text-foreground/80 transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-60"
          >
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  );
}
