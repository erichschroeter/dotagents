#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
build-aepp: build one or more AEPP-git projects inside their architecture's
devcontainer.

Usage:
    uv run scripts/build.py <project> [<project> ...] \
        [--arch NAME] [--config CONFIG] [--target NAME ...] [--test]

See ../SKILL.md for the full contract this implements (BAE-002..BAE-005).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aepp_project_map import resolve_all  # noqa: E402

REPO_ROOT_DEFAULT = Path("/opt/BradyRD/AEPP-git")

# Maps a BuildList.cmake `*_PROJECTS` list name to (architecture id,
# devcontainer.json path relative to the repo root). Windows-only lists
# (VS2022_PROJECTS, CSHARP_PROJECTS) have no devcontainer and are
# intentionally absent (BAE-001's Out-of-scope).
ARCH_TABLE = {
    "LINUX_PROJECTS": ("linux", ".devcontainer/linuxaepp/devcontainer.json"),
    "AARCH64_PROJECTS": ("linux-aarch64", ".devcontainer/linuxaarch64/devcontainer.json"),
    "QNX_PROJECTS": ("qnx", ".devcontainer/qnx/devcontainer.json"),
    "M33_PROJECTS": ("freertos_m33", ".devcontainer/freertos_m33/devcontainer.json"),
    "M4_PROJECTS": ("freertos_m4", ".devcontainer/freertos_m4/devcontainer.json"),
}
# Reverse lookup: architecture id -> devcontainer.json path.
DEVCONTAINER_CONFIG_BY_ARCH = {arch: path for arch, path in ARCH_TABLE.values()}

# Architectures whose devcontainer bind-mounts a QNX license file that must
# already exist on the host (BAE-003): fail fast with a clear message rather
# than let `devcontainer up` fail deep inside a bind-mount error.
QNX_LICENSE_PATH = Path.home() / ".qnx" / "license"

_DEFAULT_ARCH = "linux-aarch64"


class AmbiguousArchitectureError(Exception):
    """Raised when a project's valid architecture can't be determined
    without the caller specifying --arch."""


class AmbiguousTargetError(Exception):
    """Raised when a project's buildable CMake target can't be determined
    without the caller specifying --target."""


def resolve_architecture(project_lists: list[str], requested_arch: str | None) -> str:
    """Resolve which devcontainer architecture to build a project in.

    `project_lists` are the raw `*_PROJECTS` list names (from
    aepp_project_map's `resolve()`) that a project is a member of in
    cmake/BuildList.cmake.

    IMPORTANT: those `*_PROJECTS` lists are only the *default* "build
    everything" set CMake uses per platform when the caller doesn't pass
    `-DPROJECT_LIST=...` at all -- BuildList.cmake's platform->list mapping
    is inside an `if (NOT PROJECT_LIST OR ...)` guard that this skill's
    explicit `-DPROJECT_LIST=<project>` always bypasses. They are NOT an
    exhaustive registry of which architectures a project can actually build
    on (verified: `PropertyServer` is only in LINUX_PROJECTS, yet builds
    successfully on linux-aarch64 too, because its own CMakeLists.txt gates
    on `PLATFORM_DEFINITION MATCHES "QNX|LINUX"`, and that regex also
    matches "LINUX_AARCH64"). So list membership is used only as a
    *heuristic* to pick a default when the caller doesn't say --arch; an
    explicit --arch is always honored and left for the real `cmake
    --preset`/`cmake --build` invocation to accept or reject.
    """
    if requested_arch is not None:
        if requested_arch not in DEVCONTAINER_CONFIG_BY_ARCH:
            raise AmbiguousArchitectureError(
                f"'{requested_arch}' is not a known architecture; "
                f"choices: {sorted(DEVCONTAINER_CONFIG_BY_ARCH)}"
            )
        return requested_arch

    valid = {ARCH_TABLE[name][0] for name in project_lists if name in ARCH_TABLE}
    if not valid:
        raise AmbiguousArchitectureError(
            "no devcontainer architecture is available for this project "
            "(it only builds on Windows/VS2022), or its architecture can't be guessed "
            "from cmake/BuildList.cmake; pass --arch to pick one"
        )
    if len(valid) == 1:
        return next(iter(valid))
    if _DEFAULT_ARCH in valid:
        return _DEFAULT_ARCH
    raise AmbiguousArchitectureError(
        f"project defaults to multiple architectures {sorted(valid)}, none of which is "
        f"the default ('{_DEFAULT_ARCH}'); pass --arch to pick one (other architectures may "
        f"also work -- BuildList.cmake's lists aren't an exhaustive validity registry)"
    )


# Matches `add_executable(Name`, `add_library(Name`, or
# `CreateProjectTarget(Name` (the repo's own target-creation macro,
# cmake/include/GeneralUtils.cmake) at the start of a target-defining call.
_TARGET_PATTERN = re.compile(
    r"\b(?:add_executable|add_library|CreateProjectTarget)\(\s*([A-Za-z0-9_]+)"
)


