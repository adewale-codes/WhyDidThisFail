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


# ---------------------------------------------------------------------------
# GitHub Actions
# ---------------------------------------------------------------------------

_MISSING_INPUT_RE = re.compile(r"Input required and not supplied:\s*(\S+)")


def _match_gh_missing_input(signal: ParsedSignal):
    return _MISSING_INPUT_RE.search(signal.message)


def _build_gh_missing_input(signal: ParsedSignal, match: re.Match) -> dict:
    input_name = match.group(1)
    step = signal.extra.get("step")
    return {
        "cause": f"The action in this step requires an input named '{input_name}', but it wasn't provided.",
        "explanation": (
            "Actions declare required inputs in their action.yml. If a workflow calls the action "
            f"without setting '{input_name}' (directly, or via a secret/variable that turned out to "
            "be empty), the runner fails the step before the action's own code even runs."
        ),
        "fix": (
            f"Add 'with: {input_name}: ...' to this step in the workflow file"
            + (f" (step: {step})" if step else "")
            + f", making sure any secret/variable it references is actually set for this repo/environment."
        ),
        "commands": [],
    }


def _match_gh_resource_not_accessible(signal: ParsedSignal):
    return "Resource not accessible by integration" in signal.message


def _build_gh_resource_not_accessible(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The GITHUB_TOKEN used by this workflow doesn't have permission to make this API call.",
        "explanation": (
            "Since GitHub's 2023 permission defaults, GITHUB_TOKEN is read-only unless the workflow "
            "explicitly grants more. Actions that comment on PRs, push commits, create releases, or "
            "otherwise write via the API fail with this error when the token's scope doesn't cover it."
        ),
        "fix": (
            "Add a 'permissions:' block to the job (or workflow) granting the specific scope needed "
            "(e.g. 'contents: write', 'pull-requests: write'), rather than broadly re-enabling "
            "write-all."
        ),
        "commands": [],
    }


_BAD_ACTION_VERSION_RE = re.compile(r"Unable to resolve action `([^`]+)`")


def _match_gh_bad_action_version(signal: ParsedSignal):
    return _BAD_ACTION_VERSION_RE.search(signal.message)


def _build_gh_bad_action_version(signal: ParsedSignal, match: re.Match) -> dict:
    ref = match.group(1)
    return {
        "cause": f"The workflow references an action ('{ref}') at a version/tag that doesn't exist.",
        "explanation": (
            "This happens after a repo renames or deletes a tag/release the workflow pins to, or from "
            "a typo in the version -- GitHub can't resolve the ref at checkout time, before the "
            "action's own code ever runs."
        ),
        "fix": f"Check {ref.split('@')[0] if '@' in ref else ref}'s available tags/releases and pin to one that actually exists.",
        "commands": [],
    }


def _match_gh_job_timeout(signal: ParsedSignal):
    return "has exceeded the maximum execution time" in signal.message


def _build_gh_job_timeout(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The job ran longer than its allowed execution time and was killed by the runner.",
        "explanation": (
            "Every job has a timeout (default 360 minutes, or whatever 'timeout-minutes' is set to). "
            "This usually means a step is hanging -- waiting on input, a deadlocked test, an "
            "unresponsive network call -- rather than the workflow being legitimately slow."
        ),
        "fix": (
            "Find which step was actually running when it was killed and fix why it hangs; only raise "
            "'timeout-minutes' once you're confident the job is meant to take that long."
        ),
        "commands": [],
    }


def _match_gh_push_denied(signal: ParsedSignal):
    # The actual "remote: Permission to ... denied" line comes from git
    # itself, printed *before* the runner's generic "##[error]Process
    # completed..." line -- so it's in the step's context, not the message.
    text = f"{signal.message}\n{signal.context}"
    return re.search(r"Permission to .* denied to", text) or "denied to github-actions" in text


def _build_gh_push_denied(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The workflow tried to push/write to the repository with a token that isn't allowed to.",
        "explanation": (
            "The default GITHUB_TOKEN is scoped to the triggering repo and, since 2023, defaults to "
            "read-only. A step running 'git push' (or an action that pushes on your behalf) fails "
            "with this permission error unless the token's write scope was explicitly granted."
        ),
        "fix": (
            "Grant 'contents: write' under 'permissions:' for this job, or use a PAT/deploy key with "
            "push access if pushing to a different repository."
        ),
        "commands": [],
    }


