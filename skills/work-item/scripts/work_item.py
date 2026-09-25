#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdownify"]
# ///
"""
work-item: list/show/comment on Azure DevOps work items (bradycorp1/AEPP).
See ../SKILL.md for the full contract this implements (WI-001..WI-006).

Usage:
    uv run scripts/work_item.py list [--assignee me|<name-or-email>|none]
        [--sprint current|future|past] [--team NAME] [--format markdown|table]
    uv run scripts/work_item.py show <id> [--save]
    uv run scripts/work_item.py comment <id> [text] [--file PATH] [--author NAME]
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ado_client  # noqa: E402
import render  # noqa: E402

WORK_ITEMS_DIR = Path("work-items")


def _human_url(work_item_id) -> str:
    return f"{ado_client.ORGANIZATION_URL}/{ado_client.PROJECT}/_workitems/edit/{work_item_id}"


def cmd_list(args: argparse.Namespace) -> int:
    pat = ado_client.require_pat()
    items = ado_client.list_work_items(args.assignee, args.sprint, args.team, pat)
    if args.format == "table":
        print(render.render_list_table(items), end="")
    else:
        print(render.render_list_markdown(items), end="")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    pat = ado_client.require_pat()
    item = ado_client.show_work_item(args.id, pat)
    comments = ado_client.get_comments(args.id, pat)
    url = _human_url(item["id"])
    markdown = render.render_work_item_markdown(
        item, comments, ado_client.FINDINGS_MARKER, url, include_frontmatter=args.save
    )
    if args.save:
        WORK_ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        fields = item["fields"]
        filename = render.save_filename(item["id"], fields.get("System.Title", ""))
        path = WORK_ITEMS_DIR / filename
        path.write_text(markdown)
        print(f"saved: {path}")
    else:
        print(markdown, end="")
    return 0


def _resolve_comment_text(args: argparse.Namespace) -> str:
    # Fixed precedence when more than one is given: positional > --file > stdin.
    if args.text is not None:
        return args.text
    if args.file is not None:
        return args.file.read_text()
    return sys.stdin.read()


def cmd_comment(args: argparse.Namespace) -> int:
    pat = ado_client.require_pat()
    text = _resolve_comment_text(args)
    if not text.strip():
        print("error: no findings text given (positional arg, --file, or stdin)", file=sys.stderr)
        return 1
    author = args.author or getpass.getuser()
    ado_client.append_findings_comment(args.id, author, text.strip(), pat)
    print(f"findings recorded on work item {args.id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List/show/comment on AEPP work items.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List work items")
    p_list.add_argument("--assignee", default=None, help="me | <name-or-email> | none")
    p_list.add_argument("--sprint", choices=["current", "future", "past"], default=None)
    p_list.add_argument("--team", default=None, help="Team backlog (e.g. OS, THT, Test Automation)")
    p_list.add_argument("--format", choices=["markdown", "table"], default="markdown")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Render one work item as markdown")
    p_show.add_argument("id")
    p_show.add_argument("--save", action="store_true", help="Write to work-items/<id>-<slug>.md")
    p_show.set_defaults(func=cmd_show)

    p_comment = sub.add_parser("comment", help="Append findings to the findings comment")
    p_comment.add_argument("id")
    p_comment.add_argument("text", nargs="?", default=None)
    p_comment.add_argument("--file", type=Path, default=None)
    p_comment.add_argument("--author", default=None, help="Attribution name (default: OS username)")
    p_comment.set_defaults(func=cmd_comment)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ado_client.AdoError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
