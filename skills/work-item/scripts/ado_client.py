#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
ado_client: thin wrapper around `az boards`/`az devops invoke` for the
work-item skill (WI-003, WI-005). All subprocess calls to Azure DevOps live
here; render.py and work_item.py never shell out directly.

Auth: reads ADO_PAT from the environment and forwards it to `az` as
AZURE_DEVOPS_EXT_PAT, which authenticates non-interactively -- no
`az devops login`/interactive session state needed (confirmed live: WI-003).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

ORGANIZATION_URL = "https://dev.azure.com/bradycorp1"
PROJECT = "AEPP"
# Team whose sprint schedule anchors --sprint when --team is omitted (WI-003).
DEFAULT_TEAM = "OS"
# Plain-text marker (not an HTML comment -- those are silently stripped by
# ADO's comment sanitizer, confirmed live: WI-005).
FINDINGS_MARKER = "[work-item-skill:findings]"


class AdoError(Exception):
    """Raised for any failure talking to Azure DevOps (auth, az/REST errors,
    or a filter that can't be resolved)."""


class ConcurrentUpdateError(AdoError):
    """Raised when the findings comment changed between our read and our
    write (WI-005's optimistic-concurrency guard)."""


def require_pat() -> str:
    pat = os.environ.get("ADO_PAT")
    if not pat:
        raise AdoError(
            "ADO_PAT is not set. Create a PAT with Work Items (Read & Write) "
            "scope at https://bradycorp1.visualstudio.com/_usersSettings/tokens "
            "and `export ADO_PAT=<token>`. See SKILL.md for details."
        )
    return pat


def _env(pat: str) -> dict[str, str]:
    env = os.environ.copy()
    env["AZURE_DEVOPS_EXT_PAT"] = pat
    return env