GITHUB_ACTIONS_PATTERNS = [
    Pattern("gh-missing-input", "github_actions", "Required action input not supplied",
            _match_gh_missing_input, _build_gh_missing_input),
    Pattern("gh-resource-not-accessible", "github_actions", "GITHUB_TOKEN lacks required permission",
            _match_gh_resource_not_accessible, _build_gh_resource_not_accessible),
    Pattern("gh-bad-action-version", "github_actions", "Referenced action version/tag doesn't exist",
            _match_gh_bad_action_version, _build_gh_bad_action_version),
    Pattern("gh-job-timeout", "github_actions", "Job exceeded its maximum execution time",
            _match_gh_job_timeout, _build_gh_job_timeout),
    Pattern("gh-push-denied", "github_actions", "git push denied due to token permissions",
            _match_gh_push_denied, _build_gh_push_denied),
]


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------

_TS_CANNOT_FIND_MODULE_RE = re.compile(r"Cannot find module '([^']+)'")


def _match_ts_cannot_find_module(signal: ParsedSignal):
    return signal.error_type == "TS2307" and _TS_CANNOT_FIND_MODULE_RE.search(signal.message)


def _build_ts_cannot_find_module(signal: ParsedSignal, match: re.Match) -> dict:
    module = match.group(1)
    is_relative = module.startswith(".")
    return {
        "cause": f"TypeScript can't find '{module}' or type declarations for it.",
        "explanation": (
            "For a relative import, the file doesn't exist at that path. For a package import, "
            "either the package isn't installed, or it has no bundled types and no matching "
            "'@types/...' package is installed either."
        ),
        "fix": (
            "Check the path is correct and the file exists."
            if is_relative
            else f"Install the package, and if it has no bundled types, install '@types/{module}' as well."
        ),
        "commands": (
            []
            if is_relative
            else [f"npm install {module}", f"npm install --save-dev @types/{module}"]
        ),
    }


_TS_CANNOT_FIND_NAME_RE = re.compile(r"Cannot find name '([^']+)'")


def _match_ts_cannot_find_name(signal: ParsedSignal):
    return signal.error_type == "TS2304" and _TS_CANNOT_FIND_NAME_RE.search(signal.message)


def _build_ts_cannot_find_name(signal: ParsedSignal, match: re.Match) -> dict:
    name = match.group(1)
    return {
        "cause": f"'{name}' is used but never declared, imported, or brought into scope by an @types package.",
        "explanation": (
            f"TypeScript has no declaration for '{name}' anywhere it can see. This is usually a "
            "missing import, a typo in the name, or a missing global type (e.g. DOM or Node types) "
            "that needs its @types package listed in tsconfig's \"types\"/\"lib\"."
        ),
        "fix": f"Import '{name}' from wherever it's actually defined, fix the typo, or install the @types package that declares it.",
        "commands": [],
    }


_TS_PROPERTY_MISSING_RE = re.compile(r"Property '([^']+)' does not exist on type '([^']+)'")


def _match_ts_property_missing(signal: ParsedSignal):
    return signal.error_type == "TS2339" and _TS_PROPERTY_MISSING_RE.search(signal.message)


def _build_ts_property_missing(signal: ParsedSignal, match: re.Match) -> dict:
    prop, type_name = match.group(1), match.group(2)
    return {
        "cause": f"Code accesses '.{prop}' on a value TypeScript has typed as '{type_name}', which has no such property.",
        "explanation": (
            "Either the type definition is missing that property (an interface/type that's out of "
            f"date with the real shape of the data), or '{prop}' is a typo for a property that does "
            "exist, or the value's inferred type is narrower than what's actually at runtime."
        ),
        "fix": f"Add '{prop}' to the type/interface if it's genuinely supposed to be there, or fix the typo.",
        "commands": [],
    }


def _match_ts_implicit_any(signal: ParsedSignal):
    return signal.error_type == "TS7006"


