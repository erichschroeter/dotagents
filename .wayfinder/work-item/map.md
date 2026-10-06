---
id: WI-001
title: Build an agent skill that retrieves and refines Azure DevOps work items
status: open
labels:
  - wayfinder:map
assignee:
---

## Destination

A working `work-item` agent skill: given Azure DevOps org `bradycorp1`, project `AEPP`, it lists work items (by assignee — me/other/unassigned, sprint timeframe — current/future/past, team backlog — OS/THT/Test Automation/etc.) and renders any single work item as markdown (to stdout, or saved to `work-items/<id>-<slug>.md`) including prior findings; and appends dated findings sub-sections to a marker-tagged ADO comment via REST PATCH — the skill's only write path. No State/Description/Acceptance-Criteria writes; no built-in sufficiency judgment or codebase investigation — those stay with the calling agent.

## Notes

- Domain: Azure DevOps org `bradycorp1`, project `AEPP`, via `az boards`/`az devops` CLI (`azure-devops` extension, installed) + raw REST via `az devops invoke` (or `curl`+PAT) for comment PATCH — no CLI comment-update command exists.
- Auth: `ADO_PAT` env var (Work Items Read & Write scope, `vso.work_write`). Fail fast with a `SKILL.md` setup pointer if unset — no `az login`/interactive fallback.
- Findings are the skill's **only** write: appended as dated sub-sections inside one marker-tagged comment (e.g. `<!-- work-item-skill:findings -->`), found via `GET .../comments` + filter, then `PATCH .../comments/{id}` in place (never a new comment) — the PAT authenticates as the human user, not a dedicated bot identity, so a marker is the only way to distinguish the skill's comment from manual ones.
- Command surface: `list`, `show`, `comment`. No `refine`/gap-analysis/investigation logic in this skill — thin ADO plumbing only; sufficiency judgment and any codebase research or human-question dispatch is the calling agent's job (it already has skill/subagent-dispatch ability).
- `show` renders the full work item as markdown incl. `## Findings` parsed from the marker comment; `--save` writes `work-items/<id>-<slug>.md` w/ YAML frontmatter (id, type, state, assignee, sprint, url). Default (no flag): markdown to stdout only, matching Erich's `/copy`-to-notes workflow.
- Sprint filtering = ADO's own iteration timeframe concept (`current`/`future`/`past`), single sprint, via `az boards iteration project list --timeframe`.
- Team backlogs (OS, THT, Test Automation, etc.) are ADO Team names; each has a default Area Path used for WIQL filtering — the mapping mechanics are an implementation detail, not a standing decision.
- Assignee filter: default = the PAT's own identity ("me"); accepts any name/email; unassigned = ADO's unassigned filter.
- Package structure mirrors `build-aepp`: `skills/work-item/{SKILL.md, scripts/*.py, tests/}`, `uv run --script` + argparse; prefer scripts/tools over commands embedded directly in `SKILL.md`.
- Tests: mocked unit tests (no live org dependency) + a small live read-only smoke suite (list/show only, never comment writes) that auto-skips when `ADO_PAT` is unset.
- Every session should consult the `grilling` and `domain-modeling` skills.
- Notes-override: this map plans and implements the skill (execution is in scope, not just a spec) — same override as `build-aepp`.
- Local Markdown tracker convention: child identity, parent, claim, labels, and blockers are frontmatter fields. An open child with no assignee and no open `blocked_by` entries is on the frontier. Resolution comments are stored as ticket-named files under `comments/`.

## Decisions so far

- [Determine team→area-path/iteration mapping for AEPP teams](tickets/determine-team-backlog-mapping.md): Team CRUD is `az devops team` (not `az boards team`); area path via `az boards area team list` → `TeamFieldValues.defaultValue`; iterations via `az boards iteration team list [--timeframe current]` → `path`/`attributes.startDate/finishDate`, or `show-default-iteration`/`show-backlog-iteration` for the team's defaults. Returned paths are WIQL-ready as-is. Real AEPP team names remain unconfirmed (no PAT yet) — see "Provision ADO_PAT and confirm real AEPP team names live".
- [Provision ADO_PAT and confirm real AEPP team names live](tickets/provision-ado-pat-and-confirm-teams.md): PAT works; real teams confirmed: OS, Test Automation, THT (as assumed).
- [Define the list/show query contract (assignee, sprint timeframe, team backlog)](tickets/define-list-show-query-contract.md): WIQL ANDs optional assignee (`@Me`/verbatim string/`''`) + sprint (single nearest current/future/past iteration, defaults to team OS's schedule when `--team` omitted) + team backlog (`AreaPath UNDER <defaultValue>`) clauses; no required flag. `show` = two live-confirmed calls: `az boards work-item show` (fields+relations) then `az devops invoke --area wit --resource comments --api-version 7.0-preview` (note: no `.3` suffix, unlike raw REST docs). Findings-comment marker scheme settled here too: one shared, generic marker per work item, dated+attributed sub-sections per contributor (not per-author markers).
- [Define the markdown rendering and frontmatter contract for show/--save](tickets/define-markdown-rendering-contract.md): Fixed per-type body sections (Bug: Description/Repro Steps/System Info/Expected/Actual Results/Tags/Findings; PBI/Spike: Description/Acceptance Criteria/Tags/Findings; others: Description/Tags/Findings), blank-but-present when the field is empty, omitted only when the field doesn't apply to the type. HTML fields converted via `markdownify`. Frontmatter: `id`/`title`/`type` (full ADO name)/`state`/`assignee` (email)/`area`/`sprint`/`url`. `--save` filename: `<id>-<slug>.md`, slug capped ~60 chars.
- [Define the findings comment marker and PATCH contract for the comment command](tickets/define-findings-comment-contract.md): Marker corrected to plain-text `[work-item-skill:findings]` (an HTML-comment marker gets silently stripped by ADO's sanitizer — confirmed live). Sub-section header: `### <date> — <name> (agent)`. Find-by-marker via `GET .../comments`, then `PATCH` in place if found else `POST` to create. Optimistic-concurrency version check guards against two concurrent sessions clobbering each other's append.
- [Design the skill's script/package structure and CLI output contract](tickets/design-skill-package-structure.md): `skills/work-item/{SKILL.md, scripts/ado_client.py, scripts/render.py, scripts/work_item.py, tests/}`. CLI: `list [--assignee] [--sprint] [--team] [--format markdown|table]`, `show <id> [--save]`, `comment <id> [text] [--file PATH]` (+ stdin, fixed precedence positional > file > stdin). Same fail-fast/raw-stderr philosophy as `build-aepp`. Tests: mocked units + a live read-only smoke tier that auto-skips without `ADO_PAT`.

## Not yet specified

- Whether a `search` command (by keyword/tag) is worth adding once `list`/`show`/`comment` are in real use.
- Whether other work item types (Epic/Feature vs. Bug/Task/Story) need distinct rendering quirks once seen against real AEPP data.
- PAT rotation/expiry handling for long-lived use of this skill.

## Out of scope

- Writing State, Description, or Acceptance Criteria fields — the findings comment is the only write path this skill performs.
- A hardcoded per-type sufficiency rubric ("enough info to start work") — that judgment is the calling agent's job; this skill only fetches and renders raw fields.
- The skill dispatching its own codebase-research or human-question sub-agents — that orchestration stays with the calling agent, keeping this a thin ADO tool.
- A `configure-work-item` skill guiding PAT creation / `azure-devops` extension install interactively — `SKILL.md` documents the steps, but automated setup is a separate effort (mirrors `build-aepp`'s `configure-aepp` exclusion).
