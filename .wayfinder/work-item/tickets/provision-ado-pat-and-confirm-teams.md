---
id: WI-007
title: Provision ADO_PAT and confirm real AEPP team names live
status: closed
labels:
  - wayfinder:task
parent: WI-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

Create a PAT (Work Items Read & Write scope) for `bradycorp1`, export it as `ADO_PAT`, and run `az devops team list --organization https://dev.azure.com/bradycorp1 --project AEPP` to confirm the real team names (OS, THT, Test Automation, etc. were assumed, not verified) and their default area paths (`az boards area team list --team <name>`). Record the actual team list and area paths so `define-list-show-query-contract` and later implementation don't build against guessed names.
