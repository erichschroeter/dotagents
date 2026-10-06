## Resolution

Verified against the real repo (84 in-scope projects across `BuildList.cmake`'s lists, plus real `devcontainer exec` runs).

**Scoping to a single project**: `cmake --preset dev -DPROJECT_LIST=<Project>` (configure-time; `PROJECT_LIST` only feeds `FetchContent_Declare`/`MakeAvailable` calls). The skill always reruns this configure step before every build — confirmed it costs ~1.7s regardless of whether `PROJECT_LIST` changed, and skipping it risks building a stale project scope since it's a configure-time variable.

**Target-name resolution**: statically parse the project's top-level `CMakeLists.txt` for `add_executable(<Name> ...)`, `add_library(<Name> ...)`, or the repo's `CreateProjectTarget(<Name> ...)` macro (`cmake/include/GeneralUtils.cmake`).
- 56/84 projects: exact name match (target name == project/list name).
- 12/84: found via `CreateProjectTarget`.
- 6/84: target name differs from the project name entirely, e.g. `CpuSpeedTest`→`CpuSpeedTestApp`, `PC-FCTApplication`→`PC`, `PrintSpooler`→`PrintSpoolerLib`, `STM32WBBootLoader`→`STM32WBBootloader`, `Sparta_x86`→`Sparta`, `Tiny-CMS`→`TinyCms`, and `Eleven`→`Icarus` (completely unrelated name, defined in `Projects/Eleven/CM33/CMakeLists.txt`).
- 2/84 (`DevicePackages`, `QNXMfgFullUpgrade`): aggregators with no single target — they `FetchContent`/build several independently-named app targets.
- The original ticket's assumption that `PropertyServer`'s buildable target is `PropertyServerBase` is **wrong**: `PropertyServerBase` is a static library always built; on Linux/QNX (`PLATFORM_DEFINITION MATCHES "QNX|LINUX"`) the actual executable is defined in `Projects/PropertyServer/PropertyServer/Posix/CMakeLists.txt` and is named `PropertyServer` (same as the project name) — confirmed via `ninja -t targets`.

Decision: if static parsing finds exactly one target-name candidate, build it via `cmake --build --preset debug --target <resolved-name>` (never a bare `cmake --build` with no target — confirmed that pulls in 371 unrelated targets including test suites transitively, vs. 296 when scoped). If zero or multiple candidates are found, fail fast asking the caller to pass an explicit `--target <name>` rather than guessing.

**Default build configuration**: no repo-wide default exists (CI itself is inconsistent: `Debug` on Linux, `Developer` on Windows, per `azure-pipelines.yml`). Decision: default to `Developer`, overridable via a `--config` argument (superseded 2026-09-25: originally decided `Debug`, changed to `Developer` after implementation — see `design-skill-package-structure-resolution.md`).

**`ctest`/`BUILD_TESTING` interaction**: confirmed via `cmake/configurePresets.json` that `freertos_m33`/`freertos_m4` presets set `BUILD_TESTING=OFF` (no unit-test framework on embedded targets); all other in-scope architectures build with `BUILD_TESTING=ON`. Decision: if the caller opts into running tests (map's Notes) on `freertos_m33`/`freertos_m4`, fail fast with a clear "tests aren't supported on this architecture" error instead of silently no-op'ing.
