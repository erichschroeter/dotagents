---
id: WI-002
title: Determine team→area-path/iteration mapping for AEPP teams
status: closed
labels:
  - wayfinder:research
parent: WI-001
assignee:
blocked_by: []
---

## Question

For the AEPP project's teams (OS, THT, Test Automation, and any others), what is the concrete `az boards` / REST mechanism to resolve a team name to (a) its default Area Path (for WIQL backlog filtering) and (b) its current/future/past iteration path (for sprint-timeframe filtering)? Confirm exact commands (e.g. `az boards team list`, `az boards team show`, `az boards area team list-defaults`/equivalent REST `teamsettings` endpoints), what output shape they return, and whether team names need any normalization (spaces, `AEPP Team\OS` style paths) to use directly in filters. List the actual team names found in the AEPP project.