_TS_IMPLICIT_ANY_PARAM_RE = re.compile(r"Parameter '([^']+)' implicitly has an 'any' type")


def _build_ts_implicit_any(signal: ParsedSignal, match) -> dict:
    m = _TS_IMPLICIT_ANY_PARAM_RE.search(signal.message)
    param = m.group(1) if m else "this parameter"
    return {
        "cause": f"'{param}' has no type annotation and TypeScript couldn't infer one, so it fell back to 'any' -- which noImplicitAny treats as an error.",
        "explanation": (
            "This is intentional strictness: an un-annotated, uninferrable parameter silently loses "
            "type checking for anything derived from it. It usually shows up on callback parameters "
            "whose type TypeScript can't infer from context."
        ),
        "fix": f"Add an explicit type annotation to '{param}' (or to the function it belongs to so TypeScript can infer it via context).",
        "commands": [],
    }


_TS_TYPE_NOT_ASSIGNABLE_RE = re.compile(r"Type '([^']+)' is not assignable to type '([^']+)'")


def _match_ts_type_not_assignable(signal: ParsedSignal):
    return signal.error_type == "TS2322" and _TS_TYPE_NOT_ASSIGNABLE_RE.search(signal.message)


def _build_ts_type_not_assignable(signal: ParsedSignal, match: re.Match) -> dict:
    src, dst = match.group(1), match.group(2)
    return {
        "cause": f"A value of type '{src}' is being assigned where type '{dst}' is required.",
        "explanation": (
            "This is TypeScript's core type check doing its job -- somewhere the actual shape of a "
            "value (from an API response, a default value, a cast, or a prop) doesn't match what the "
            "receiving variable/parameter/field declares."
        ),
        "fix": (
            f"Fix the mismatch at the source (produce a real '{dst}' instead of a '{src}'), or narrow/"
            "convert the value explicitly if the mismatch is only apparent, not real."
        ),
        "commands": [],
    }


TYPESCRIPT_PATTERNS = [
    Pattern("ts-cannot-find-module", "typescript", "TS2307: Cannot find module or its types",
            _match_ts_cannot_find_module, _build_ts_cannot_find_module),
    Pattern("ts-cannot-find-name", "typescript", "TS2304: Cannot find name",
            _match_ts_cannot_find_name, _build_ts_cannot_find_name),
    Pattern("ts-property-missing", "typescript", "TS2339: Property does not exist on type",
            _match_ts_property_missing, _build_ts_property_missing),
    Pattern("ts-implicit-any", "typescript", "TS7006: Parameter implicitly has an 'any' type",
            _match_ts_implicit_any, _build_ts_implicit_any),
    Pattern("ts-type-not-assignable", "typescript", "TS2322: Type is not assignable",
            _match_ts_type_not_assignable, _build_ts_type_not_assignable),
]


# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------

def _match_tf_state_lock(signal: ParsedSignal):
    return "Error acquiring the state lock" in signal.message


def _build_tf_state_lock(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "Another Terraform run (or a crashed one) is already holding the state lock.",
        "explanation": (
            "Terraform locks remote state before writing to it so concurrent runs can't corrupt it. "
            "This fires when another apply is genuinely in progress, or a previous run crashed/was "
            "killed without releasing the lock it held."
        ),
        "fix": (
            "Confirm no other apply is actually running, then release the stale lock using the lock "
            "ID from the error output. Don't use -lock=false as a routine workaround."
        ),
        "commands": ["terraform force-unlock <lock ID from the error output>"],
    }


def _match_tf_unsupported_argument(signal: ParsedSignal):
    return signal.message.strip() == "Unsupported argument"


_TF_ARG_DETAIL_RE = re.compile(r'An argument named "([^"]+)" is not expected here(?:\. Did you mean "([^"]+)"\?)?')