def _run_az(args: list[str], pat: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["az", *args, "--organization", ORGANIZATION_URL, "-o", "json"]
    print(f"+ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(
        cmd, text=True, input=input_text, capture_output=True, env=_env(pat)
    )


def _parse_or_raise(result: subprocess.CompletedProcess, step: str) -> Any:
    if result.returncode != 0:
        raise AdoError(f"{step} failed:\n{result.stderr}")
    return json.loads(result.stdout)


def area_team_default(team: str, pat: str) -> dict:
    """TeamFieldValues shape: {'defaultValue': 'AEPP\\OS', 'values': [...]}."""
    result = _run_az(
        ["boards", "area", "team", "list", "--team", team, "--project", PROJECT],
        pat,
    )
    return _parse_or_raise(result, f"resolving area path for team '{team}'")


def iteration_team_list(team: str, pat: str, timeframe: str | None = None) -> list[dict]:
    args = ["boards", "iteration", "team", "list", "--team", team, "--project", PROJECT]
    if timeframe:
        args += ["--timeframe", timeframe]
    result = _run_az(args, pat)
    return _parse_or_raise(result, f"listing iterations for team '{team}'")


def resolve_iteration_path(team: str, sprint: str, pat: str) -> str:
    """Resolve `sprint` (current/future/past) to a single nearest iteration
    path for `team` (WI-003: single iteration, symmetric across timeframes)."""
    if sprint == "current":
        rows = iteration_team_list(team, pat, timeframe="current")
        if not rows:
            raise AdoError(f"team '{team}' has no current iteration")
        return rows[0]["path"]

    rows = iteration_team_list(team, pat)
    now = datetime.now(timezone.utc)

    def parse_dt(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    if sprint == "future":
        candidates = [r for r in rows if parse_dt(r["attributes"]["startDate"]) > now]
        candidates.sort(key=lambda r: parse_dt(r["attributes"]["startDate"]))
    elif sprint == "past":
        candidates = [r for r in rows if parse_dt(r["attributes"]["finishDate"]) < now]
        candidates.sort(key=lambda r: parse_dt(r["attributes"]["finishDate"]), reverse=True)
    else:
        raise AdoError(f"unknown sprint timeframe '{sprint}' (expected current/future/past)")

    if not candidates:
        raise AdoError(f"team '{team}' has no {sprint} iteration")
    return candidates[0]["path"]


def _wiql_escape(value: str) -> str:
    return value.replace("'", "''")


def build_wiql(assignee: str | None, sprint: str | None, team: str | None, pat: str) -> str:
    """Build the WIQL WHERE clause for `list` (WI-003): assignee/sprint/team
    are independently optional and ANDed together; no filter means every
    item in the project."""
    clauses = [f"[System.TeamProject] = '{PROJECT}'"]

    if assignee is not None:
        if assignee == "me":
            clauses.append("[System.AssignedTo] = @Me")
        elif assignee == "none":
            clauses.append("[System.AssignedTo] = ''")
        else:
            clauses.append(f"[System.AssignedTo] = '{_wiql_escape(assignee)}'")

    if sprint is not None:
        anchor_team = team or DEFAULT_TEAM
        iteration_path = resolve_iteration_path(anchor_team, sprint, pat)
        clauses.append(f"[System.IterationPath] = '{_wiql_escape(iteration_path)}'")

    if team is not None:
        area_path = area_team_default(team, pat)["defaultValue"]
        clauses.append(f"[System.AreaPath] UNDER '{_wiql_escape(area_path)}'")

    select = (
        "SELECT [System.Id],[System.Title],[System.WorkItemType],"
        "[System.State],[System.AssignedTo] FROM WorkItems"
    )
    return f"{select} WHERE {' AND '.join(clauses)}"


def list_work_items(
    assignee: str | None, sprint: str | None, team: str | None, pat: str
) -> list[dict]:
    wiql = build_wiql(assignee, sprint, team, pat)
    result = _run_az(["boards", "query", "--wiql", wiql, "--project", PROJECT], pat)
    return _parse_or_raise(result, "querying work items")


def show_work_item(work_item_id: str, pat: str) -> dict:
    result = _run_az(["boards", "work-item", "show", "--id", work_item_id], pat)
    return _parse_or_raise(result, f"fetching work item {work_item_id}")


def _run_invoke(
    route_params: dict[str, str], http_method: str, pat: str, body: dict | None = None
) -> subprocess.CompletedProcess:
    args = [
        "devops", "invoke",
        "--area", "wit",
        "--resource", "comments",
        "--route-parameters", *[f"{k}={v}" for k, v in route_params.items()],
        "--api-version", "7.0-preview",  # no ".3" suffix -- az's parser rejects it (WI-003)
        "--http-method", http_method,
    ]
    # `az devops invoke --in-file` takes a real file path, not stdin (confirmed
    # via `az devops invoke -h`), so a request body is written to a temp file.
    if body is None:
        return _run_az(args, pat)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        body_path = f.name
    try:
        args += ["--in-file", body_path]
        return _run_az(args, pat)
    finally:
        os.unlink(body_path)


def get_comments(work_item_id: str, pat: str) -> list[dict]:
    result = _run_invoke(
        {"project": PROJECT, "workItemId": work_item_id}, "GET", pat
    )
    data = _parse_or_raise(result, f"fetching comments for work item {work_item_id}")
    return data.get("comments", [])


def find_findings_comment(comments: list[dict]) -> dict | None:
    for c in comments:
        if c.get("text", "").startswith(FINDINGS_MARKER):
            return c
    return None


def format_findings_section(author: str, text: str, when: datetime | None = None) -> str:
    date_str = (when or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return f"### {date_str} — {author} (agent)\n\n{text}"


def create_findings_comment(work_item_id: str, section: str, pat: str) -> dict:
    body = {"text": f"{FINDINGS_MARKER}\n\n{section}"}
    result = _run_invoke(
        {"project": PROJECT, "workItemId": work_item_id}, "POST", pat, body=body
    )
    return _parse_or_raise(result, f"creating findings comment on work item {work_item_id}")


def patch_findings_comment(work_item_id: str, comment_id: str, new_text: str, pat: str) -> dict:
    body = {"text": new_text}
    result = _run_invoke(
        {"project": PROJECT, "workItemId": work_item_id, "commentId": str(comment_id)},
        "PATCH",
        pat,
        body=body,
    )
    return _parse_or_raise(result, f"updating findings comment on work item {work_item_id}")


def append_findings_comment(work_item_id: str, author: str, text: str, pat: str) -> dict:
    """Find-or-create the marker comment, then append a dated sub-section
    (WI-005). Guards against a concurrent session's append being clobbered:
    re-fetches the comment immediately before writing and fails fast if its
    version has moved since the first read."""
    section = format_findings_section(author, text)

    comments = get_comments(work_item_id, pat)
    existing = find_findings_comment(comments)
    if existing is None:
        return create_findings_comment(work_item_id, section, pat)

    fresh_comments = get_comments(work_item_id, pat)
    fresh = find_findings_comment(fresh_comments)
    if fresh is None or fresh.get("version") != existing.get("version"):
        raise ConcurrentUpdateError(
            "the findings comment changed concurrently (another session updated it); retry"
        )

    new_text = f"{fresh['text']}\n\n{section}"
    return patch_findings_comment(work_item_id, fresh["id"], new_text, pat)
