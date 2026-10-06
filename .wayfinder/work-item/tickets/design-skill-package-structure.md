---
id: WI-006
title: Design the skill's script/package structure and CLI output contract
status: closed
labels:
  - wayfinder:grilling
parent: WI-001
assignee: Erich Schroeter
blocked_by: [WI-003, WI-004, WI-005]
---

## Question

Given the query contract, rendering contract, and comment contract, how is `work-item` packaged: what scripts/tools does it call (language, directory layout under the skill folder, mirroring `build-aepp`'s `scripts/`+`tests/` split), what arguments does each of `list`/`show`/`comment` expose, and what does each report on success/failure? How do the mocked unit tests and the live read-only smoke suite fit into the test layout, and how does the smoke suite auto-skip when `ADO_PAT` is unset?
