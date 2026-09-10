import re

from .base import ParsedSignal

# tsc's two on-disk diagnostic formats. The colon-separated one is what
# `--pretty` (an interactive TTY) prints; the paren-separated one is what
# tsc actually falls back to in most CI logs (non-TTY stdout), so both need
# to be recognized.
#   src/index.ts:10:5 - error TS2322: Type 'string' is not assignable to type 'number'.
COLON_DIAG_RE = re.compile(
    r"^(?P<file>\S.*?):(?P<line>\d+):(?P<col>\d+) - error (?P<code>TS\d+): (?P<message>.+)$",
    re.MULTILINE,
)
#   src/index.ts(10,5): error TS2322: Type 'string' is not assignable to type 'number'.
PAREN_DIAG_RE = re.compile(
    r"^(?P<file>\S.*?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<message>.+)$",
    re.MULTILINE,
)

FOUND_SUMMARY_RE = re.compile(r"Found (\d+) errors?\b")


class TypeScriptParser:
    """Parses `tsc` compiler output.

    A single root-cause error (a bad export, a wrong interface) routinely
    cascades into many downstream type errors that all disappear once it's
    fixed. Rather than treat every reported error as equally important, this
    surfaces the *first* diagnostic as the primary signal -- tsc reports
    errors in compilation order, so the first one is almost always the
    upstream cause, not a symptom of it -- and records how many followed.
    """

    def parse(self, log: str) -> ParsedSignal:
        matches = sorted(
            [*COLON_DIAG_RE.finditer(log), *PAREN_DIAG_RE.finditer(log)],
            key=lambda m: m.start(),
        )

        if not matches:
            tail = log.strip()[-1500:]
            return ParsedSignal(format="typescript", message=tail, context=tail)

        first = matches[0]
        file_ = first.group("file")
        line_ = int(first.group("line"))
        code = first.group("code")
        message = first.group("message").strip()

        summary = FOUND_SUMMARY_RE.search(log)
        total_errors = int(summary.group(1)) if summary else len(matches)

        # Context: the diagnostic line itself plus whatever tsc prints right
        # below it (the source snippet + "~~~" caret), up to the next
        # diagnostic or a reasonable cutoff.
        context_end = matches[1].start() if len(matches) > 1 else min(len(log), first.start() + 500)
        context = log[first.start() : context_end].strip()[-1500:]

        all_errors = [
            {"file": m.group("file"), "line": int(m.group("line")), "code": m.group("code")}
            for m in matches[:20]
        ]

        return ParsedSignal(
            format="typescript",
            error_type=code,
            message=message,
            file=file_,
            line=line_,
            context=context,
            extra={
                "total_errors": total_errors,
                "is_cascade": len(matches) > 1,
                "all_errors": all_errors,
            },
        )
