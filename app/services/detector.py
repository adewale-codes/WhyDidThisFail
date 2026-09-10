import re

PYTHON_TRACEBACK_RE = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)
NPM_ERR_RE = re.compile(r"\bnpm ERR!")
PNPM_ERR_RE = re.compile(r"\bpnpm ERR!|ERR_PNPM_\w+")
DOCKER_BUILDKIT_STEP_RE = re.compile(r"^#\d+ \[[^\]]+\]", re.MULTILINE)
DOCKER_LEGACY_STEP_RE = re.compile(r"^Step \d+/\d+ :", re.MULTILINE)

SUPPORTED_FORMATS = ("python", "npm", "docker")


def detect_format(log: str) -> str:
    """Classify raw log text as one of the supported formats, or "unknown".

    Deliberately simple, distinctive-string heuristics -- reliable for the
    three formats in scope rather than a general-purpose classifier.
    """
    if PYTHON_TRACEBACK_RE.search(log):
        return "python"

    # Checked before the npm heuristic: a Docker build that fails inside an
    # `npm ci`/`npm install` RUN step embeds raw "npm ERR!" lines in its
    # output, so Docker's more distinctive step markers must win first.
    if (
        DOCKER_BUILDKIT_STEP_RE.search(log)
        or DOCKER_LEGACY_STEP_RE.search(log)
        or "failed to solve" in log
        or "returned a non-zero code" in log
        or "COPY failed:" in log
    ):
        return "docker"

    if NPM_ERR_RE.search(log) or PNPM_ERR_RE.search(log):
        return "npm"

    return "unknown"
