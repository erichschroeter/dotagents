## Resolution

Implemented `skills/build-aepp/`:

```
skills/build-aepp/
├── SKILL.md
├── scripts/
│   ├── build.py             # entry point (uv run --script, argparse)
│   └── aepp_project_map.py  # BAE-002's extractor, promoted verbatim
└── tests/
    ├── test_build.py             # 16 tests, pure-logic + mocked orchestration
    └── test_aepp_project_map.py  # 7 tests, promoted verbatim
```

**CLI**: `uv run scripts/build.py <project> [<project> ...] [--arch NAME] [--config CONFIG] [--target NAME ...] [--test]`. Positional `project` is repeatable (multi-project builds share one `PROJECT_LIST` configure, as confirmed via a real `cmake --build --target A --target B` invocation — CMake requires every needed project be present in `PROJECT_LIST` at configure time to produce all requested targets). `--target` is likewise repeatable, used as an override when auto-resolution is ambiguous or fails.

**Output contract**: raw `devcontainer`/`cmake`/`ctest` output is always printed unhidden (both stdout/stderr), so agents and humans can diagnose failures without needing a `--verbose` flag. On success, additionally prints: resolved architecture (flagged `(defaulted)` when BAE-002's ambiguity default applied), resolved target(s) (flagged `(auto-resolved)` when they differ from the project name), each artifact path (parsed from `cmake --build`'s `Linking ...` lines), and `tests: passed` when `--test` was used. On failure: which step failed (`devcontainer up`/`exec`, QNX-license precheck, configure, build, or test) plus the tool's stderr, and a nonzero exit code.

**BAE-002 correction** (found while investigating the map's "Not yet specified" fog item on multi-architecture default behavior): BAE-002's "default to `linux-aarch64`" rule was verified against the real `BuildList.cmake` — 21/84 projects are valid for more than one architecture, but only 5 of those 21 include `linux-aarch64` as an option at all (16, e.g. `CpuSpeedTest`, `Est`, `HttpServer`, are `LINUX`+`QNX` or similar, with no aarch64 option). Corrected: default to `linux-aarch64` only when it's a valid option for the ambiguous project; otherwise fail fast, listing the valid architectures and asking the caller to pass `--arch`.

**Code review found and fixed two real bugs** before closing:
1. **Shell injection**: the original design piped `bash -lc "cmake --preset dev -DPROJECT_LIST={project}"`-style interpolated strings through `devcontainer exec`, letting a project/target/config value containing shell metacharacters execute arbitrary commands inside the container. Fixed by confirming (via a real `devcontainer exec ... cmake --version` call) that `devcontainer exec` accepts a direct argv without any shell wrapper — removed `bash -lc` entirely; every invocation is now a plain argv list passed straight to `subprocess.run`.
2. **False-ambiguous target resolution**: `resolve_targets()` counted every `add_executable`/`add_library`/`CreateProjectTarget` call in a file, including mutually-exclusive CMake `if()`/`elseif()` branches. `PropertyServer`'s real top-level `CMakeLists.txt` textually declares `PropertyServerBase`, then (in different platform-gated branches) an executable and a shared-library both named `PropertyServer` — 3 raw candidates, wrongly reported ambiguous. Fixed by deduplicating candidates and preferring the project's own name when it survives deduplication. Verified end-to-end: `build.py PropertyServer --arch linux` now builds successfully and auto-resolves to `PropertyServer` (previously would have demanded `--target`).

All 23 tests pass (`python3 -m unittest discover` from `tests/`). Verified real end-to-end builds for `CpuSpeedTest` (mismatched target name) and `PropertyServer` (platform-conditional target, post-fix) via real `devcontainer exec`/`cmake` invocations against `/opt/BradyRD/AEPP-git`.

## Post-close corrections (real usage found 2 issues)

1. **Architecture-validity check was wrong**: `resolve_architecture()` treated `BuildList.cmake`'s `*_PROJECTS` list membership as the exhaustive set of architectures a project builds on. Wrong: those lists are only the *default* per-platform build set, used when `-DPROJECT_LIST` is unset — this skill always sets it explicitly, bypassing that mapping. Verified real bug: `PropertyServer` (`LINUX_PROJECTS` only) builds successfully on `linux-aarch64` too, since its own `CMakeLists.txt` guard (`PLATFORM_DEFINITION MATCHES "QNX|LINUX"`) also matches `LINUX_AARCH64`. Fixed: an explicit `--arch` is now always honored (left for real `cmake` to accept/reject); list membership is used only to guess a default when `--arch` is omitted.
2. **Default `--config` changed from `Debug` to `Developer`**: BAE-004 originally decided `Debug`. Changed post-close (uncommitted local edit found and confirmed as intended by the user) — `SKILL.md` and this ticket's decision text updated to match.

