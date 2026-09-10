"""Manual acceptance check against the sample logs (see README).

Runs the pattern-match path fully offline. For the "unusual" log, it only
confirms that no pattern matched (i.e. it *would* escalate to the LLM)
without requiring ANTHROPIC_API_KEY, since that call needs network + a key.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services.detector import detect_format
from app.services.diagnose import PARSERS
from app.services.patterns import match_pattern

SAMPLES = {
    "python": "python_modulenotfound.txt",
    "npm": "npm_eresolve.txt",
    "docker": "docker_run_fail.txt",
}

SAMPLE_DIR = pathlib.Path(__file__).resolve().parent.parent / "sample_logs"


def check(name: str, filename: str, expected_format: str) -> None:
    log = (SAMPLE_DIR / filename).read_text()
    detected = detect_format(log)
    print(f"--- {name} ---")
    print(f"expected format: {expected_format} | detected: {detected}")
    assert detected == expected_format, f"FAIL: expected {expected_format}, got {detected}"

    signal = PARSERS[detected].parse(log)
    print(f"error_type={signal.error_type!r} message={signal.message!r}")
    print(f"file={signal.file!r} line={signal.line!r}")
    if signal.extra:
        print(f"extra keys: {list(signal.extra.keys())}")

    matched = match_pattern(signal)
    if matched:
        pattern, result = matched
        print(f"PATTERN MATCH: {pattern.id}")
        print(f"cause: {result['cause']}")
        print(f"fix: {result['fix']}")
        print(f"commands: {result['commands']}")
    else:
        print("NO PATTERN MATCH -> would escalate to LLM")
    print()


def check_unusual() -> None:
    log = (SAMPLE_DIR / "unusual_error.txt").read_text()
    detected = detect_format(log)
    print("--- unusual (should fall through to LLM) ---")
    print(f"detected: {detected}")
    assert detected == "python"
    signal = PARSERS[detected].parse(log)
    print(f"error_type={signal.error_type!r} message={signal.message!r}")
    matched = match_pattern(signal)
    assert matched is None, f"FAIL: expected no pattern match, got {matched[0].id}"
    print("Confirmed: no pattern matched, would correctly escalate to the LLM path.")
    print()


if __name__ == "__main__":
    check("Python ModuleNotFoundError", SAMPLES["python"], "python")
    check("npm ERESOLVE", SAMPLES["npm"], "npm")
    check("Docker RUN failure (npm ci)", SAMPLES["docker"], "docker")
    check_unusual()
    print("All offline checks passed.")
