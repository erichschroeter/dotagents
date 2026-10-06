## Resolution

**Package structure** (mirrors `build-aepp`'s split, adapted for three distinct contracts already settled):
```
skills/work-item/
├── SKILL.md
├── scripts/
│   ├── ado_client.py   # all az/az devops invoke subprocess calls (auth check, WIQL query, work-item show, comments GET/POST/PATCH)
│   ├── render.py        # markdown + YAML-frontmatter rendering for `show`, table/markdown rendering for `list`
│   └── work_item.py     # argparse CLI entry point, subcommand dispatch
└── tests/
```
Split (not single-file like `build-aepp`) because rendering and ADO I/O are independently testable and map to genuinely separate, already-resolved contracts (query contract, rendering contract, comment contract) rather than one linear build pipeline.

**CLI**:
- `list [--assignee me|<name-or-email>|none] [--sprint current|future|past] [--team NAME] [--format markdown|table]` — filters AND together per the query contract; `--format` default `markdown`; `table` is a plain columnar rendering (id/title/type/state/assignee) the skill builds itself from the same WIQL result — no passthrough to `az`'s own `-o table` (that's just generic JSON→table formatting with no special reusable shape for a custom WIQL query; every `az` command gets it for free, it isn't a feature specific to `az boards query`).
- `show <id> [--save]` — markdown to stdout by default; `--save` writes `work-items/<id>-<slug>.md`.
- `comment <id> [text] [--file PATH]` (+ stdin as final fallback) — fixed precedence when multiple are given: positional arg > `--file` > stdin. Chosen over a required-single-mode error because an agent scripting this benefits from predictable precedence over a hard failure.

**Error/exit contract**: same philosophy as `build-aepp` — raw `az`/REST stderr always shown unhidden on failure, nonzero exit code, and a clear "which step failed" prefix (e.g. `ADO_PAT not set`, `az devops invoke failed: <stderr>`, `no marker comment found and creation failed`).

**Testing** (per the map's Notes, decided at charting time, reaffirmed here): mocked unit tests for `ado_client.py`/`render.py`/`work_item.py` (subprocess mocking, no live-org dependency) plus a small separate live read-only smoke suite (`list`/`show` only, never `comment`'s write path) that auto-skips when `ADO_PAT` is unset — mirrors `build-aepp`'s test layout but adds the live smoke tier this effort's Notes called for.
