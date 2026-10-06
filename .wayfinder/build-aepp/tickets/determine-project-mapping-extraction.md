---
id: BAE-002
title: Determine how to extract project→architecture(s) and project→source-path mapping
status: closed
labels:
  - wayfinder:prototype
parent: BAE-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

`cmake/BuildList.cmake` defines `QNX_PROJECTS`, `LINUX_PROJECTS`, `AARCH64_PROJECTS`, `M33_PROJECTS`, `M4_PROJECTS` (project name lists), and `cmake/ProjectIndex.cmake` defines `<Project>_LOC` (source path per project) — both are CMake files, not plain data. What is the most reliable way for the skill to extract, for any given project name, (a) which of these lists it belongs to and (b) its `_LOC` source path, without requiring a full CMake configure of every architecture? Build a small prototype extractor (e.g. a throwaway `cmake -P` script, or targeted regex/text parsing) against a sample of projects — including multi-list ones like `IppServer` and nested ones like `PropertyServer` — and confirm its output matches what a real CMake configure would resolve.
