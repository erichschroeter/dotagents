"""
Prototype extractor for BAE-002: given an AEPP-git checkout, resolve every
project name to its source location (`_LOC` from cmake/ProjectIndex.cmake)
and the platform-specific project lists (from cmake/BuildList.cmake) it
belongs to, without running a full CMake configure of any architecture.

Approach
--------
`ProjectIndex.cmake` is almost entirely `set(<Project>_LOC ...)` data, so
it is safe to `include()` directly. One entry (`HttpLib_LOC`) is gated on
`PLATFORM_DEFINITION MATCHES "QNX"`; pass the target platform's
`PLATFORM_DEFINITION` (e.g. "QNX", "LINUX_AARCH64") to `resolve_all()` to
resolve such entries correctly for that platform. The default ("NONE")
resolves them to their non-QNX branch.

`BuildList.cmake` is only safe up to its `foreach(PROJECT ${PROJECT_LIST})`
line: everything after that calls `FetchContent_MakeAvailable`, which would
`add_subdirectory` every project and require a full toolchain. We copy the
file verbatim up to (not including) that line, so the list-building logic
(the `*_PROJECTS` variables, `DEFINE_QT` appends, etc.) runs unmodified,
byte-for-byte identical to what a real configure would execute.

We then dump every `*_PROJECTS` list and every `<Project>_LOC` variable
from that CMake process as delimited `message()` lines (CMake's `-P` mode
writes `message()` to stderr) and parse them back in Python.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

_LIST_VAR_NAMES = [
    "QNX_PROJECTS",
    "VS2022_PROJECTS",
    "LINUX_PROJECTS",
    "AARCH64_PROJECTS",
    "CSHARP_PROJECTS",
    "M4_PROJECTS",
    "M33_PROJECTS",
]

# NOTE: _RECORD_SEP must not be one of the characters str.splitlines()
# treats as its own line boundary (\n, \r, \v, \f, \x1c-\x1e, \x85, U+2028,
# U+2029) or resolve_all()'s `output.splitlines()` will silently swallow it.
_RECORD_SEP = "AEPP_MAP_RECORD::"
_FIELD_SEP = "\x1f"  # ASCII unit separator (not a splitlines() boundary)


def _truncate_before_foreach(build_list_path: Path) -> str:
    """Return BuildList.cmake's content up to (not including) the
    FetchContent foreach loop, so including it only defines variables."""
    lines = build_list_path.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("foreach(PROJECT"):
            return "\n".join(lines[:i])
    raise RuntimeError(
        f"Could not find 'foreach(PROJECT ...)' marker in {build_list_path}; "
        "BuildList.cmake's structure may have changed."
    )


def _harness_script(repo_root: Path, truncated_build_list: Path, platform_definition: str) -> str:
    list_dumps = "\n".join(
        f'string(REPLACE ";" "{_FIELD_SEP}" _joined "${{{name}}}")\n'
        f'message("{_RECORD_SEP}LIST{_FIELD_SEP}{name}{_FIELD_SEP}${{_joined}}")'
        for name in _LIST_VAR_NAMES
    )
    # Plain (non f-string) block: needs a literal CMake indirect-variable
    # reference `${${_var}}`, which is easiest to write without juggling
    # f-string brace-escaping.
    loc_dump = (
        'get_cmake_property(_all_vars VARIABLES)\n'
        'foreach(_var ${_all_vars})\n'
        '    if(_var MATCHES "^(.+)_LOC$")\n'
        '        set(_project "${CMAKE_MATCH_1}")\n'
        '        set(_value "${${_var}}")\n'
        f'        message("{_RECORD_SEP}LOC{_FIELD_SEP}${{_project}}{_FIELD_SEP}${{_value}}")\n'
        '    endif()\n'
        'endforeach()\n'
    )
    return f"""
set(REPO_ROOTDIR "{repo_root.as_posix()}")
set(DEFINE_QT ON)
set(PLATFORM_DEFINITION "{platform_definition}")

include("{repo_root.as_posix()}/cmake/ProjectIndex.cmake")
include("{truncated_build_list.as_posix()}")

{list_dumps}

{loc_dump}
"""


def _run_harness(repo_root: Path, platform_definition: str) -> str:
    build_list = repo_root / "cmake" / "BuildList.cmake"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        truncated = tmp_path / "BuildList.truncated.cmake"
        truncated.write_text(_truncate_before_foreach(build_list))

        script = tmp_path / "harness.cmake"
        script.write_text(_harness_script(repo_root, truncated, platform_definition))

        result = subprocess.run(
            ["cmake", "-P", str(script)],
            capture_output=True,
            text=True,
            check=True,
        )
        # CMake's message() writes to stderr by default.
        return result.stderr


def resolve_all(repo_root: Path, platform_definition: str = "NONE") -> dict[str, dict]:
    """Return {project_name: {"loc": str, "lists": [str, ...]}} for every
    project known to ProjectIndex.cmake, using the platform lists defined
    in BuildList.cmake (with DEFINE_QT=ON).

    `platform_definition` (e.g. "QNX", "LINUX_AARCH64") only affects the
    small number of `_LOC` entries gated on `PLATFORM_DEFINITION` (currently
    just `HttpLib_LOC`); pass the target platform's value when resolving a
    project meant for that platform."""
    repo_root = Path(repo_root)
    output = _run_harness(repo_root, platform_definition)

    locs: dict[str, str] = {}
    lists: dict[str, list[str]] = {}

    for line in output.splitlines():
        if not line.startswith(_RECORD_SEP):
            continue
        record = line[len(_RECORD_SEP):]
        fields = record.split(_FIELD_SEP)
        kind = fields[0]
        if kind == "LOC":
            _, project, loc = fields
            if loc:
                # ProjectIndex.cmake derives its own REPO_ROOTDIR as
                # `${CMAKE_CURRENT_LIST_DIR}/..`, so raw paths legitimately
                # contain "..". Normalize for a clean, comparable path.
                locs[project] = os.path.normpath(loc)
        elif kind == "LIST":
            list_name = fields[1]
            for project in filter(None, fields[2:]):
                lists.setdefault(project, []).append(list_name)

    mapping: dict[str, dict] = {}
    for project, loc in locs.items():
        mapping[project] = {"loc": loc, "lists": sorted(lists.get(project, []))}
    return mapping


def resolve(repo_root: Path, project: str, platform_definition: str = "NONE") -> dict | None:
    return resolve_all(repo_root, platform_definition).get(project)