def _build_tf_unsupported_argument(signal: ParsedSignal, match) -> dict:
    m = _TF_ARG_DETAIL_RE.search(signal.context)
    arg = m.group(1) if m else None
    suggestion = m.group(2) if m and m.group(2) else None
    return {
        "cause": (
            f"'{arg}' isn't a valid argument for this resource/block."
            if arg
            else "An argument used in this block isn't valid for it."
        ),
        "explanation": (
            "This is a straightforward config typo or a mismatch against the provider schema -- "
            "usually the argument was renamed in a provider version bump, or was simply mistyped."
            + (f" Terraform itself suggests '{suggestion}'." if suggestion else "")
        ),
        "fix": (
            f"Rename '{arg}' to '{suggestion}'."
            if arg and suggestion
            else "Check the resource's documentation for the provider version you're pinned to and fix the argument name."
        ),
        "commands": [],
    }


def _match_tf_provider_credentials(signal: ParsedSignal):
    text = f"{signal.message}\n{signal.context}"
    return "no valid credential sources" in text or "NoCredentialProviders" in text


def _build_tf_provider_credentials(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "The provider (e.g. AWS/GCP/Azure) couldn't find any valid credentials in this environment.",
        "explanation": (
            "Terraform's provider block needs credentials from somewhere -- environment variables, a "
            "shared credentials file, an instance/role profile, or explicit provider config -- and "
            "none of the sources it checked had anything usable."
        ),
        "fix": "Set the provider's expected credential environment variables (or configure a credentials file/profile) before running terraform.",
        "commands": [],
    }


def _match_tf_already_exists(signal: ParsedSignal):
    return "already exists" in signal.message


def _build_tf_already_exists(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "Terraform is trying to create a resource that already exists outside of its state.",
        "explanation": (
            "This happens when a resource was created manually, by another tool, or by a previous "
            "apply whose state was lost/not committed -- Terraform doesn't know about it, so it tries "
            "to create it again and the provider rejects the duplicate."
        ),
        "fix": (
            "Import the existing resource into Terraform's state instead of letting it try to "
            "recreate it, or rename/remove the pre-existing resource if it shouldn't exist."
        ),
        "commands": ["terraform import <resource address> <existing resource ID>"],
    }


def _match_tf_undeclared_reference(signal: ParsedSignal):
    return "Reference to undeclared resource" in signal.message or "has not been declared" in signal.message


def _build_tf_undeclared_reference(signal: ParsedSignal, match) -> dict:
    return {
        "cause": "A resource, module, or variable is referenced that doesn't exist under that name.",
        "explanation": (
            "Usually a typo in the reference, a resource that was renamed or removed elsewhere in the "
            "config without updating everything that pointed to it, or a reference to a resource "
            "inside a module without the module prefix."
        ),
        "fix": "Fix the reference to match the actual resource/module/variable name declared in the config.",
        "commands": [],
    }


TERRAFORM_PATTERNS = [
    Pattern("tf-state-lock", "terraform", "State lock already held", _match_tf_state_lock, _build_tf_state_lock),
    Pattern("tf-unsupported-argument", "terraform", "Unsupported/typo'd argument", _match_tf_unsupported_argument, _build_tf_unsupported_argument),
    Pattern("tf-provider-credentials", "terraform", "No valid provider credentials found", _match_tf_provider_credentials, _build_tf_provider_credentials),
    Pattern("tf-already-exists", "terraform", "Resource already exists outside state", _match_tf_already_exists, _build_tf_already_exists),
    Pattern("tf-undeclared-reference", "terraform", "Reference to an undeclared resource/module", _match_tf_undeclared_reference, _build_tf_undeclared_reference),
]


PATTERNS_BY_FORMAT: dict[str, list[Pattern]] = {
    "python": PYTHON_PATTERNS,
    "npm": NPM_PATTERNS,
    "docker": DOCKER_PATTERNS,
    "github_actions": GITHUB_ACTIONS_PATTERNS,
    "typescript": TYPESCRIPT_PATTERNS,
    "terraform": TERRAFORM_PATTERNS,
}


def match_pattern(signal: ParsedSignal) -> Optional[tuple[Pattern, dict]]:
    """Return (pattern, built_result) for the first confident match, or None."""
    for pattern in PATTERNS_BY_FORMAT.get(signal.format, []):
        match = pattern.matcher(signal)
        if match:
            return pattern, pattern.build(signal, match)
    return None
