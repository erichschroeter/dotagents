"""
Tests for build.py's pure logic: architecture resolution, target-name
resolution, and build-output parsing (BAE-005). No devcontainer/CMake
invocation happens here; that's exercised manually against the real repo.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build import (
    AmbiguousArchitectureError,
    AmbiguousTargetError,
    resolve_architecture,
    resolve_targets,
    parse_artifact_paths,
    ARCH_TABLE,
    DEVCONTAINER_CONFIG_BY_ARCH,
)


class TestResolveArchitecture(unittest.TestCase):
    def test_single_valid_architecture_is_used_unconditionally(self):
        arch = resolve_architecture(["LINUX_PROJECTS"], requested_arch=None)
        self.assertEqual(arch, "linux")

    def test_ambiguous_with_aarch64_option_defaults_to_aarch64(self):
        # BAE-002's original default.
        arch = resolve_architecture(
            ["AARCH64_PROJECTS", "LINUX_PROJECTS"], requested_arch=None
        )
        self.assertEqual(arch, "linux-aarch64")

    def test_ambiguous_without_aarch64_option_fails_fast(self):
        # BAE-005 correction: default doesn't silently apply when
        # linux-aarch64 isn't one of the valid options.
        with self.assertRaises(AmbiguousArchitectureError) as ctx:
            resolve_architecture(["LINUX_PROJECTS", "QNX_PROJECTS"], requested_arch=None)
        self.assertIn("linux", str(ctx.exception))
        self.assertIn("qnx", str(ctx.exception))

    def test_explicit_arch_overrides_default(self):
        arch = resolve_architecture(
            ["AARCH64_PROJECTS", "LINUX_PROJECTS"], requested_arch="linux"
        )
        self.assertEqual(arch, "linux")

    def test_explicit_arch_is_always_honored_even_if_not_in_default_lists(self):
        # Verified real bug: PropertyServer is only in LINUX_PROJECTS (the
        # *default* per-platform build set), yet it builds successfully on
        # linux-aarch64 too, because BuildList.cmake's platform->list
        # mapping is skipped whenever -DPROJECT_LIST is set explicitly (as
        # this skill always does) -- list membership is not an exhaustive
        # validity registry. An explicit --arch must always be attempted;
        # only cmake itself can reject an unsupported combination.
        arch = resolve_architecture(["LINUX_PROJECTS"], requested_arch="linux-aarch64")
        self.assertEqual(arch, "linux-aarch64")

    def test_explicit_arch_must_be_a_known_architecture(self):
        with self.assertRaises(AmbiguousArchitectureError):
            resolve_architecture(["LINUX_PROJECTS"], requested_arch="not-a-real-arch")

    def test_windows_only_project_has_no_valid_architecture(self):
        with self.assertRaises(AmbiguousArchitectureError):
            resolve_architecture(["VS2022_PROJECTS"], requested_arch=None)


class TestResolveTargets(unittest.TestCase):
    def test_exact_name_match(self):
        text = "add_executable(PropertyServer)\n"
        self.assertEqual(resolve_targets(text), ["PropertyServer"])

    def test_create_project_target_macro(self):
        text = 'CreateProjectTarget(Icarus EXE version.json)\n'
        self.assertEqual(resolve_targets(text), ["Icarus"])

    def test_mismatched_name_is_still_resolved_when_unique(self):
        # CpuSpeedTest's real target is CpuSpeedTestApp.
        text = "add_executable(CpuSpeedTestApp)\n"
        self.assertEqual(resolve_targets(text), ["CpuSpeedTestApp"])

    def test_conditional_branches_of_the_same_project_name_prefer_project_name(self):
        # PropertyServer's real top-level CMakeLists.txt textually declares
        # PropertyServerBase plus two platform-gated `if()` branches that
        # both define a target named PropertyServer (only one is ever
        # active for a given build) -- must not be reported ambiguous.
        text = (
            "add_library(PropertyServerBase STATIC)\n"
            "if (PLATFORM_DEFINITION MATCHES \"QNX|LINUX\")\n"
            "    add_subdirectory(Posix)\n"
            "        add_executable(PropertyServer)\n"
            "elseif (PLATFORM_DEFINITION MATCHES \"WINDOWS_DESKTOP\")\n"
            "        add_library(PropertyServer SHARED)\n"
            "endif()\n"
        )
        self.assertEqual(resolve_targets(text, project_name="PropertyServer"), ["PropertyServer"])

    def test_no_target_found_raises(self):
        text = "FetchContent_Declare(Foo SOURCE_DIR ${Foo_LOC})\n"
        with self.assertRaises(AmbiguousTargetError):
            resolve_targets(text)

    def test_multiple_distinct_targets_found_raises(self):
        text = "add_library(PropertyServerBase STATIC)\nadd_executable(PropertyServerHandler)\n"
        with self.assertRaises(AmbiguousTargetError):
            resolve_targets(text)


class TestParseArtifactPaths(unittest.TestCase):
    def test_parses_single_linking_line(self):
        output = (
            "[278/279] Linking CXX static library _deps/aeppcore-build/Debug/libAEPPCore.a\n"
            "[279/279] Linking CXX executable artifacts/Debug/CpuSpeedTestApp\n"
        )
        self.assertEqual(
            parse_artifact_paths(output),
            [
                "_deps/aeppcore-build/Debug/libAEPPCore.a",
                "artifacts/Debug/CpuSpeedTestApp",
            ],
        )

    def test_no_linking_lines_returns_empty_list(self):
        self.assertEqual(parse_artifact_paths("no matches here\n"), [])


class TestDevcontainerConfigLookup(unittest.TestCase):
    def test_every_arch_id_resolve_architecture_can_return_has_a_devcontainer_config(self):
        # Regression: build_project looks up DEVCONTAINER_CONFIG_BY_ARCH by
        # the architecture id (e.g. "linux"), not by the *_PROJECTS list
        # name (e.g. "LINUX_PROJECTS") ARCH_TABLE is keyed by.
        arch_ids = {arch for arch, _ in ARCH_TABLE.values()}
        self.assertEqual(arch_ids, set(DEVCONTAINER_CONFIG_BY_ARCH))


class TestBuildProjectCommandConstruction(unittest.TestCase):
    """build_project must never interpolate untrusted values (project,
    target, config) into a shell string -- every devcontainer/cmake/ctest
    invocation must be a plain argv list passed straight to subprocess.run,
    with no intermediate shell that could interpret metacharacters."""

    def setUp(self):
        import build as build_module

        self.build_module = build_module
        self.calls = []

        def fake_resolve_all(repo_root):
            return {
                "Evil; rm -rf /": {"loc": "/tmp/does-not-matter", "lists": ["LINUX_PROJECTS"]},
            }

        def fake_run(cmd, **kwargs):
            self.calls.append(cmd)
            import subprocess as sp

            return sp.CompletedProcess(cmd, 0, stdout="", stderr="")

        self._orig_resolve_all = build_module.resolve_all
        self._orig_run = build_module._run
        build_module.resolve_all = fake_resolve_all
        build_module._run = fake_run

    def tearDown(self):
        self.build_module.resolve_all = self._orig_resolve_all
        self.build_module._run = self._orig_run

    def test_project_and_target_names_are_never_embedded_in_a_shell_string(self):
        # These would break out of a `bash -lc "...{value}..."`-style
        # f-string if one were used; as argv-only invocations they're inert.
        malicious = "Evil; rm -rf /"
        self.build_module.build_project(
            malicious,
            Path("/tmp"),
            requested_arch="linux",
            config="Debug",
            explicit_targets=["also; evil"],
            run_tests=False,
        )
        self.assertTrue(self.calls, "expected at least one subprocess invocation")
        for cmd in self.calls:
            self.assertIsInstance(cmd, list)
            self.assertNotIn("bash", cmd)
            self.assertNotIn("sh", cmd)
            self.assertNotIn("-lc", cmd)


if __name__ == "__main__":
    unittest.main()
