import re

from .base import ParsedSignal

TRACEBACK_HEADER = re.compile(r"^Traceback \(most recent call last\):\s*$", re.MULTILINE)
FRAME_RE = re.compile(r'File "(?P<file>.+?)", line (?P<line>\d+), in (?P<func>.+)')
# Lines that separate chained exceptions ("raise X from Y", or a bare exception
# raised while handling another one).
CHAIN_SEPARATOR_RE = re.compile(
    r"^(During handling of the above exception, another exception occurred:|"
    r"The above exception was the direct cause of the following exception:)\s*$",
    re.MULTILINE,
)


def _split_blocks(log: str) -> list[str]:
    starts = [m.start() for m in TRACEBACK_HEADER.finditer(log)]
    if not starts:
        return []
    starts.append(len(log))
    return [log[starts[i] : starts[i + 1]] for i in range(len(starts) - 1)]


def _parse_block(block: str) -> tuple[list[tuple[str, int, str]], str | None, str, str]:
    frames = [(f, int(ln), fn) for f, ln, fn in FRAME_RE.findall(block)]

    lines = [l for l in block.splitlines() if l.strip()]
    exc_line = None
    for l in reversed(lines):
        if l.startswith("Traceback"):
            continue
        if not l.startswith((" ", "\t")):
            exc_line = l
            break

    error_type: str | None = None
    message = ""
    if exc_line:
        m = re.match(r"^([\w.]+)(?::\s*(.*))?$", exc_line)
        if m:
            error_type = m.group(1)
            message = m.group(2) or ""
        else:
            message = exc_line

    return frames, error_type, message, block


class PythonTracebackParser:
    """Parses Python tracebacks, including chained exceptions.

    The last block in the log is what actually terminated the program (the
    final_exception); the first block, when the exception is chained, is the
    original error that triggered the chain (the root_cause).
    """

    def parse(self, log: str) -> ParsedSignal:
        blocks = _split_blocks(log)
        if not blocks:
            tail = log.strip()[-1500:]
            return ParsedSignal(format="python", message=tail, context=tail)

        parsed = [_parse_block(b) for b in blocks]
        frames, error_type, message, raw = parsed[-1]

        file_, line_ = None, None
        if frames:
            file_, line_, _ = frames[-1]

        chain = [{"error_type": et, "message": msg} for (_, et, msg, _) in parsed]
        extra = {
            "is_chained": len(parsed) > 1,
            "chain": chain,
            "root_cause": chain[0] if len(parsed) > 1 else None,
            "frames": [{"file": f, "line": ln, "function": fn} for f, ln, fn in frames],
        }

        context = raw.strip()[-2500:]
        return ParsedSignal(
            format="python",
            error_type=error_type,
            message=message.strip(),
            file=file_,
            line=line_,
            context=context,
            extra=extra,
        )
