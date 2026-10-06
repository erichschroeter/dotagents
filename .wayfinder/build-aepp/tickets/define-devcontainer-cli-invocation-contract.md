---
id: BAE-003
title: Define the devcontainer CLI invocation contract
status: closed
labels:
  - wayfinder:grilling
parent: BAE-001
assignee: Erich Schroeter
blocked_by: []
---

## Question

For each in-scope architecture (`linuxaepp`, `linuxaarch64`, `freertos_m33`, `freertos_m4`, `qnx`), what exact `devcontainer up` / `devcontainer exec` invocation (workspace folder, `--config` path to the architecture's `devcontainer.json`, working directory, environment) does the skill run, and how does it detect an already-running container to reuse versus needing `up`? Separately, what fail-fast prerequisite checks (docker registry auth, QNX license file, `.devcontainer/config/.env` populated, NuGet PAT) does the skill perform before attempting a build, and what does the resulting error message say (what's missing, where to fix it per `.devcontainer/README.md`)?
