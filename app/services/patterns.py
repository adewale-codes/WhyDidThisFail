"""A small, hand-curated database of known error signatures per format.

Each Pattern's `matcher` decides (deterministically, no LLM) whether a
ParsedSignal is a known case, and returns a re.Match (or True) that `build`
can use to fill in dynamic details like the missing module name. This list
is meant to grow over time as more common failures are identified -- it is
intentionally narrow for Phase 1 rather than trying to catch everything,
so that genuinely novel errors fall through to the LLM instead of being
mismatched against a vague catch-all.
"""

import re
from dataclasses import dataclass
from typing import Callable, Optional

from .parsers.base import ParsedSignal


@dataclass
class Pattern:
    id: str
    format: str
    description: str
    matcher: Callable[[ParsedSignal], object]
    build: Callable[[ParsedSignal, object], dict]


def _static(cause: str, explanation: str, fix: str, commands: list[str]):
    def _build(signal: ParsedSignal, match: object) -> dict:
        return {"cause": cause, "explanation": explanation, "fix": fix, "commands": commands}

    return _build


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

_MODULE_NOT_FOUND_RE = re.compile(r"No module named '([^']+)'")


def _match_module_not_found(signal: ParsedSignal):
    if signal.error_type not in ("ModuleNotFoundError", "ImportError"):
        return None
    return _MODULE_NOT_FOUND_RE.search(signal.message)


def _build_module_not_found(signal: ParsedSignal, match: re.Match) -> dict:
    module = match.group(1)
    top_level = module.split(".")[0]
    return {
        "cause": f"The package providing '{module}' is not installed in the current Python environment.",
        "explanation": (
            f"Python looked for a module named '{module}' on sys.path and couldn't find it. "
            "This almost always means the package isn't installed, is installed in a different "
            "virtual environment/interpreter than the one running the code, or the module name "
            "differs from the pip package name."
        ),
        "fix": (
            f"Install the package that provides '{top_level}' into the environment you're running "
            "with, and double-check you're using the interpreter/virtualenv you think you are."
        ),
        "commands": [
            f"pip install {top_level}",
            "python -c \"import sys; print(sys.executable)\"",
        ],
    }


_CIRCULAR_IMPORT_RE = re.compile(r"cannot import name '([^']+)' from partially initialized module '([^']+)'")


def _match_circular_import(signal: ParsedSignal):
    if signal.error_type != "ImportError":
        return None
    return _CIRCULAR_IMPORT_RE.search(signal.message) or (
        "circular import" in signal.message.lower()
    )


def _build_circular_import(signal: ParsedSignal, match) -> dict:
    detail = ""
    if isinstance(match, re.Match):
        name, module = match.group(1), match.group(2)
        detail = f" Specifically, '{name}' was being imported from '{module}' before '{module}' had finished initializing."
    return {
        "cause": "Two modules import each other (directly or via a chain), creating a circular import.",
        "explanation": (
            "Module A starts importing module B before module A has finished running its own "
            "top-level code. If B then tries to import a name from A, that name doesn't exist "
            "yet because A is only partially initialized." + detail
        ),
        "fix": (
            "Break the cycle: move the shared code into a third module both sides import, move the "
            "import inside the function that needs it (deferred import), or import the module itself "
            "(`import module`) instead of specific names, and reference `module.name` at call time."
        ),
        "commands": [],
    }


_NONE_ATTRIBUTE_RE = re.compile(r"'NoneType' object has no attribute '([^']+)'")


def _match_none_attribute(signal: ParsedSignal):
    if signal.error_type != "AttributeError":
        return None
    return _NONE_ATTRIBUTE_RE.search(signal.message)


def _build_none_attribute(signal: ParsedSignal, match: re.Match) -> dict:
    attr = match.group(1)
    return {
        "cause": f"Something that was expected to be an object is actually None, and code then accessed '.{attr}' on it.",
        "explanation": (
            "This usually happens when a function that can return None (e.g. dict.get, re.match, "
            "or a function with an implicit fallthrough return) is used without checking the result "
            f"before accessing '.{attr}' on it."
        ),
        "fix": (
            f"Find where the value became None before the '.{attr}' access (check the traceback's "
            "file/line) and either handle the None case explicitly or fix why it wasn't set."
        ),
        "commands": [],
    }


def _match_file_not_found(signal: ParsedSignal):
    return signal.error_type == "FileNotFoundError"


_FILE_NOT_FOUND_PATH_RE = re.compile(r"No such file or directory: '([^']+)'")


