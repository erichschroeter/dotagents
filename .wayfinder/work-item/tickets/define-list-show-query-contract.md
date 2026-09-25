---
id: WI-003
title: Define the list/show query contract (assignee, sprint timeframe, team backlog)
status: closed
labels:
  - wayfinder:grilling
parent: WI-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

Given the team→area-path/iteration mapping from "Determine team→area-path/iteration mapping for AEPP teams", what exact `az boards query`/WIQL shape does `list` construct for each filter combination (assignee: me/other/unassigned; sprint: current/future/past; team backlog: optional)? What columns does it fetch, how is `--filter` composability handled when multiple filters are combined, and what does `show`'s single-item fetch (`az boards work-item show`) request to get all fields needed for markdown rendering (including linked comments)?