def resolve_targets(cmakelists_text: str, project_name: str | None = None) -> list[str]:
    """Statically resolve the buildable target name(s) for a project from
    its top-level CMakeLists.txt text (BAE-004). Target names frequently
    differ from the project/list name (e.g. CpuSpeedTest -> CpuSpeedTestApp),
    so this returns whatever name(s) are actually defined there.

    CMake conditionals (e.g. platform-gated `if()` branches) aren't
    evaluated, so the same file can textually declare several target
    candidates that are never simultaneously active (e.g. PropertyServer's
    top-level CMakeLists.txt declares an executable AND a shared-library
    branch of the same name, gated on different platforms). Deduplicate
    candidates first; if the project name itself survives deduplication,
    prefer it (it's almost always the intended target even when other
    conditional branches are textually present).

    Raises AmbiguousTargetError if zero or more than one *distinct* name
    remains; the caller must then be given an explicit --target."""
    candidates = list(dict.fromkeys(_TARGET_PATTERN.findall(cmakelists_text)))
    if project_name is not None and project_name in candidates:
        return [project_name]
    if len(candidates) != 1:
        raise AmbiguousTargetError(
            f"could not uniquely resolve a buildable target ({len(candidates)} candidates: "
            f"{candidates}); pass --target to specify explicitly"
        )
    return candidates


# Matches ninja/cmake's "Linking <lang> <kind> <path>" build-log lines to
# recover artifact paths without additional CMake introspection.
_LINKING_PATTERN = re.compile(r"^\s*\[\d+/\d+\]\s+Linking\s+\S+\s+.+?\s+(\S+)\s*$")


def parse_artifact_paths(build_output: str) -> list[str]:
    return [m.group(1) for line in build_output.splitlines() if (m := _LINKING_PATTERN.match(line))]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess, always showing raw stdout/stderr as it happens so
    both humans and agents can diagnose failures (per BAE-005)."""
    print(f"+ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, text=True, **kwargs)


def _build_preset_name(config: str) -> str:
    # The devcontainer's `cmakepreset` feature always generates lowercase
    # build-preset names matching the CMAKE_BUILD_TYPE-style config name.
    return config.lower()


def build_project(
    project: str,
    repo_root: Path,
    requested_arch: str | None,
    config: str,
    explicit_targets: list[str] | None,
    run_tests: bool,
) -> int:
    info = resolve_all(repo_root).get(project)
    if info is None:
        print(f"error: unknown project '{project}' (not found in ProjectIndex.cmake)", file=sys.stderr)
        return 1

    try:
        arch = resolve_architecture(info["lists"], requested_arch)
    except AmbiguousArchitectureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    defaulted = requested_arch is None and arch == _DEFAULT_ARCH and len(info["lists"]) > 1

    if arch in ("freertos_m33", "freertos_m4") and run_tests:
        print(f"error: tests aren't supported on '{arch}' (BUILD_TESTING=OFF)", file=sys.stderr)
        return 1

    if arch == "qnx" and not QNX_LICENSE_PATH.exists():
        print(f"error: QNX license not found at {QNX_LICENSE_PATH}; see .devcontainer/README.md", file=sys.stderr)
        return 1

    if explicit_targets:
        targets = explicit_targets
        auto_resolved = False
    else:
        cmakelists = Path(info["loc"]) / "CMakeLists.txt"
        try:
            targets = resolve_targets(cmakelists.read_text(), project_name=project)
        except (AmbiguousTargetError, FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        auto_resolved = targets != [project]

    config_path = DEVCONTAINER_CONFIG_BY_ARCH[arch]
    workspace = str(repo_root)
    devcontainer_config = str(repo_root / config_path)

    up = _run(
        ["devcontainer", "up", "--workspace-folder", workspace, "--config", devcontainer_config],
        capture_output=True,
    )
    print(up.stdout, end="")
    print(up.stderr, end="", file=sys.stderr)
    if up.returncode != 0:
        print("error: 'devcontainer up' failed (see output above)", file=sys.stderr)
        return up.returncode

    def exec_in_container(*cmd: str) -> subprocess.CompletedProcess:
        result = _run(
            [
                "devcontainer", "exec",
                "--workspace-folder", workspace,
                "--config", devcontainer_config,
                *cmd,
            ],
            capture_output=True,
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result

    configure = exec_in_container("cmake", "--preset", "dev", f"-DPROJECT_LIST={project}")
    if configure.returncode != 0:
        print("error: cmake configure failed (see output above)", file=sys.stderr)
        return configure.returncode

    build_preset = _build_preset_name(config)
    build_args = ["cmake", "--build", "--preset", build_preset]
    for t in targets:
        build_args += ["--target", t]
    build = exec_in_container(*build_args)
    if build.returncode != 0:
        print("error: cmake build failed (see output above)", file=sys.stderr)
        return build.returncode

    artifact_paths = parse_artifact_paths(build.stdout)

    test_result = None
    if run_tests:
        test_result = exec_in_container("ctest", "--preset", build_preset)
        if test_result.returncode != 0:
            print("error: ctest failed (see output above)", file=sys.stderr)
            return test_result.returncode

    print(f"architecture: {arch}" + (" (defaulted)" if defaulted else ""))
    print(f"target(s): {', '.join(targets)}" + (" (auto-resolved)" if auto_resolved else ""))
    for path in artifact_paths:
        print(f"artifact: {path}")
    if test_result is not None:
        print("tests: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build AEPP-git projects in their devcontainer.")
    parser.add_argument("projects", nargs="+", help="Project name(s) to build (from ProjectIndex.cmake)")
    parser.add_argument("--arch", default=None, help="Override the resolved/defaulted architecture")
    parser.add_argument("--config", default="Developer", help="Build configuration (default: Developer)")
    parser.add_argument("--target", action="append", default=None, help="Override auto-resolved target name (repeatable)")
    parser.add_argument("--test", action="store_true", help="Also run ctest after building")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT_DEFAULT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    exit_code = 0
    for project in args.projects:
        rc = build_project(
            project,
            args.repo_root,
            args.arch,
            args.config,
            args.target,
            args.test,
        )
        exit_code = exit_code or rc
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
