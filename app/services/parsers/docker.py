import re

from .base import ParsedSignal

# BuildKit output, e.g.:
#   #8 [5/7] RUN npm install
#   #8 0.523 npm ERR! code E404
#   #8 ERROR: process "/bin/sh -c npm install" did not complete successfully: exit code: 1
BUILDKIT_STEP_RE = re.compile(r"^#(\d+) \[([^\]]+)\] (.+)$", re.MULTILINE)
BUILDKIT_ERROR_RE = re.compile(r"^#(\d+) ERROR: (.+)$", re.MULTILINE)
FAILED_TO_SOLVE_RE = re.compile(r"^failed to solve: (.+)$", re.MULTILINE)

# Legacy (non-BuildKit) output, e.g.:
#   Step 5/10 : RUN npm install
#    ---> Running in 3f1a2b3c4d5e
#   The command '/bin/sh -c npm install' returned a non-zero code: 1
LEGACY_STEP_RE = re.compile(r"^Step (\d+/\d+) : (.+)$", re.MULTILINE)
LEGACY_FAILED_CMD_RE = re.compile(r"The command '(.+)' returned a non-zero code: (\d+)")
COPY_FAILED_RE = re.compile(r"COPY failed: (.+)")

SH_C_RE = re.compile(r"^/bin/(?:sh|bash) -c (.+)$")


def _inner_command(raw_cmd: str) -> str:
    m = SH_C_RE.match(raw_cmd)
    return m.group(1) if m else raw_cmd


class DockerParser:
    """Parses Docker build output (both classic and BuildKit) to find which
    layer/step failed and what command was running when it did."""

    def parse(self, log: str) -> ParsedSignal:
        buildkit_steps = {num: (stage, cmd) for num, stage, cmd in BUILDKIT_STEP_RE.findall(log)}

        if buildkit_steps:
            err_num, err_msg = None, None
            m = BUILDKIT_ERROR_RE.search(log)
            if m:
                err_num, err_msg = m.groups()
            else:
                m = FAILED_TO_SOLVE_RE.search(log)
                if m:
                    err_msg = m.group(1)

            if err_num and err_num in buildkit_steps:
                stage, cmd = buildkit_steps[err_num]
                step_lines = re.findall(
                    rf"^#{err_num} (?:\d+\.\d+ )?(.*)$", log, re.MULTILINE
                )
                context = "\n".join(step_lines).strip()[-2500:]
                instruction = cmd.split(None, 1)[0].upper() if cmd else None
                cmd = _inner_command(re.sub(r"^\w+\s+", "", cmd, count=1)) if cmd else cmd
                return ParsedSignal(
                    format="docker",
                    error_type=instruction,
                    message=err_msg or f"Step failed: {cmd}",
                    context=context or log.strip()[-2000:],
                    extra={"step": stage, "command": cmd, "buildkit": True},
                )

            if err_msg:
                return ParsedSignal(
                    format="docker",
                    message=err_msg,
                    context=log.strip()[-2000:],
                    extra={"buildkit": True},
                )

        legacy_steps = LEGACY_STEP_RE.findall(log)
        m = LEGACY_FAILED_CMD_RE.search(log)
        if m:
            failed_cmd, exit_code = m.groups()
            last_step_num = legacy_steps[-1][0] if legacy_steps else None
            inner_cmd = _inner_command(failed_cmd)
            snippet = log
            if last_step_num:
                idx = log.rfind(f"Step {last_step_num} :")
                if idx != -1:
                    snippet = log[idx:]
            context = snippet.strip()[-2500:]
            return ParsedSignal(
                format="docker",
                error_type=f"exit_code_{exit_code}",
                message=f"Command failed: {inner_cmd}",
                context=context,
                extra={
                    "step": last_step_num,
                    "command": inner_cmd,
                    "exit_code": int(exit_code),
                    "buildkit": False,
                },
            )

        m = COPY_FAILED_RE.search(log)
        if m:
            last_step = legacy_steps[-1] if legacy_steps else (None, None)
            return ParsedSignal(
                format="docker",
                error_type="COPY_FAILED",
                message=m.group(1),
                context=log.strip()[-1500:],
                extra={"step": last_step[0], "command": last_step[1], "buildkit": False},
            )

        tail = log.strip()[-1500:]
        return ParsedSignal(format="docker", message=tail, context=tail, extra={})
