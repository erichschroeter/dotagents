# Resolution: Determine how to extract project→architecture(s) and project→source-path mapping

## Decision

Extract by `include()`-ing the repo's own CMake files in a throwaway `cmake -P` harness, rather than regex-parsing them as text:

- `cmake/ProjectIndex.cmake` is pure `set(<Project>_LOC ...)` data (one entry, `HttpLib_LOC`, is gated on `PLATFORM_DEFINITION MATCHES "QNX"`), so it's safe to `include()` directly.
- `cmake/BuildList.cmake` is safe only up to its `foreach(PROJECT ${PROJECT_LIST})` line — everything after that calls `FetchContent_MakeAvailable`, which would `add_subdirectory` every project and need a full toolchain. Copy the file verbatim up to (not including) that line into a temp file and `include()` the copy, so the actual list-building logic (`*_PROJECTS` variables, `DEFINE_QT` appends) runs unmodified — byte-for-byte identical to a real configure.
- Dump every `*_PROJECTS` list and every `<Project>_LOC` variable as delimited `message()` lines (CMake `-P` writes `message()` to stderr) and parse them back in Python.

This avoids regex fragility against the conditional-append logic (`DEFINE_QT`, platform selection) while never running a full configure.

## Validation

Verified against the real `/opt/BradyRD/AEPP-git` checkout:
- `IppServer` (multi-platform) resolves to all four lists it belongs to: `QNX_PROJECTS`, `LINUX_PROJECTS`, `AARCH64_PROJECTS`, `VS2022_PROJECTS`.
- `PropertyServer` resolves its nested `_LOC` (`Projects/PropertyServer/PropertyServer`, one level below the top-level project directory) and its single list membership (`LINUX_PROJECTS`).
- `Artemis`/`Sparta` resolve correctly to `M4_PROJECTS`/`M33_PROJECTS`.
- `PahoMqttCpp` resolves a `_LOC` outside `Projects/` entirely (`lib/paho-mqtt-cpp`), with no platform-list membership (a library dependency, not a top-level buildable project).
- The one `PLATFORM_DEFINITION`-gated `_LOC` (`HttpLib_LOC`) resolves differently depending on the `platform_definition` argument passed to `resolve_all()`/`resolve()`, matching `ProjectIndex.cmake`'s conditional.
- With `DEFINE_QT=ON`, resolved list sizes match the raw `set(...)` blocks plus their `DEFINE_QT`-gated appends exactly (e.g. `LINUX_PROJECTS` 36 base + 4 Qt-only = 40).

Full test suite: `python3 -m unittest test_aepp_project_map` — 7/7 pass.

## Asset

[`aepp_project_map.py`](../assets/aepp_project_map.py) (extractor) and [`test_aepp_project_map.py`](../assets/test_aepp_project_map.py) (tests), both under `.wayfinder/build-aepp/assets/`. This is prototype code proving the mechanism; BAE-005 (skill packaging) decides where/how it lands in the final `build-aepp` skill.

## Consequences

- Future tickets (BAE-004 CMake invocation contract, BAE-005 packaging) can rely on `resolve_all(repo_root, platform_definition)` / `resolve(repo_root, project, platform_definition)` returning `{"loc": <absolute path>, "lists": [<*_PROJECTS names>]}` for any project known to `ProjectIndex.cmake`.
- Multi-platform projects (e.g. `IppServer`) return every matching list; resolving *which one* to build for a given call is BAE-004/BAE-005's concern (per the map's "default to `linux-aarch64` when ambiguous" decision).
- `platform_definition` only matters for the rare `PLATFORM_DEFINITION`-gated `_LOC` entries (currently just `HttpLib_LOC`); pass the target architecture's value when resolving a project meant for that architecture.
