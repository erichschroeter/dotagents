"""
Live read-only smoke tests against the real bradycorp1/AEPP org (WI-006).
Exercises `list`/`show` only -- never `comment`'s write path. Auto-skips
the whole module when ADO_PAT isn't set, so the mocked unit tests remain
the default `python3 -m unittest discover` path.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ado_client

PAT = os.environ.get("ADO_PAT")


@unittest.skipUnless(PAT, "ADO_PAT not set; skipping live smoke tests")
class TestLiveAuthAndQuery(unittest.TestCase):
    def test_can_list_current_sprint_for_os_team(self):
        items = ado_client.list_work_items(assignee=None, sprint="current", team="OS", pat=PAT)
        self.assertIsInstance(items, list)

    def test_can_resolve_os_area_path(self):
        result = ado_client.area_team_default("OS", PAT)
        self.assertIn("AEPP", result["defaultValue"])

    def test_can_show_a_real_work_item(self):
        # Any real, stable item ID in AEPP; adjust if it's ever deleted.
        item = ado_client.show_work_item("458732", PAT)
        self.assertIn("fields", item)
        self.assertEqual(item["fields"]["System.WorkItemType"], "Bug")

    def test_can_fetch_comments_without_writing(self):
        comments = ado_client.get_comments("458732", PAT)
        self.assertIsInstance(comments, list)


if __name__ == "__main__":
    unittest.main()
