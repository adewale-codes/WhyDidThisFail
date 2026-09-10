import re

from .base import ParsedSignal

# Modern Terraform (0.15+) wraps each error in a box:
#   ╷
#   │ Error: <summary>
#   │
#   │   on main.tf line 12, in resource "aws_instance" "example":
#   │   12: resource "aws_instance" "example" {
#   │
#   │ <detail text>
#   ╵
# This is usually the *only* thing in the output worth looking at -- unlike
# Docker/GitHub Actions, there's rarely much noise to cut through here, so
# the parser's job is mostly to not over-extract.
BOX_START_RE = re.compile(r"^╷\s*$", re.MULTILINE)
BOX_END_RE = re.compile(r"^╵\s*$", re.MULTILINE)
BOX_SUMMARY_RE = re.compile(r"^│\s*Error:\s*(.+)$", re.MULTILINE)

# Fallback for older Terraform (pre-0.15) or `-no-color` output that never
# used box-drawing characters at all.
PLAIN_ERROR_RE = re.compile(r"^Error:\s*(.+)$", re.MULTILINE)

FILE_LINE_RE = re.compile(r"\bon (?P<file>\S+) line (?P<line>\d+)")


class TerraformParser:
    """Parses `terraform plan`/`apply` failures: a provider error, a state
    lock error, or a config/resource error, almost always presented as one
    clean, self-contained error block."""

    def parse(self, log: str) -> ParsedSignal:
        starts = [m.start() for m in BOX_START_RE.finditer(log)]
        ends = [m.start() for m in BOX_END_RE.finditer(log)]

        if starts:
            block_start = starts[0]
            block_end = next((e for e in ends if e > block_start), len(log))
            block = log[block_start:block_end]
            total_blocks = len(starts)
        else:
            m = PLAIN_ERROR_RE.search(log)
            if not m:
                tail = log.strip()[-1500:]
                return ParsedSignal(format="terraform", message=tail, context=tail)
            block = log[m.start() :][:2000]
            total_blocks = 1

        summary_match = BOX_SUMMARY_RE.search(block) or PLAIN_ERROR_RE.search(block)
        message = summary_match.group(1).strip() if summary_match else block.strip()[:300]

        file_line_match = FILE_LINE_RE.search(block)
        file_ = file_line_match.group("file") if file_line_match else None
        line_ = int(file_line_match.group("line")) if file_line_match else None

        context = block.strip()[-2000:]

        return ParsedSignal(
            format="terraform",
            message=message,
            file=file_,
            line=line_,
            context=context,
            extra={"total_error_blocks": total_blocks},
        )
