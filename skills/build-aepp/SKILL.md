---
name: build-aepp
description: Build AEPP projects inside their architecture-specific devcontainer. Use when the user asks to build, compile, or test a project from /opt/BradyRD/AEPP-git.
---

# build-aepp

Builds one or more AEPP-git projects inside the correct devcontainer for their architecture, without VS Code.

## Usage

```bash
uv run scripts/build.py <project> [<project> ...] [--arch NAME] [--config CONFIG] [--target NAME ...] [--test]
```

- `<project>`: one or more project names as they appear in `cmake/ProjectIndex.cmake` (e.g. `PropertyServer`, `CpuSpeedTest`).
- `--arch`: override the resolved/defaulted architecture (`linux`, `linux-aarch64`, `qnx`, `freertos_m33`, `freertos_m4`).
- `--config`: build configuration, default `Developer` (`Debug`, `Release`, `RelWithDebInfo`, `MinSizeRel`).
- `--target`: override the auto-resolved CMake target name; repeatable.
- `--test`: also run `ctest` after building (errors on `freertos_m33`/`freertos_m4`, which build with `BUILD_TESTING=OFF`).

## How it works

1. Resolves the project's valid architecture(s) from `cmake/BuildList.cmake`/`cmake/ProjectIndex.cmake` (via `scripts/aepp_project_map.py`, `cmake -P`, no full configure).
   - Unambiguous → used directly.
   - Ambiguous and `linux-aarch64` is a valid option → defaults to it.
   - Ambiguous and `linux-aarch64` is **not** valid → fails fast listing valid architectures; pass `--arch`.
2. Resolves the buildable CMake target by parsing the project's top-level `CMakeLists.txt` for `add_executable`/`add_library`/`CreateProjectTarget` (target names often differ from the project name, e.g. `CpuSpeedTest` → `CpuSpeedTestApp`). Fails fast (asks for `--target`) if zero or multiple candidates are found (e.g. aggregator projects like `DevicePackages`).
3. Runs `devcontainer up` (idempotent — reuses an already-running container) then `devcontainer exec ... cmake --preset dev -DPROJECT_LIST=<project> && cmake --build --preset <config> --target <target>` inside it. Always reconfigures (cheap, ~2s) so `PROJECT_LIST` is never stale.
4. On `qnx`, fails fast before invoking the CLI if `~/.qnx/license` is missing. Warns (doesn't fail) if `.devcontainer/config/.env`/`QT_LICENSE` is missing or empty — common after `git worktree add`, since `.env` is git-ignored and not copied.

## Output

- Raw `devcontainer`/`cmake`/`ctest` output is always shown, unhidden, for both humans and agents to diagnose failures.
- On success: resolved architecture (flagged `(defaulted)` when the ambiguity default applied), resolved target(s) (flagged `(auto-resolved)` when different from the project name), each built artifact path, and a `tests: passed` line when `--test` was used.
- On failure: which step failed (`devcontainer up`/`exec`, QNX-license check, configure, build, or test) and the tool's stderr; nonzero exit.

## Files

- `scripts/build.py` — entry point.
- `scripts/aepp_project_map.py` — project → architecture/source-path resolver.
- `tests/` — unit tests for both (`python3 -m unittest discover` from `tests/`).

## Out of scope

- Provisioning prerequisites (registry auth, QNX license, `.env` tokens, NuGet PAT) — this skill only fails fast when they're missing.
- Windows (VS2022/C#) and macOS builds — no devcontainer exists for them.
- The `squish` devcontainer (GUI tests, not a build).
