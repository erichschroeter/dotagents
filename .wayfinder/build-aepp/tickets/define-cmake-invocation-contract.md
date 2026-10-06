---
id: BAE-004
title: Define the per-project CMake invocation contract
status: closed
labels:
  - wayfinder:grilling
parent: BAE-001
assignee: Erich Schroeter
blocked_by: [BAE-002]
---

## Question

Given the resolved architecture and the project's CMake preset name (`linux`, `linux-aarch64`, `freertos_m33`, `freertos_m4`, `qnx`/`qnx_linux`), how does the skill scope a build to a single requested project rather than the whole default `PROJECT_LIST` (e.g. `-DPROJECT_LIST=<Project>`), and what CMake target does it actually build given target names can differ from the project directory/list name (e.g. `PropertyServer`'s buildable target is `PropertyServerBase`)? What default build configuration (Release/Debug/Developer/etc.) is used when the caller doesn't specify one, and does that default vary per architecture (e.g. `freertos_m33`/`freertos_m4` build with `BUILD_TESTING=OFF`, so the opt-in `ctest` flag from the map's Notes must no-op or error clearly there)?
