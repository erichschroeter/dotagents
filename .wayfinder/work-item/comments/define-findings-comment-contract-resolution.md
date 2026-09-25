## Resolution

**Marker — corrected from the map's original assumption**: `<!-- work-item-skill:findings -->` (HTML comment) gets **silently stripped** by ADO's comment sanitizer on save — confirmed live (created a real comment on AEPP item 458732 containing it; the returned `text` had the marker line blank). A plain bracket marker, `[work-item-skill:findings]`, survives intact through both POST and PATCH round-trips — confirmed live. Adopted as visible plain text, not hidden; findings comments are expected to be seen.

**Sub-section header format**: `### <YYYY-MM-DD> — <display name> (agent)` (e.g. `### 2026-09-25 — Erich Schroeter (agent)`) — confirmed live to round-trip through PATCH unchanged. The `(agent)` suffix distinguishes an agent-run session from a manually-typed note, since ADO's `createdBy`/`modifiedBy` metadata can't: the PAT always authenticates as the human, whether the comment came from typing or from this skill.

**Find-then-update flow — confirmed live end-to-end**:
1. `GET .../comments` (per the earlier list/show contract, `az devops invoke --area wit --resource comments --api-version 7.0-preview`), filter client-side for the comment whose `text` starts with `[work-item-skill:findings]`.
2. If found: append the new dated sub-section to its `text`, then `PATCH .../comments/{commentId}` with `{"text": "<full new body>"}` (confirmed live: version incremented 1→2, same `commentId`, full text intact).
3. If not found (first run on this item): `POST .../comments` with `{"text": "[work-item-skill:findings]\n\n<dated sub-section>"}` (confirmed live) — no separate setup step needed.

**Concurrency**: read-then-PATCH is a real race between two sessions finding the same comment and both appending — the map's own Notes call out expecting concurrent sessions. Mitigated with an optimistic-concurrency check: capture the comment's `version` at GET time, and if the PATCH response's resulting version isn't exactly `+1` from what was read (or the PATCH is preceded by a fresh GET whose version differs from what was captured), fail with a clear "concurrent update detected, retry" error rather than silently clobbering. (Exact API mechanic — whether ADO's comments PATCH supports an `If-Match`/version-guard header or this must be a read-immediately-before-write re-check — is an implementation detail for the package-structure ticket, not a further decision.)

**Live verification**: created, PATCHed, and deleted two real test comments on AEPP item 458732 (`bradycorp1`/`AEPP`) to confirm marker survival, PATCH-in-place behavior, and DELETE cleanup; item returned to 0 comments afterward, no residue left in the real org.
