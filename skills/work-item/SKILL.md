---
name: work-item
description: List, show, and comment on Azure DevOps work items in bradycorp1/AEPP. Use when the user wants to find work items assigned to someone (or unassigned), browse a sprint or team backlog, turn a work item into a local markdown note, or record findings back onto a work item.
---

# work-item

Thin CLI over `az boards`/`az devops` for the `bradycorp1.visualstudio.com/AEPP` org. It only reads work items and appends to one designated "findings" comment — it never edits Description, Acceptance Criteria, or State.

## Setup

1. Install the `az devops` extension: `az extension add --name azure-devops`.
2. Create a PAT with **Work Items (Read & Write)** scope at `https://bradycorp1.visualstudio.com/_usersSettings/tokens`.
3. `export ADO_PAT=<token>`

## Usage

```bash
uv run scripts/work_item.py list [--assignee me|<name-or-email>|none] [--sprint current|future|past] [--team NAME] [--format markdown|table]
uv run scripts/work_item.py show <id> [--save]
uv run scripts/work_item.py comment <id> [text] [--file PATH] [--author NAME]
```

- `list`: no filters = every item in the project. `--assignee me` uses the PAT owner; `--assignee none` finds unassigned items; any other value is matched verbatim (name or email). `--sprint` picks the nearest single iteration in that timeframe (current/future/past — one iteration, not a range). `--team` scopes to a team's area+iteration path (e.g. `OS`, `THT`, `Test Automation`); defaults to `OS` when `--sprint` is given without `--team`. `--format table` renders a fixed-width text table instead of a markdown table.
- `show <id>`: prints the work item as markdown to stdout. `--save` adds YAML frontmatter and writes to `work-items/<id>-<slug-of-title>.md` instead of printing.
- `comment <id> [text]`: appends a dated, attributed sub-section to the item's findings comment (creating it on first use). Text comes from the positional arg, else `--file`, else stdin (in that precedence). `--author` defaults to the OS username running the command — pass it explicitly for a nicer display name.

## How it works

- Auth: `AZURE_DEVOPS_EXT_PAT=$ADO_PAT` is set per-subprocess for every `az` call; no `az devops login` state is used or required.
- `list`/`show` build a WIQL query (`az boards query`) or fetch a single item (`az boards work-item show`); `--team`/`--sprint` resolve to area/iteration paths via `az boards area team list` / `az boards iteration team list`.
- `comment` finds the shared findings comment by its leading marker `[work-item-skill:findings]` (a plain-text marker — HTML comments are silently stripped by ADO's comment sanitizer) via `az devops invoke` on the comments REST resource, then POSTs a new comment or PATCHes the existing one, appending a `### <date> — <author> (agent)` sub-section per call. Before patching, it re-fetches the comment to check its version hasn't changed since it was read, and raises rather than overwrite if another writer got there first.
- Markdown rendering (`render.py`) maps ADO fields to fixed sections per work item type: Bug → Description, Repro Steps, System Info, Expected Results, Actual Results; Product Backlog Item/Spike → Description, Acceptance Criteria; everything else → Description only (or whatever fields the type actually returns). Empty sections are kept, left blank under the heading, so they stand out. HTML field values are converted to markdown via `markdownify`. `--save` frontmatter includes `title` and full work item type name (no abbreviations — ADO doesn't expose any).

## Output

- `list`: a markdown or plain-text table with ID, Title, Type, State, Assignee.
- `show`: markdown to stdout by default; with `--save`, the same markdown plus YAML frontmatter, written to `work-items/<id>-<slug>.md`.
- `comment`: confirmation line to stdout on success.
- Errors (missing `ADO_PAT`, failed `az` call, concurrent findings-comment write) print `error: ...` to stderr and exit nonzero.

## Files

- `scripts/ado_client.py` — all ADO I/O: WIQL/query building, iteration/area resolution, comment read/create/patch.
- `scripts/render.py` — pure markdown/frontmatter rendering, no ADO calls.
- `scripts/work_item.py` — CLI entry point wiring the two together.
- `tests/test_ado_client.py`, `tests/test_render.py`, `tests/test_work_item.py` — mocked unit tests (`uv run --with markdownify python3 -m unittest discover` from `tests/`).
- `tests/test_live_smoke.py` — read-only tests against the real org; auto-skipped unless `ADO_PAT` is set.

## Out of scope

- Editing Description, Acceptance Criteria, State, or any field other than the findings comment.
- Investigating or refining work items itself — this skill only fetches/renders/records; an agent using it does the actual refinement.
- Attaching files, work item creation, or any write outside the findings comment.
