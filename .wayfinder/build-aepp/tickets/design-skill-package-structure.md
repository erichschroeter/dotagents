---
id: BAE-005
title: Design the skill's script/package structure and output contract
status: closed
labels:
  - wayfinder:grilling
parent: BAE-001
assignee: Erich Schroeter
blocked_by: [BAE-003, BAE-004]
---

## Question

Given the resolved devcontainer-invocation contract and CMake-invocation contract, how is `build-aepp` packaged: what scripts/tools does it call (language, directory layout under the skill folder), what arguments does it expose (project name, optional architecture override, optional test flag), and what does it report on success/failure (binary output path, log excerpts on failure, ctest summary when requested)? How does it surface the BAE-002 project-mapping extraction and the ambiguous-architecture default (`linux-aarch64`) to the caller when it applies?
