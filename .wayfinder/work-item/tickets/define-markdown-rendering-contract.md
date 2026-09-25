---
id: WI-004
title: Define the markdown rendering and frontmatter contract for show/--save
status: closed
labels:
  - wayfinder:grilling
parent: WI-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

What exact markdown structure does `show` produce: which ADO fields map to which sections (Description, Repro Steps, Acceptance Criteria, etc., varying by work item type), how is the `## Findings` section parsed out of the marker comment and rendered, and what are the exact YAML frontmatter keys/format written when `--save` targets `work-items/<id>-<slug>.md` (including slug derivation from title)?
