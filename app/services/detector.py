import re

PYTHON_TRACEBACK_RE = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)
NPM_ERR_RE = re.compile(r"\bnpm ERR!")
PNPM_ERR_RE = re.compile(r"\bpnpm ERR!|ERR_PNPM_\w+")
DOCKER_BUILDKIT_STEP_RE = re.compile(r"^#\d+ \[[^\]]+\]", re.MULTILINE)
DOCKER_LEGACY_STEP_RE = re.compile(r"^Step \d+/\d+ :", re.MULTILINE)
GITHUB_ACTIONS_RE = re.compile(r"##\[(?:group|endgroup|error|section)\]|::(?:error|warning|notice)\b")
TYPESCRIPT_ERROR_RE = re.compile(r"error TS\d+:")
TERRAFORM_RE = re.compile(
    r"^╷\s*$|Initializing the backend\.\.\.|Terraform will perform the following actions"
    r"|Error acquiring the state lock|\bon \S+\.tf line \d+",
    re.MULTILINE,
)

SUPPORTED_FORMATS = ("python", "npm", "docker", "github_actions", "typescript", "terraform")


def detect_format(log: str) -> str:
    """Classify raw log text as one of the supported formats, or "unknown".

    Deliberately simple, distinctive-string heuristics -- reliable for the
    formats in scope rather than a general-purpose classifier. Order
    matters: a format that *wraps* another one's output (Docker wrapping an
    npm install, a GitHub Actions job wrapping any step at all) needs to be
    checked before the format it wraps, so the wrapper's own "which step
    actually failed" structure wins over generically re-detecting whatever
    happened to be running inside it.
    """
    if PYTHON_TRACEBACK_RE.search(log):
        return "python"

    # GitHub Actions' own runner/annotation markers are distinctive enough
    # that they essentially never appear in bare tool output -- checked
    # early since a job log can wrap literally any of the other formats.
    if GITHUB_ACTIONS_RE.search(log):
        return "github_actions"

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

    # Checked before npm for the same reason: `npm run build` failing
    # because `tsc` exited non-zero prints both a TS diagnostic *and* npm's
    # own "npm ERR!" wrapper around it. The TS diagnostic is the actual,
    # specific error; npm's is just "the command failed".
    if TYPESCRIPT_ERROR_RE.search(log):
        return "typescript"

    if NPM_ERR_RE.search(log) or PNPM_ERR_RE.search(log):
        return "npm"

    if TERRAFORM_RE.search(log):
        return "terraform"

    return "unknown"
