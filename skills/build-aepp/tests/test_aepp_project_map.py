"""
Tests for aepp_project_map.py against the real AEPP-git repo checkout.

Ticket: Determine how to extract project->architecture(s) and
project->source-path mapping (BAE-002).

Requires the repo at AEPP_REPO_ROOT (default /opt/BradyRD/AEPP-git).
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from aepp_project_map import resolve_all

REPO_ROOT = Path(os.environ.get("AEPP_REPO_ROOT", "/opt/BradyRD/AEPP-git"))


class TestAeppProjectMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (REPO_ROOT / "cmake" / "BuildList.cmake").exists():
            raise unittest.SkipTest(f"AEPP-git checkout not found at {REPO_ROOT}")
        cls.mapping = resolve_all(REPO_ROOT)

    def test_single_architecture_project_has_one_list(self):
        # PropertyServer only appears in LINUX_PROJECTS.
        info = self.mapping["PropertyServer"]
        self.assertEqual(info["lists"], ["LINUX_PROJECTS"])

    def test_nested_loc_resolves_below_top_level_project_dir(self):
        # PropertyServer's buildable source lives one level deeper than
        # Projects/PropertyServer.
        info = self.mapping["PropertyServer"]
        self.assertEqual(
            info["loc"],
            str(REPO_ROOT / "Projects" / "PropertyServer" / "PropertyServer"),
        )

    def test_multi_architecture_project_lists_every_membership(self):
        # IppServer spans QNX, Linux desktop, aarch64, and Windows.
        info = self.mapping["IppServer"]
        self.assertEqual(
            set(info["lists"]),
            {"QNX_PROJECTS", "LINUX_PROJECTS", "AARCH64_PROJECTS", "VS2022_PROJECTS"},
        )

    def test_freertos_projects_resolve_correctly(self):
        self.assertEqual(self.mapping["Artemis"]["lists"], ["M4_PROJECTS"])
        self.assertEqual(self.mapping["Sparta"]["lists"], ["M33_PROJECTS"])

    def test_loc_outside_projects_directory_is_resolved(self):
        # Several _LOC entries point under lib/ or CoreCode/, not Projects/.
        info = self.mapping["PahoMqttCpp"]
        self.assertEqual(info["loc"], str(REPO_ROOT / "lib" / "paho-mqtt-cpp"))
        self.assertEqual(info["lists"], [])

    def test_unknown_project_is_absent(self):
        self.assertNotIn("DoesNotExistProject", self.mapping)

    def test_platform_conditional_loc_honors_platform_definition(self):
        # ProjectIndex.cmake gates HttpLib_LOC on PLATFORM_DEFINITION; the
        # default resolve_all() call (no platform_definition) must not
        # silently report the QNX-specific path.
        default = resolve_all(REPO_ROOT)
        qnx = resolve_all(REPO_ROOT, platform_definition="QNX")
        self.assertEqual(default["HttpLib"]["loc"], str(REPO_ROOT / "lib" / "httplib" / "master"))
        self.assertEqual(qnx["HttpLib"]["loc"], str(REPO_ROOT / "lib" / "httplib" / "qnx710"))


if __name__ == "__main__":
    unittest.main()
