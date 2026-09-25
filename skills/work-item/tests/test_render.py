"""
Tests for render.py's pure rendering logic (WI-004, WI-006): per-type body
sections, HTML->markdown conversion, frontmatter, slugify, and list
table/markdown rendering. No ADO I/O -- that's ado_client.py, tested
separately.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from render import (
    frontmatter,
    html_to_markdown,
    render_findings_section,
    render_list_markdown,
    render_list_table,
    render_work_item_markdown,
    save_filename,
    slugify,
)

MARKER = "[work-item-skill:findings]"


def _bug_item(**overrides) -> dict:
    fields = {
        "System.Title": "Build downgrade from a release build to a dev build fails",
        "System.WorkItemType": "Bug",
        "System.State": "In Review",
        "System.AreaPath": "AEPP\\OS",
        "System.IterationPath": "AEPP\\OS\\Sprint 59",
        "System.Description": "<p><b>DUT 1</b></p>",
        "Microsoft.VSTS.TCM.ReproSteps": "<div>Downgrade a printer</div>",
        "Microsoft.VSTS.TCM.SystemInfo": "",
        "Custom.ExpectedResults": "",
        "Custom.ActualResults": "<div>Downgrades seem to have intermittent issues</div>",
        "System.Tags": "Dev",
        "System.AssignedTo": {
            "displayName": "Tan Liu",
            "uniqueName": "tan_liu@bradycorp.com",
        },
    }
    fields.update(overrides)
    return {"id": 458732, "fields": fields}


class TestHtmlToMarkdown(unittest.TestCase):
    def test_converts_html_tags(self):
        self.assertEqual(html_to_markdown("<div>hi <b>bold</b></div>"), "hi **bold**")

    def test_empty_or_none_is_empty_string(self):
        self.assertEqual(html_to_markdown(""), "")
        self.assertEqual(html_to_markdown(None), "")


class TestSlugify(unittest.TestCase):
    def test_lowercases_and_collapses_non_alphanumerics(self):
        self.assertEqual(slugify("Build downgrade: from Release!"), "build-downgrade-from-release")

    def test_truncates_at_word_boundary_under_cap(self):
        title = "alpha bravo charlie delta echo foxtrot golf hotel"
        slug = slugify(title, max_len=20)
        self.assertLessEqual(len(slug), 20)
        self.assertEqual(slug, "alpha-bravo-charlie")  # cut before the partial "delta"


class TestSaveFilename(unittest.TestCase):
    def test_id_dash_slug(self):
        self.assertEqual(
            save_filename(458732, "Build downgrade from a release build to a dev build fails"),
            "458732-build-downgrade-from-a-release-build-to-a-dev-build-fails.md",
        )


class TestFrontmatter(unittest.TestCase):
    def test_includes_assignee_email_not_display_name(self):
        fm = frontmatter(_bug_item(), url="https://example/edit/458732")
        self.assertEqual(fm["assignee"], "tan_liu@bradycorp.com")
        self.assertEqual(fm["type"], "Bug")
        self.assertEqual(fm["id"], 458732)
        self.assertEqual(fm["url"], "https://example/edit/458732")

    def test_omits_assignee_when_unassigned(self):
        fm = frontmatter(_bug_item(**{"System.AssignedTo": None}), url="u")
        self.assertNotIn("assignee", fm)

    def test_title_with_colon_is_quoted_and_round_trips(self):
        item = _bug_item(**{"System.Title": "Fix: the thing"})
        md = render_work_item_markdown(item, [], MARKER, url="u", include_frontmatter=True)
        yaml = md.split("---")[1]
        self.assertIn('title: "Fix: the thing"', yaml)


class TestFindingsSection(unittest.TestCase):
    def test_strips_marker_prefix(self):
        comments = [{"text": f"{MARKER}\n\n### 2026-09-25 — Erich (agent)\n\nfound it"}]
        self.assertIn("found it", render_findings_section(comments, MARKER))
        self.assertNotIn(MARKER, render_findings_section(comments, MARKER))

    def test_no_marker_comment_is_empty(self):
        self.assertEqual(render_findings_section([{"text": "unrelated"}], MARKER), "")


class TestRenderWorkItemMarkdown(unittest.TestCase):
    def test_bug_sections_present_and_ordered(self):
        md = render_work_item_markdown(_bug_item(), [], MARKER, url="u")
        for heading in ["Description", "Repro Steps", "System Info", "Expected Results",
                         "Actual Results", "Tags", "Findings"]:
            self.assertIn(f"## {heading}", md)
        self.assertLess(md.index("## Description"), md.index("## Repro Steps"))
        self.assertLess(md.index("## Repro Steps"), md.index("## Actual Results"))

    def test_empty_field_section_stays_but_blank(self):
        md = render_work_item_markdown(_bug_item(), [], MARKER, url="u")
        # System Info is empty on this fixture but the heading must still appear.
        idx = md.index("## System Info")
        next_heading_idx = md.index("## Expected Results")
        between = md[idx:next_heading_idx]
        self.assertNotIn("<div>", between)

    def test_pbi_has_acceptance_criteria_not_repro_steps(self):
        item = _bug_item(**{
            "System.WorkItemType": "Product Backlog Item",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "<p>Must work</p>",
        })
        md = render_work_item_markdown(item, [], MARKER, url="u")
        self.assertIn("## Acceptance Criteria", md)
        self.assertNotIn("## Repro Steps", md)
        self.assertNotIn("## System Info", md)

    def test_other_type_only_has_description(self):
        item = _bug_item(**{"System.WorkItemType": "Task"})
        md = render_work_item_markdown(item, [], MARKER, url="u")
        self.assertIn("## Description", md)
        self.assertNotIn("## Repro Steps", md)
        self.assertNotIn("## Acceptance Criteria", md)

    def test_frontmatter_only_included_when_requested(self):
        without = render_work_item_markdown(_bug_item(), [], MARKER, url="u")
        self.assertFalse(without.startswith("---"))
        with_fm = render_work_item_markdown(_bug_item(), [], MARKER, url="u", include_frontmatter=True)
        self.assertTrue(with_fm.startswith("---"))


class TestListRendering(unittest.TestCase):
    def _query_items(self):
        return [
            {"fields": {"System.Id": 1, "System.Title": "Fix thing", "System.WorkItemType": "Bug",
                        "System.State": "To Do", "System.AssignedTo": {"displayName": "Erich Schroeter"}}},
        ]

    def test_markdown_table_has_pipes(self):
        md = render_list_markdown(self._query_items())
        self.assertIn("| ID | Title | Type | State | Assignee |", md)
        self.assertIn("Fix thing", md)

    def test_plain_table_has_no_pipes(self):
        table = render_list_table(self._query_items())
        self.assertNotIn("|", table)
        self.assertIn("Fix thing", table)

    def test_pipe_in_title_is_escaped_in_markdown_table(self):
        items = [{"fields": {"System.Id": 1, "System.Title": "Fix | thing", "System.WorkItemType": "Bug",
                              "System.State": "To Do", "System.AssignedTo": None}}]
        md = render_list_markdown(items)
        self.assertIn("Fix \\| thing", md)
        # 5 delimiter pipes in header/sep plus 4 in the data row (marker escaped, not counted as a column break).
        data_row = md.splitlines()[2]
        self.assertEqual(data_row.count(" | "), 4)


if __name__ == "__main__":
    unittest.main()
