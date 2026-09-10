from typing import Optional

from .detector import SUPPORTED_FORMATS, detect_format
from .llm_diagnose import diagnose_with_llm
from .parsers.base import ParsedSignal
from .parsers.docker import DockerParser
from .parsers.npm import NpmParser
from .parsers.python_traceback import PythonTracebackParser
from .patterns import match_pattern

PARSERS = {
    "python": PythonTracebackParser(),
    "npm": NpmParser(),
    "docker": DockerParser(),
}


def diagnose(log: str, format_hint: Optional[str] = None) -> dict:
    fmt = format_hint if format_hint in SUPPORTED_FORMATS else detect_format(log)

    if fmt in PARSERS:
        signal = PARSERS[fmt].parse(log)
    else:
        fmt = "unknown"
        tail = log.strip()[-2000:]
        signal = ParsedSignal(format="unknown", message=tail, context=tail)

    matched = match_pattern(signal) if fmt in PARSERS else None

    if matched:
        pattern, result = matched
        return {
            "detected_format": fmt,
            "error_signal": signal.as_dict(),
            "cause": result["cause"],
            "explanation": result["explanation"],
            "fix": result["fix"],
            "commands": result["commands"],
            "source": "pattern",
            "pattern_id": pattern.id,
        }

    llm_result = diagnose_with_llm(fmt, signal, log)
    return {
        "detected_format": fmt,
        "error_signal": signal.as_dict(),
        "cause": llm_result["cause"],
        "explanation": llm_result["explanation"],
        "fix": llm_result["fix"],
        "commands": llm_result.get("commands", []),
        "source": "llm",
        "pattern_id": None,
    }