def _build_file_not_found(signal: ParsedSignal, match) -> dict:
    m = _FILE_NOT_FOUND_PATH_RE.search(signal.message)
    path = m.group(1) if m else None
    return {
        "cause": f"The path{f' {path}' if path else ''} doesn't exist at the time the code tried to open it.",
        "explanation": (
            "This is typically caused by a relative path being resolved against the wrong working "
            "directory, a file that hasn't been created/downloaded yet, or a typo in the path."
        ),
        "fix": "Verify the path is correct and exists, and check what the process's working directory is when it runs.",
        "commands": [f"ls -la {path}" if path else "pwd"],
    }


PYTHON_PATTERNS = [
    Pattern("py-module-not-found", "python", "ModuleNotFoundError / ImportError: No module named X",
            _match_module_not_found, _build_module_not_found),
    Pattern("py-circular-import", "python", "ImportError caused by a circular import",
            _match_circular_import, _build_circular_import),
    Pattern("py-none-attribute", "python", "AttributeError on a None value",
            _match_none_attribute, _build_none_attribute),
    Pattern("py-file-not-found", "python", "FileNotFoundError",
            _match_file_not_found, _build_file_not_found),
]


# ---------------------------------------------------------------------------
# npm / pnpm
# ---------------------------------------------------------------------------

def _match_eresolve(signal: ParsedSignal):
    return signal.error_type == "ERESOLVE"


def _build_eresolve(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "npm can't find a set of dependency versions that satisfies every package's peer dependency requirements.",
        "explanation": (
            "One installed (or requested) package declares a peerDependency version range that "
            "conflicts with what another package, or the root project, requires. Since npm 7, this "
            "is a hard error instead of a warning."
        ),
        "fix": (
            "Update the conflicting package(s) to versions whose peer dependency ranges are "
            "compatible. If you're confident the mismatch is safe, you can force npm to ignore it, "
            "but that's a workaround, not a fix."
        ),
        "commands": [
            "npm install --legacy-peer-deps",
            "npm ls <package> (see which packages require conflicting versions)",
        ],
    }


def _match_missing_script(signal: ParsedSignal):
    return re.search(r"Missing script:\s*\"?([^\"]+)\"?", signal.message)


def _build_missing_script(signal: ParsedSignal, match: re.Match) -> dict:
    script = match.group(1)
    return {
        "cause": f"There's no script named '{script}' defined in package.json.",
        "explanation": (
            f"`npm run {script}` looks up the \"{script}\" key under \"scripts\" in package.json. "
            "It doesn't exist -- either it was never added, renamed, or you're in the wrong package "
            "in a monorepo."
        ),
        "fix": f"Add a '{script}' entry to package.json's \"scripts\", or run the correct existing script.",
        "commands": ["npm run", "cat package.json"],
    }


def _match_enoent_package_json(signal: ParsedSignal):
    if signal.error_type != "ENOENT":
        return None
    return signal.file and signal.file.endswith("package.json")


def _build_enoent_package_json(signal: ParsedSignal, match) -> dict:
    return {
        "cause": f"npm couldn't find a package.json at {signal.file}.",
        "explanation": (
            "npm commands need to be run from inside a directory that has a package.json (or a "
            "descendant of one), and the file wasn't found at the expected path."
        ),
        "fix": "Run npm from the project's root directory, or create a package.json with `npm init` if this is a new project.",
        "commands": ["npm init -y", "ls package.json"],
    }


def _match_e404(signal: ParsedSignal):
    return signal.error_type == "E404"


def _build_e404(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "npm tried to install a package/version that doesn't exist in the configured registry.",
        "explanation": (
            "This is usually a typo in the package name, a version that was never published (or was "
            "unpublished), or a private package that the current registry/auth can't see."
        ),
        "fix": "Double-check the package name and version, and confirm your npm registry/auth config points at the right place.",
        "commands": ["npm view <package> versions", "npm config get registry"],
    }


def _match_eacces(signal: ParsedSignal):
    return signal.error_type == "EACCES"


def _build_eacces(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "npm doesn't have filesystem permission to write to the target directory.",
        "explanation": (
            "This is common when installing global packages with a Node install owned by root/admin, "
            "or when node_modules was previously created by a different user (e.g. inside Docker)."
        ),
        "fix": (
            "Fix ownership of the npm/global directories, or use a Node version manager (nvm/fnm) so "
            "npm never needs elevated permissions -- avoid running npm with sudo."
        ),
        "commands": ["npm config get prefix", "sudo chown -R $(whoami) <printed prefix path>"],
    }


NPM_PATTERNS = [
    Pattern("npm-eresolve", "npm", "ERESOLVE peer dependency conflict", _match_eresolve, _build_eresolve),
    Pattern("npm-missing-script", "npm", "Missing script in package.json", _match_missing_script, _build_missing_script),
    Pattern("npm-enoent-package-json", "npm", "ENOENT: package.json not found", _match_enoent_package_json, _build_enoent_package_json),
    Pattern("npm-e404", "npm", "E404: package/version not found in registry", _match_e404, _build_e404),
    Pattern("npm-eacces", "npm", "EACCES: permission denied", _match_eacces, _build_eacces),
]


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

