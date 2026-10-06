"""
Tests for work_item.py's CLI dispatch and I/O glue (WI-006): argument
parsing, comment-text precedence (positional > --file > stdin), and
--save writing to work-items/<id>-<slug>.md. ado_client is mocked -- no
real ADO calls.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import work_item


def _bug_item():
    return {
        "id": 458732,
        "fields": {
            "System.Title": "Fix the thing",
            "System.WorkItemType": "Bug",
            "System.State": "Active",
            "System.AreaPath": "AEPP\\OS",
            "System.IterationPath": "AEPP\\OS\\Sprint 59",
            "System.Description": "<p>desc</p>",
            "Microsoft.VSTS.TCM.ReproSteps": "",
            "Microsoft.VSTS.TCM.SystemInfo": "",
            "Custom.ExpectedResults": "",
            "Custom.ActualResults": "",
            "System.Tags": "",
        },
    }


class TestCommentTextPrecedence(unittest.TestCase):
    def _args(self, text=None, file=None):
        ns = work_item.argparse.Namespace(id="1", text=text, file=file, author=None)
        return ns

    def test_positional_wins_over_file_and_stdin(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("from file")
            file_path = Path(f.name)
        try:
            args = self._args(text="from positional", file=file_path)
            self.assertEqual(work_item._resolve_comment_text(args), "from positional")
        finally:
            file_path.unlink()

    def test_file_wins_over_stdin(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("from file")
            file_path = Path(f.name)
        try:
            args = self._args(text=None, file=file_path)
            self.assertEqual(work_item._resolve_comment_text(args), "from file")
        finally:
            file_path.unlink()

    @patch("sys.stdin")
    def test_stdin_used_when_nothing_else_given(self, mock_stdin):
        mock_stdin.read.return_value = "from stdin"
        args = self._args(text=None, file=None)
        self.assertEqual(work_item._resolve_comment_text(args), "from stdin")


class TestCmdShow(unittest.TestCase):
    @patch("ado_client.get_comments")
    @patch("ado_client.show_work_item")
    @patch("ado_client.require_pat")
    def test_save_writes_file_under_work_items_dir(self, mock_pat, mock_show, mock_comments):
        mock_pat.return_value = "x"
        mock_show.return_value = _bug_item()
        mock_comments.return_value = []
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = work_item.WORK_ITEMS_DIR
            old_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmp)
                work_item.WORK_ITEMS_DIR = Path("work-items")
                args = work_item.argparse.Namespace(id="458732", save=True)
                rc = work_item.cmd_show(args)
                self.assertEqual(rc, 0)
                saved = Path("work-items") / "458732-fix-the-thing.md"
                self.assertTrue(saved.exists())
                self.assertTrue(saved.read_text().startswith("---"))
            finally:
                os.chdir(old_cwd)
                work_item.WORK_ITEMS_DIR = old_dir

    @patch("ado_client.get_comments")
    @patch("ado_client.show_work_item")
    @patch("ado_client.require_pat")
    def test_no_save_prints_without_frontmatter(self, mock_pat, mock_show, mock_comments, ):
        mock_pat.return_value = "x"
        mock_show.return_value = _bug_item()
        mock_comments.return_value = []
        args = work_item.argparse.Namespace(id="458732", save=False)
        with patch("builtins.print") as mock_print:
            rc = work_item.cmd_show(args)
        self.assertEqual(rc, 0)
        printed = "".join(str(c.args[0]) for c in mock_print.call_args_list)
        self.assertFalse(printed.startswith("---"))


class TestCmdComment(unittest.TestCase):
    @patch("ado_client.append_findings_comment")
    @patch("ado_client.require_pat")
    def test_empty_text_is_rejected(self, mock_pat, mock_append):
        mock_pat.return_value = "x"
        args = work_item.argparse.Namespace(id="1", text="   ", file=None, author=None)
        rc = work_item.cmd_comment(args)
        self.assertEqual(rc, 1)
        mock_append.assert_not_called()

    @patch("ado_client.append_findings_comment")
    @patch("ado_client.require_pat")
    def test_defaults_author_to_os_username(self, mock_pat, mock_append):
        mock_pat.return_value = "x"
        args = work_item.argparse.Namespace(id="1", text="found it", file=None, author=None)
        work_item.cmd_comment(args)
        called_author = mock_append.call_args[0][1]
        self.assertTrue(called_author)  # non-empty; exact OS username isn't asserted


if __name__ == "__main__":
    unittest.main()
