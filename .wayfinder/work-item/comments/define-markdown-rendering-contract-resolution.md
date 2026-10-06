## Resolution

**Frontmatter keys**: `id`, `title`, `type` (full ADO WorkItemType name verbatim, e.g. "Product Backlog Item", "Bug", "Spike" — ADO's API exposes no abbreviated codes; inventing one risks collisions, e.g. "Support Request"/"Sprint Goals" both → "SR"/"SG"), `state`, `assignee` (`uniqueName`/email, or omitted if unassigned — matches what `list`'s assignee filter accepts as input), `area` (`System.AreaPath`), `sprint` (`System.IterationPath`), `url` (human-viewable `https://bradycorp1.visualstudio.com/.../_workitems/edit/<id>`, not the REST API `url`).

**Body sections — fixed per type, no generic field dump**:
- **Bug**: `## Description`, `## Repro Steps`, `## System Info`, `## Expected Results`, `## Actual Results`, `## Tags`, `## Findings`
- **Product Backlog Item / Spike**: `## Description`, `## Acceptance Criteria`, `## Tags`, `## Findings`
- **Every other type** (Task, Feature, Epic, Investigation, Support Request, etc.): `## Description`, `## Tags`, `## Findings`

No `## Summary` section — frontmatter already carries id/title/type/state/assignee/area/sprint; repeating them in the body risked drift.

Field references confirmed live against real AEPP data:
- `System.Description`, `Microsoft.VSTS.TCM.ReproSteps`, `Microsoft.VSTS.TCM.SystemInfo`, `Custom.ExpectedResults`, `Custom.ActualResults` (Bug)
- `System.Description`, `Microsoft.VSTS.Common.AcceptanceCriteria` (PBI/Spike)
- `System.Tags` (semicolon-joined string, all types)

**Empty-section handling**: a section stays in the output with just its heading and no body text — no `_(none)_` placeholder — when the field exists on the type but is empty for that item. A section is omitted entirely only when the field doesn't apply to that type at all (e.g. no Repro Steps heading on a Task).

**HTML fields**: `Description`/`ReproSteps`/`AcceptanceCriteria`/`SystemInfo`/`ExpectedResults`/`ActualResults` arrive as raw HTML (confirmed live, e.g. `<div>Downgrades seem to have intermittent issues </div>`) — converted via `markdownify` before rendering, never embedded as raw HTML.

**People fields**: `AssignedTo` (and any other identity field) is a nested REST object (`displayName`, `uniqueName`, etc.) — body renders `displayName` only (e.g. "Tan Liu"); frontmatter's `assignee` key uses `uniqueName` (email) instead, since that's the machine-usable form `list`'s assignee filter takes as input.

**`## Findings` section**: rendered from the marker comment (feeds from "Define the findings comment marker and PATCH contract", not yet resolved) — present (possibly empty) for every type.

**`--save` filename**: `work-items/<id>-<slug>.md`, slug = lowercased title, non-alphanumerics collapsed to `-`, trimmed, capped at ~60 chars truncated at a word boundary (not mid-word).

**Live verification**: confirmed via `az devops invoke --area wit --resource fields --api-version 7.0` (all-fields catalog) and `az boards work-item show` against real Bug/Spike/PBI items in AEPP — exact field reference names above are real, not guessed. Also confirmed ADO's `workitemtypes` metadata has no abbreviated-code field, settling Q4a (use full type names).