def _match_copy_failed(signal: ParsedSignal):
    return signal.error_type == "COPY_FAILED" or "not found" in signal.message.lower() and "COPY" in str(
        signal.extra.get("command", "")
    ).upper()


def _build_copy_failed(signal: ParsedSignal, match) -> dict:
    cmd = signal.extra.get("command", "")
    return {
        "cause": "The COPY instruction references a source path that doesn't exist in the build context.",
        "explanation": (
            f"'{cmd}' couldn't find its source file/directory. This happens when the path is relative "
            "to the wrong location (the build context, not the Dockerfile's directory), it's excluded "
            "by .dockerignore, or the file simply wasn't created before the build ran."
        ),
        "fix": (
            "Check the path is correct relative to the build context root, confirm it isn't listed in "
            ".dockerignore, and make sure the file exists before running `docker build`."
        ),
        "commands": ["cat .dockerignore", "ls -la <path from the COPY instruction>"],
    }


def _match_apt_get(signal: ParsedSignal):
    cmd = str(signal.extra.get("command", ""))
    return "apt-get" in cmd and (
        "Unable to locate package" in signal.message
        or "Unable to locate package" in signal.context
        or "Could not get lock" in signal.context
    )


def _build_apt_get(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The `apt-get install` step failed because the package index is stale or a package name is wrong.",
        "explanation": (
            "Docker layer caching means an old `apt-get update` layer can be reused even after the "
            "package list changes upstream, or the RUN step installs a package before ever running "
            "`apt-get update` in that layer."
        ),
        "fix": (
            "Make sure `apt-get update` runs in the same RUN instruction as `apt-get install` (so "
            "Docker can't cache a stale index separately), and verify the package name."
        ),
        "commands": ["RUN apt-get update && apt-get install -y <package>"],
    }


def _match_pip_install(signal: ParsedSignal):
    cmd = str(signal.extra.get("command", ""))
    return "pip install" in cmd and (
        "No matching distribution found" in signal.context or "Could not find a version" in signal.context
    )


def _build_pip_install(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "pip couldn't find a version of a required package that matches the requested constraints for this image's Python/platform.",
        "explanation": (
            "This is usually a version pin in requirements.txt that doesn't have a wheel for the "
            "base image's Python version or CPU architecture, forcing a build from source that then "
            "fails, or a genuinely nonexistent version."
        ),
        "fix": "Loosen or update the offending version pin in requirements.txt, or switch the base image to match the package's supported Python version.",
        "commands": ["pip index versions <package>"],
    }


def _match_npm_install_in_docker(signal: ParsedSignal):
    cmd = str(signal.extra.get("command", ""))
    return bool(re.search(r"npm (ci|install)", cmd)) and "npm ERR!" in signal.context


def _build_npm_install_in_docker(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The `npm install`/`npm ci` RUN step failed inside the image build.",
        "explanation": (
            "The underlying npm error is in the step output above -- common causes inside a Docker "
            "build specifically are package.json/package-lock.json not being COPYed in before this "
            "step, or a private registry that isn't reachable/authenticated from inside the build."
        ),
        "fix": "Check the npm error text in this step's output; ensure package.json and the lockfile are COPYed before the install RUN step so Docker's layer cache is used correctly.",
        "commands": ["docker build --progress=plain ."],
    }


DOCKER_PATTERNS = [
    Pattern("docker-copy-failed", "docker", "COPY source path not found", _match_copy_failed, _build_copy_failed),
    Pattern("docker-apt-get", "docker", "apt-get install failure", _match_apt_get, _build_apt_get),
    Pattern("docker-pip-install", "docker", "pip install failure inside RUN", _match_pip_install, _build_pip_install),
    Pattern("docker-npm-install", "docker", "npm install/ci failure inside RUN", _match_npm_install_in_docker, _build_npm_install_in_docker),
]


PATTERNS_BY_FORMAT: dict[str, list[Pattern]] = {
    "python": PYTHON_PATTERNS,
    "npm": NPM_PATTERNS,
    "docker": DOCKER_PATTERNS,
}


def match_pattern(signal: ParsedSignal) -> Optional[tuple[Pattern, dict]]:
    """Return (pattern, built_result) for the first confident match, or None."""
    for pattern in PATTERNS_BY_FORMAT.get(signal.format, []):
        match = pattern.matcher(signal)
        if match:
            return pattern, pattern.build(signal, match)
    return None
