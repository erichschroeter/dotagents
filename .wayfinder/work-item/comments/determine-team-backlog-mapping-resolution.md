## Resolution

**Live confirmation blocked**: `az account show` / `az devops team list` both fail — no `az login` and `ADO_PAT` is unset. The `azure-devops` extension (1.0.8) is installed and its command tree was inspected locally, but **no real team names were retrieved**; do not treat "OS", "THT", "Test Automation" as confirmed — they came from the ticket prompt, not a live query.

**Team discovery**: teams live under `az devops team`, not `az boards team` (that group doesn't exist in 1.0.8). Use:
```
az devops team list --org https://dev.azure.com/bradycorp1 --project AEPP
az devops team show --org .../bradycorp1 --project AEPP --team "<name>"
```
Returns each team's `id`, `name`, `description`, `url` (REST: `GET .../_apis/projects/{project}/teams?api-version=7.1`).

**(a) Default Area Path** — `az boards area team list` (REST `GET .../{project}/{team}/_apis/work/teamsettings/teamfieldvalues?api-version=7.1`, `TeamFieldValues` shape) returns `field.referenceName` (`System.AreaPath`), **`defaultValue`** (the team's default area, e.g. `Fabrikam-Fiber\Auto`), and `values[]` (each with `value` + `includeChildren`) for all areas the team owns. `defaultValue` is what to plug into WIQL `[System.AreaPath] = '...'` (or `UNDER` if `includeChildren`).

**(b) Iterations** — `az boards iteration team list --team <name> [--timeframe current]` (REST `GET .../{project}/{team}/_apis/work/teamsettings/iterations?api-version=7.1&$timeframe=current`, only `current` supported) returns each iteration's `id`, `name`, **`path`** (e.g. `Fabrikam-Fiber\Release 1\Sprint 2`), `attributes.startDate/finishDate`. For past/future iterations, omit `$timeframe` to list all, then filter client-side by `attributes` dates. `az boards iteration team show-default-iteration` / `show-backlog-iteration` (REST `GET .../teamsettings`, `TeamSetting` shape) expose `defaultIteration.path` and `backlogIteration.path` directly.

**Normalization**: `--team` accepts the plain team display name (spaces OK, quote it) or its GUID — no manual encoding needed for CLI. The **returned** `path`/`defaultValue` fields already use the `Project\Area\Sub` / `Project\Iteration\Sprint` backslash form required verbatim in WIQL string literals — no reformatting beyond that backslash convention.

**Recommendation**: once a PAT is available (`az devops login --organization https://dev.azure.com/bradycorp1`), re-run `az devops team list -p AEPP` first to get real team names before wiring any WIQL filters.
