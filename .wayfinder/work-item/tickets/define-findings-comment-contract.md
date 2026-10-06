---
id: WI-005
title: Define the findings comment marker and PATCH contract for the comment command
status: closed
labels:
  - wayfinder:grilling
parent: WI-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

Building on the REST findings already gathered (comments are editable via `PATCH .../comments/{commentId}`, no CLI equivalent, `az devops invoke` required), what is the exact marker string/format embedded in the findings comment, what is the exact dated-sub-section header format appended per `comment` invocation (e.g. `### 2026-09-25 — <agent/session label>`), and what is the precise `az devops invoke` (or curl+PAT) command sequence for find-comment-by-marker → construct new body → PATCH?
