"""
Tests for ado_client.py: WIQL construction, sprint-timeframe resolution,
and the findings-comment find-or-create/concurrency logic (WI-003, WI-005).
`subprocess.run` is mocked throughout -- no real `az`/network calls.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ado_client
from ado_client import (
    AdoError,
    ConcurrentUpdateError,
    append_findings_comment,
    build_wiql,
    find_findings_comment,
    format_findings_section,
    require_pat,
    resolve_iteration_path,
)


def _completed(stdout, returncode=0, stderr=""):
    class _Result:
        pass

    r = _Result()
    r.stdout = stdout if isinstance(stdout, str) else json.dumps(stdout)
    r.stderr = stderr
    r.returncode = returncode
    return r


class TestRequirePat(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_pat_raises_with_setup_pointer(self):
        with self.assertRaises(AdoError) as ctx:
            require_pat()
        self.assertIn("ADO_PAT", str(ctx.exception))
        self.assertIn("SKILL.md", str(ctx.exception))

    @patch.dict("os.environ", {"ADO_PAT": "secret"}, clear=True)
    def test_present_pat_is_returned(self):
        self.assertEqual(require_pat(), "secret")


class TestResolveIterationPath(unittest.TestCase):
    @patch("ado_client._run_az")
    def test_current_uses_timeframe_and_returns_single_path(self, mock_run):
        mock_run.return_value = _completed([{"path": "AEPP\\OS\\Sprint 59"}])
        path = resolve_iteration_path("OS", "current", pat="x")
        self.assertEqual(path, "AEPP\\OS\\Sprint 59")
        args = mock_run.call_args[0][0]
        self.assertIn("--timeframe", args)
        self.assertIn("current", args)

    @patch("ado_client._run_az")
    def test_future_picks_nearest_upcoming_iteration(self, mock_run):
        mock_run.return_value = _completed([
            {"path": "Sprint 60", "attributes": {"startDate": "2099-01-01T00:00:00Z", "finishDate": "2099-01-14T00:00:00Z"}},
            {"path": "Sprint 61", "attributes": {"startDate": "2099-01-15T00:00:00Z", "finishDate": "2099-01-28T00:00:00Z"}},
        ])
        path = resolve_iteration_path("OS", "future", pat="x")
        self.assertEqual(path, "Sprint 60")

    @patch("ado_client._run_az")
    def test_past_picks_nearest_prior_iteration(self, mock_run):
        mock_run.return_value = _completed([
            {"path": "Sprint 1", "attributes": {"startDate": "2000-01-01T00:00:00Z", "finishDate": "2000-01-14T00:00:00Z"}},
            {"path": "Sprint 2", "attributes": {"startDate": "2000-01-15T00:00:00Z", "finishDate": "2000-01-28T00:00:00Z"}},
        ])
        path = resolve_iteration_path("OS", "past", pat="x")
        self.assertEqual(path, "Sprint 2")

    @patch("ado_client._run_az")
    def test_no_current_iteration_raises(self, mock_run):
        mock_run.return_value = _completed([])
        with self.assertRaises(AdoError):
            resolve_iteration_path("OS", "current", pat="x")


class TestBuildWiql(unittest.TestCase):
    def test_no_filters_is_project_scoped_only(self):
        wiql = build_wiql(None, None, None, pat="x")
        where_clause = wiql.split("WHERE", 1)[1]
        self.assertIn("[System.TeamProject] = 'AEPP'", wiql)
        self.assertNotIn("AssignedTo", where_clause)
        self.assertNotIn("IterationPath", where_clause)
        self.assertNotIn("AreaPath", where_clause)

    def test_assignee_me(self):
        wiql = build_wiql("me", None, None, pat="x")
        self.assertIn("[System.AssignedTo] = @Me", wiql)

    def test_assignee_none_is_unassigned(self):
        wiql = build_wiql("none", None, None, pat="x")
        self.assertIn("[System.AssignedTo] = ''", wiql)

    def test_assignee_verbatim_string(self):
        wiql = build_wiql("someone@example.com", None, None, pat="x")
        self.assertIn("[System.AssignedTo] = 'someone@example.com'", wiql)

    @patch("ado_client.area_team_default")
    def test_team_uses_under_not_equals(self, mock_area):
        mock_area.return_value = {"defaultValue": "AEPP\\OS"}
        wiql = build_wiql(None, None, "OS", pat="x")
        self.assertIn("[System.AreaPath] UNDER 'AEPP\\OS'", wiql)

    @patch("ado_client.resolve_iteration_path")
    def test_sprint_without_team_defaults_to_os(self, mock_resolve):
        mock_resolve.return_value = "AEPP\\OS\\Sprint 59"
        build_wiql(None, "current", None, pat="x")
        mock_resolve.assert_called_once_with(ado_client.DEFAULT_TEAM, "current", "x")

    @patch("ado_client.area_team_default")
    @patch("ado_client.resolve_iteration_path")
    def test_sprint_with_team_uses_that_team(self, mock_resolve, mock_area):
        mock_resolve.return_value = "AEPP\\THT\\Sprint 5"
        mock_area.return_value = {"defaultValue": "AEPP\\THT"}
        build_wiql(None, "current", "THT", pat="x")
        mock_resolve.assert_called_once_with("THT", "current", "x")


class TestFindingsComment(unittest.TestCase):
    MARKER = ado_client.FINDINGS_MARKER

    def test_find_findings_comment_matches_marker_prefix(self):
        comments = [{"text": "hello"}, {"text": f"{self.MARKER}\n\nstuff", "id": 5}]
        found = find_findings_comment(comments)
        self.assertEqual(found["id"], 5)

    def test_find_findings_comment_none_when_absent(self):
        self.assertIsNone(find_findings_comment([{"text": "hello"}]))

    def test_format_section_includes_agent_suffix(self):
        section = format_findings_section("Erich Schroeter", "found the bug")
        self.assertIn("Erich Schroeter (agent)", section)
        self.assertIn("found the bug", section)

    @patch("ado_client.create_findings_comment")
    @patch("ado_client.get_comments")
    def test_creates_comment_when_none_exists(self, mock_get, mock_create):
        mock_get.return_value = []
        append_findings_comment("1", "Erich", "text", pat="x")
        mock_create.assert_called_once()

    @patch("ado_client.patch_findings_comment")
    @patch("ado_client.get_comments")
    def test_patches_existing_comment_when_version_unchanged(self, mock_get, mock_patch):
        existing = {"id": 5, "version": 1, "text": self.MARKER}
        mock_get.side_effect = [[existing], [existing]]
        append_findings_comment("1", "Erich", "text", pat="x")
        mock_patch.assert_called_once()
        new_text = mock_patch.call_args[0][2]
        self.assertIn("Erich", new_text)

    @patch("ado_client.patch_findings_comment")
    @patch("ado_client.get_comments")
    def test_raises_when_version_changed_between_reads(self, mock_get, mock_patch):
        first = {"id": 5, "version": 1, "text": self.MARKER}
        second = {"id": 5, "version": 2, "text": self.MARKER + "\n\nsomeone else's edit"}
        mock_get.side_effect = [[first], [second]]
        with self.assertRaises(ConcurrentUpdateError):
            append_findings_comment("1", "Erich", "text", pat="x")
        mock_patch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
