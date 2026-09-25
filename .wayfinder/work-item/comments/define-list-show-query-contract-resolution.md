## Resolution

**Sprint timeframe**: `current`/`future`/`past` each resolve to a single nearest iteration (not a range), symmetric with each other.

**Assignee clause**: direct WIQL mapping, no fuzzy resolution —
- `me` → `[System.AssignedTo] = @Me`
- `<name-or-email>` → `[System.AssignedTo] = '<value>'` (verbatim; zero rows if it doesn't match — not the skill's job to resolve identities)
- unassigned → `[System.AssignedTo] = ''`

**Team backlog clause**: `[System.AreaPath] UNDER '<team's defaultValue>'` (not `=`) — a team's whole backlog including sub-areas, e.g. confirmed live for OS: `defaultValue` = `AEPP\OS`, with a second real value `AEPP\Radius\OS` also in `values[]`. This shop's convention keeps Area Path and Iteration Path aligned (`AEPP\OS` area ↔ `AEPP\OS\Sprint 59` iteration), confirmed live via `az boards iteration team list --team OS --timeframe current` → `path: AEPP\OS\Sprint 59`.

**Filter combination**: assignee/sprint/team are independently optional, ANDed into one WIQL `WHERE` clause. No required flag — bare `list` returns everything unscoped.

**Sprint without `--team`**: no anchor-team flag required; when `--sprint` is given without `--team`, defaults to team **OS** (Erich's own team) rather than erroring or requiring `--team`.

**`show`'s fetch — confirmed as two separate live calls**:
1. `az boards work-item show --id <id> --output json` → top-level keys `fields`, `id`, `relations`, `rev`, `url`, `multilineFieldsFormat`. `fields` includes `System.CommentCount` as a hint but not comment bodies.
2. `az devops invoke --area wit --resource comments --route-parameters project=AEPP workItemId=<id> --api-version 7.0-preview --http-method GET -o json` → `{comments, continuation_token, count, totalCount}`. **Note**: `az devops invoke`'s `--api-version` uses `7.0-preview` (no `.3` suffix) even though the raw REST docs show `7.0-preview.3` — the CLI wrapper's version-string parsing differs from the REST URL query param and errors (`could not convert string to float`) if given the dotted preview-revision suffix.

**Live verification**: authenticated via provided PAT against `bradycorp1`/`AEPP`. Confirmed real team names (**OS**, **Test Automation**, **THT** all exist, matching the assumed names). Ran the constructed WIQL live against OS's current sprint (`Sprint 59`) and got real results (12 items: Bugs, Tasks, Spikes, PBIs). Ran both `show` calls live against work item 458732 — fields call succeeded with real data, comments call succeeded (returned `count: 0`, no comments on that item, but the call/shape is confirmed). Logged out and PAT not persisted anywhere in this repo.

**Findings-comment marker scheme** (settled while zooming into this ticket, feeds directly into "Define the findings comment marker and PATCH contract"): **shared** comment per work item — one marker (`<!-- work-item-skill:findings -->`, generic, not per-author), with each session's contribution as a dated, individually-attributed sub-section (e.g. `### 2026-09-25 — Erich Schroeter`) appended within it. Rejected per-author-marker (separate comment per teammate) — a shared comment keeps one findings history per item, readable in one place.
