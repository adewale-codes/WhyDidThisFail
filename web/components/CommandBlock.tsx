import CopyButton from "./CopyButton";

export default function CommandBlock({ commands }: { commands: string[] }) {
  if (!commands.length) return null;

  return (
    <div className="space-y-2">
      {commands.map((cmd, i) => (
        <div
          key={i}
          className="flex items-start justify-between gap-3 rounded-lg border border-code-border bg-code-bg px-3 py-2"
        >
          <code className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-sm text-foreground">
            <span className="select-none text-muted">$ </span>
            {cmd}
          </code>
          <CopyButton text={cmd} className="shrink-0" />
        </div>
      ))}
    </div>
  );
}
