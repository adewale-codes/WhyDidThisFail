import re

from .base import ParsedSignal

ERR_LINE_RE = re.compile(r"^\s*(?:npm|pnpm) ERR!.*$", re.MULTILINE)
NPM_CODE_RE = re.compile(r"npm ERR! code (\S+)")
PNPM_CODE_RE = re.compile(r"(ERR_PNPM_\w+)")
PATH_RE = re.compile(r"npm ERR! path (\S+)")
NOISE_PREFIXES = ("A complete log of this run",)


class NpmParser:
    """Parses npm/pnpm CLI error output (dependency resolution, missing
    scripts, missing files, version conflicts)."""

    def parse(self, log: str) -> ParsedSignal:
        err_lines = ERR_LINE_RE.findall(log)

        code = None
        m = NPM_CODE_RE.search(log)
        if m:
            code = m.group(1)
        else:
            m = PNPM_CODE_RE.search(log)
            if m:
                code = m.group(1)

        message = ""
        for line in err_lines:
            stripped = re.sub(r"^\s*(?:npm|pnpm) ERR!\s*", "", line).strip()
            if not stripped:
                continue
            if stripped.startswith("code "):
                continue
            if any(stripped.startswith(p) for p in NOISE_PREFIXES):
                continue
            message = stripped
            break

        file_ = None
        pm = PATH_RE.search(log)
        if pm:
            file_ = pm.group(1)

        context = "\n".join(err_lines)[-2500:] if err_lines else log.strip()[-1500:]

        return ParsedSignal(
            format="npm",
            error_type=code,
            message=message,
            file=file_,
            context=context,
            extra={"error_lines": err_lines},
        )
