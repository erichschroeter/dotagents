---
id: BAE-001
title: Build an agent skill that builds AEPP projects in their devcontainer
status: closed
labels:
  - wayfinder:map
assignee:
---

## Destination

A working `build-aepp` agent skill: given a project name from `/opt/BradyRD/AEPP-git/`, it resolves the correct devcontainer/CMake-preset architecture, drives the `devcontainer` CLI and CMake autonomously, and reports build success or failure — no VS Code required.

## Notes

- Domain: `/opt/BradyRD/AEPP-git/`, a multi-architecture AEPP monorepo built via CMake presets inside per-architecture devcontainers (`.devcontainer/{linuxaepp,linuxaarch64,freertos_m33,freertos_m4,qnx}`).
- Every session should consult the `grilling` and `domain-modeling` skills.
- This map plans and implements the skill (Notes-override: execution is in scope, not just a spec).
- Ground truth for project↔architecture mapping is `cmake/BuildList.cmake` (`QNX_PROJECTS`, `LINUX_PROJECTS`, `AARCH64_PROJECTS`, `M33_PROJECTS`, `M4_PROJECTS`) and `cmake/ProjectIndex.cmake` (`<Project>_LOC` source paths); parse these dynamically rather than hard-coding a table.
- In-scope architectures: `linuxaepp` (LINUX_DESKTOP), `linuxaarch64` (LINUX_AARCH64), `freertos_m33`, `freertos_m4`, `qnx`.
- When a project is valid for more than one in-scope architecture, default to `linux-aarch64` unless the caller names a different architecture explicitly.
- Build success means compiling (`cmake --build`); running tests (`ctest --preset`) is opt-in via a flag.
- Reuse an already-`up` devcontainer across invocations rather than tearing down/rebuilding.
- Assume prerequisites (registry auth, QNX license, `.env` tokens, NuGet PAT) are already configured; fail fast with a clear pointer to `.devcontainer/README.md` if missing. Provisioning them is a separate effort, not this skill's job.
- Prefer scripts/tools invoked by the skill over commands embedded directly in `SKILL.md`.
- Local Markdown tracker convention: child identity, parent, claim, labels, and blockers are frontmatter fields. An open child with no assignee and no open `blocked_by` entries is on the frontier. Resolution comments are stored as ticket-named files under `comments/`.

## Decisions so far

- [Determine how to extract project→architecture(s) and project→source-path mapping](tickets/determine-project-mapping-extraction.md): Include the repo's own `ProjectIndex.cmake` and a copy of `BuildList.cmake` truncated before its `FetchContent` loop via `cmake -P`, then parse the dumped `*_PROJECTS`/`_LOC` variables — no full configure needed, and it's byte-identical to real CMake logic.
- [Define the devcontainer CLI invocation contract](tickets/define-devcontainer-cli-invocation-contract.md): Always `devcontainer up` (idempotent, fast-reuses) then `devcontainer exec ... bash -lc '<cmd>'`; each worktree gets its own container automatically; fail fast only on a missing QNX license, warn (don't fail) on a missing/empty `.env`/`QT_LICENSE`.
- [Define the per-project CMake invocation contract](tickets/define-cmake-invocation-contract.md): Always reconfigure with `-DPROJECT_LIST=<Project>` before building (cheap, ~1.7s). Resolve the buildable target by statically parsing the project's `CMakeLists.txt` for `add_executable`/`add_library`/`CreateProjectTarget`; if exactly one candidate, build via `cmake --build --preset debug --target <name>` (never a bare, unscoped build); if zero/multiple, fail fast asking for an explicit `--target`. Default config is `Developer` (superseded from `Debug`, see BAE-005 resolution), overridable. `ctest` requested on `freertos_m33`/`freertos_m4` fails fast (`BUILD_TESTING=OFF` there) rather than no-op'ing.
- [Design the skill's script/package structure and output contract](tickets/design-skill-package-structure.md): `skills/build-aepp/{SKILL.md, scripts/build.py, scripts/aepp_project_map.py, tests/}`; `uv run --script` + `argparse`. CLI: repeatable positional `project`, `--arch`, `--config`, repeatable `--target`, `--test`. Raw tool output always shown unhidden; success additionally reports resolved arch/target(s) (flagged when defaulted/auto-resolved) and artifact paths; failure reports which step failed + stderr. **Corrects BAE-002**: `linux-aarch64` is only a valid option for 5/21 ambiguous projects — default to it only when valid, else fail fast listing valid architectures.

## Not yet specified

(none — all fog resolved during BAE-002 through BAE-005)

## Out of scope

- A `configure-aepp` skill that guides the user through devcontainer/registry/license/token setup — a distinct, separate effort; `build-aepp` only fails fast when prerequisites are missing.
- Windows (VS2022/CSHARP projects) and macOS native builds — no devcontainer exists for them, so they don't fit "build within its devcontainer."
- The `squish` devcontainer — it runs Squish GUI tests, not a build target.
