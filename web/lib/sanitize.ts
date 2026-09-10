// Secret redaction. Runs server-side, before anything is persisted -- see
// app/api/diagnose/route.ts. This runs even before the log is sent to the
// diagnosis API, so a real secret never has to leave this boundary at all,
// not just avoid being stored.
//
// Each pattern below matches a common secret *shape*; we replace only the
// secret-looking value, not the surrounding line, so the redacted log is
// still readable and still diagnosable. Structural patterns (private key
// blocks, connection strings) run first so the generic key=value pattern
// doesn't have to also handle their shape.

const REDACTED = "[REDACTED]";

interface RedactionRule {
  name: string;
  pattern: RegExp;
  replace: (match: string, ...groups: string[]) => string;
}

const RULES: RedactionRule[] = [
  {
    name: "private-key-block",
    pattern: /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g,
    replace: () => "[REDACTED PRIVATE KEY]",
  },
  {
    // postgres://user:pass@host, mongodb+srv://user:pass@host, redis://..., amqp(s)://...
    name: "connection-string-credentials",
    pattern:
      /\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqps?):\/\/([^:\/\s@]+):([^@\/\s]+)@/gi,
    replace: (_m, scheme: string) => `${scheme}://${REDACTED}:${REDACTED}@`,
  },
  {
    // AWS access key IDs (all current prefixes), e.g. AKIAIOSFODNN7EXAMPLE
    name: "aws-access-key-id",
    pattern: /\b(?:AKIA|ABIA|ACCA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "openai-key",
    pattern: /\bsk-[A-Za-z0-9]{20,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "anthropic-key",
    pattern: /\bsk-ant-[A-Za-z0-9\-_]{20,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "github-token",
    pattern: /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "slack-token",
    pattern: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "stripe-key",
    pattern: /\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "google-api-key",
    pattern: /\bAIza[0-9A-Za-z\-_]{35}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "jwt",
    pattern: /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g,
    replace: () => REDACTED,
  },
  {
    name: "bearer-token",
    pattern: /\bBearer\s+[A-Za-z0-9\-_.=]{10,}/gi,
    replace: () => `Bearer ${REDACTED}`,
  },
  {
    // generic key=value / key: value assignments, e.g. api_key=..., password: "...",
    // token='...', DB_PASSWORD=... -- keeps the key name visible, redacts the value.
    name: "generic-assignment",
    pattern:
      /\b((?:[a-z0-9_]*(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?key|token|password|passwd|pwd|auth)[a-z0-9_]*))\s*[:=]\s*["']?([A-Za-z0-9\-_./+=]{6,})["']?/gi,
    replace: (_m, key: string) => `${key}=${REDACTED}`,
  },
];

export interface SanitizeResult {
  sanitized: string;
  redactionCount: number;
  redactedKinds: string[];
}

export function sanitizeLog(input: string): SanitizeResult {
  let text = input;
  let redactionCount = 0;
  const redactedKinds = new Set<string>();

  for (const rule of RULES) {
    text = text.replace(rule.pattern, (...args) => {
      // args: [match, ...capturedGroups, offset, fullString]
      const match = args[0] as string;
      const groups = args.slice(1, -2) as string[];
      redactionCount += 1;
      redactedKinds.add(rule.name);
      return rule.replace(match, ...groups);
    });
  }

  return { sanitized: text, redactionCount, redactedKinds: Array.from(redactedKinds) };
}
