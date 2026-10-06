#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdownify"]
# ///
"""
render: markdown + frontmatter rendering for `show`/--save, and table
rendering for `list` (WI-004, WI-006). Pure functions -- no ADO I/O; that
lives in ado_client.py.
"""
from __future__ import annotations

import re

from markdownify import markdownify

# Fixed per-type body sections (WI-004). Each entry is (heading, field
# reference name); Tags and Findings are appended to every type.
_BUG_SECTIONS = [
    ("Description", "System.Description"),
    ("Repro Steps", "Microsoft.VSTS.TCM.ReproSteps"),
    ("System Info", "Microsoft.VSTS.TCM.SystemInfo"),
    ("Expected Results", "Custom.ExpectedResults"),
    ("Actual Results", "Custom.ActualResults"),
]
_PBI_SPIKE_SECTIONS = [
    ("Description", "System.Description"),
    ("Acceptance Criteria", "Microsoft.VSTS.Common.AcceptanceCriteria"),
]
_DEFAULT_SECTIONS = [
    ("Description", "System.Description"),
]
_TYPE_SECTIONS = {
    "Bug": _BUG_SECTIONS,
    "Product Backlog Item": _PBI_SPIKE_SECTIONS,
    "Spike": _PBI_SPIKE_SECTIONS,
}


def _sections_for_type(work_item_type: str) -> list[tuple[str, str]]:
    return _TYPE_SECTIONS.get(work_item_type, _DEFAULT_SECTIONS)


def html_to_markdown(html: str | None) -> str:
    if not html:
        return ""
    return markdownify(html).strip()


def _person_display_name(field_value) -> str:
    if isinstance(field_value, dict):
        return field_value.get("displayName", "")
    return field_value or ""


def _person_unique_name(field_value) -> str | None:
    if isinstance(field_value, dict):
        return field_value.get("uniqueName")
    return None


def frontmatter(item: dict, url: str) -> dict:
    """Build the YAML frontmatter dict for --save (WI-004)."""
    fields = item["fields"]
    fm = {
        "id": item["id"],
        "title": fields.get("System.Title", ""),
        "type": fields.get("System.WorkItemType", ""),
        "state": fields.get("System.State", ""),
        "area": fields.get("System.AreaPath", ""),
        "sprint": fields.get("System.IterationPath", ""),
        "url": url,
    }
    assignee = _person_unique_name(fields.get("System.AssignedTo"))
    if assignee:
        fm["assignee"] = assignee
    return fm


def _yaml_scalar(value) -> str:
    """Quote a frontmatter value when needed so it parses as one YAML scalar
    (e.g. a title containing ': ' or a leading/trailing space)."""
    text = str(value)
    if text == "" or re.search(r'^[\s]|[\s]$|[:#\[\]{}"\'|>*&!%@`]', text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _frontmatter_yaml(fm: dict) -> str:
    lines = ["---"]
    for key, value in fm.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def render_findings_section(comments: list[dict], marker: str) -> str:
    for c in comments:
        if c.get("text", "").startswith(marker):
            # Drop the marker line itself; keep the dated sub-sections.
            body = c["text"][len(marker):].strip()
            return body
    return ""


def render_work_item_markdown(
    item: dict, comments: list[dict], marker: str, url: str, include_frontmatter: bool = False
) -> str:
    fields = item["fields"]
    work_item_type = fields.get("System.WorkItemType", "")
    lines: list[str] = []

    if include_frontmatter:
        lines.append(_frontmatter_yaml(frontmatter(item, url)))
        lines.append("")

    lines.append(f"# {fields.get('System.Title', '')}")
    lines.append("")

    for heading, field_ref in _sections_for_type(work_item_type):
        lines.append(f"## {heading}")
        lines.append("")
        raw = fields.get(field_ref)
        text = html_to_markdown(raw) if raw else ""
        if text:
            lines.append(text)
            lines.append("")

    lines.append("## Tags")
    lines.append("")
    tags = fields.get("System.Tags", "")
    if tags:
        lines.append(tags)
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    findings = render_findings_section(comments, marker)
    if findings:
        lines.append(findings)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def slugify(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    # Truncate at a word boundary rather than mid-word (WI-004).
    if "-" in truncated:
        truncated = truncated.rsplit("-", 1)[0]
    return truncated


def save_filename(work_item_id, title: str) -> str:
    return f"{work_item_id}-{slugify(title)}.md"


def _table_cell(value) -> str:
    """Escape a value so it can't break out of a markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_list_markdown(items: list[dict]) -> str:
    """GitHub-flavored markdown table -- pastes cleanly into notes."""
    header = "| ID | Title | Type | State | Assignee |"
    sep = "|---|---|---|---|---|"
    rows = [header, sep]
    for item in items:
        fields = item["fields"]
        rows.append(
            f"| {_table_cell(fields.get('System.Id', ''))} | {_table_cell(fields.get('System.Title', ''))} | "
            f"{_table_cell(fields.get('System.WorkItemType', ''))} | {_table_cell(fields.get('System.State', ''))} | "
            f"{_table_cell(_person_display_name(fields.get('System.AssignedTo')))} |"
        )
    return "\n".join(rows) + "\n"


def render_list_table(items: list[dict]) -> str:
    """Plain fixed-width columns, similar to `az`'s own `-o table` look."""
    columns = ["ID", "Title", "Type", "State", "Assignee"]
    rows = [
        [
            str(fields.get("System.Id", "")).replace("\n", " "),
            fields.get("System.Title", "").replace("\n", " "),
            fields.get("System.WorkItemType", "").replace("\n", " "),
            fields.get("System.State", "").replace("\n", " "),
            _person_display_name(fields.get("System.AssignedTo")).replace("\n", " "),
        ]
        for fields in (item["fields"] for item in items)
    ]
    widths = [
        max(len(columns[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(columns))
    ]
    lines = ["  ".join(columns[i].ljust(widths[i]) for i in range(len(columns)))]
    lines.append("  ".join("-" * widths[i] for i in range(len(columns))))
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(columns))))
    return "\n".join(lines) + "\n"
