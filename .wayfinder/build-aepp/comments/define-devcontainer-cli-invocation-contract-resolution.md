# Resolution: Define the devcontainer CLI invocation contract

## Decision

**Base invocation**: `devcontainer up --workspace-folder <repo-root> --config .devcontainer/<arch>/devcontainer.json`, then `devcontainer exec --workspace-folder <repo-root> --config .devcontainer/<arch>/devcontainer.json bash -lc '<command>'`. No explicit `--id-label` is needed: the CLI already keys container identity on the pair `(devcontainer.local_folder, devcontainer.config_file)`.

**Reuse**: Always call `devcontainer up` unconditionally before every build. It is already idempotent — an existing container fast-paths to `docker start` (~1s observed) rather than rebuilding. The skill does not reimplement reuse-detection itself.

**Running the build**: Wrap every in-container command in `bash -lc '<command>'` rather than direct argv, so `cd`/`&&` composition works. The container's working directory is fixed at `workspaceFolder` (e.g. `/workspaces/AEPP-git`) from the architecture's `devcontainer.json`.

**Git worktrees**: Each worktree gets its own independent container — `devcontainer.local_folder` is the worktree's absolute path, so no sharing/collision occurs across worktrees of the same repo. No special-casing needed; a worktree is just a different `--workspace-folder`.

**Prerequisite fail-fast checks** (before invoking the CLI):
- `qnx` architecture only: fail fast if `~/.qnx/license` does not exist (its `devcontainer.json` bind-mounts it unconditionally; the container fails to start without it). Other architectures have no equivalent hard-failure file check.
- All architectures: warn (do not fail) if `.devcontainer/config/.env` is missing, empty, or has an empty `QT_LICENSE`. This file is git-ignored and **not** copied by `git worktree add` — a fresh worktree starts with no `.env` at all. `initCmd.sh` self-heals a missing file by `touch`ing it into existence (empty), which silently produces a `DEFINE_QT=OFF` build rather than failing outright. Since many projects don't need Qt, this must warn, not block.

**Error reporting**: On `devcontainer up`/`exec` failure, surface the CLI's own stderr verbatim (it already includes fairly specific causes, e.g. "authorization denied by plugin"). The one exception is the QNX-license pre-check (above), which produces its own clear message pointing at `.devcontainer/README.md` before ever invoking the CLI, since that failure would otherwise surface deep inside a Docker mount error.

## Validation

Ran real, non-destructive commands against the actual `/opt/BradyRD/AEPP-git` checkout and its devcontainers:
- `devcontainer up --workspace-folder . --config .devcontainer/linuxaepp/devcontainer.json` reused an already-built container via `docker start` in ~1s.
- `devcontainer exec --workspace-folder . --config .devcontainer/linuxaepp/devcontainer.json bash -lc 'cmake --preset dev -DPROJECT_LIST=CpuSpeedTest'` configured successfully end-to-end, confirming `CMakeUserPresets.json`'s `dev` preset (regenerated on every container start by the `cmakepreset` feature) is usable directly.
- Inspected real container labels (`docker ps -a --format '{{.Labels}}'`) confirming `devcontainer.config_file`/`devcontainer.local_folder` uniquely identify containers per architecture *and* per worktree — `freertos_m33`, `linuxaarch64`, and `linuxaepp` containers coexist for the same repo, and `bug-448124-large-tls-crash` (a real worktree) has its own separate container.
- Confirmed `~/.qnx/license` is absent on this host (a real fail-fast case for `qnx` builds) and that `.devcontainer/config/.env` is listed in `.gitignore`, verifying it is not repo-tracked and therefore not copied into new worktrees.

## Consequences

BAE-005 (skill packaging) wraps this contract: `devcontainer up` unconditionally, prerequisite checks (QNX license fail-fast, `.env`/`QT_LICENSE` warn), then `devcontainer exec ... bash -lc '<cmake command from BAE-004>'`, surfacing CLI stderr verbatim on failure.
