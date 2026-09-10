import re

from .base import ParsedSignal

# A full job log is a sequence of steps, each opened by the runner with a
# "##[group]Run <name>" line (the raw runner-log equivalent of the little
# expandable step headers in the GitHub UI) and closed with "##[endgroup]".
# Everything between one step's start and the next belongs to that step.
STEP_START_RE = re.compile(r"##\[group\]Run (.+)$", re.MULTILINE)

# Emitted by the runner itself when a step's process exits non-zero --
# always present on a failing step, but often generic ("Process completed
# with exit code 1").
RUNNER_ERROR_RE = re.compile(r"##\[error\](.+)$", re.MULTILINE)

# GitHub's own workflow-command annotation syntax, e.g.:
#   ::error file=src/index.ts,line=10,col=5,title=TS2322::Type 'string' is not assignable...
#   ::error::Something went wrong
# Tools and custom scripts emit these deliberately, so when present they're
# usually more specific than the runner's generic exit-code message.
ANNOTATION_RE = re.compile(r"::error(?:\s+([^:]*))?::(.*)$", re.MULTILINE)


def _parse_annotation_params(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    params = {}
    for part in raw.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            params[key.strip()] = value.strip()
    return params


class GithubActionsParser:
    """Parses a GitHub Actions job log to find which step failed among
    however many succeeded, preferring GitHub's own ::error:: annotations
    (specific) over the runner's generic exit-code message when both are
    present."""

    def parse(self, log: str) -> ParsedSignal:
        steps = [(m.start(), m.group(1).strip()) for m in STEP_START_RE.finditer(log)]

        annotation = ANNOTATION_RE.search(log)
        runner_error = RUNNER_ERROR_RE.search(log)
        candidates = [m for m in (annotation, runner_error) if m]

        if not candidates:
            tail = log.strip()[-1500:]
            return ParsedSignal(format="github_actions", message=tail, context=tail)

        # Whichever failure signal appears first in the log is the one that
        # actually broke things -- not a later, downstream symptom.
        primary = min(candidates, key=lambda m: m.start())

        step_idx = None
        step_name = None
        for i, (start, name) in enumerate(steps):
            if start <= primary.start():
                step_idx = i
                step_name = name
            else:
                break

        if primary is annotation:
            params = _parse_annotation_params(annotation.group(1))
            message = annotation.group(2).strip()
            file_ = params.get("file")
            line_raw = params.get("line")
            line_ = int(line_raw) if line_raw and line_raw.isdigit() else None
            error_type = params.get("title")
        else:
            message = runner_error.group(1).strip()
            file_, line_, error_type = None, None, None

        if step_idx is not None:
            span_start = steps[step_idx][0]
            span_end = steps[step_idx + 1][0] if step_idx + 1 < len(steps) else len(log)
            context = log[span_start:span_end].strip()[-2500:]
        else:
            context = log.strip()[-2000:]

        return ParsedSignal(
            format="github_actions",
            error_type=error_type,
            message=message,
            file=file_,
            line=line_,
            context=context,
            extra={"step": step_name},
        )
