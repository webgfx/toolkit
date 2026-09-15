from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock


WEBGFX_DIR = Path(__file__).resolve().parents[1]
TOOLKIT_DIR = WEBGFX_DIR.parent
sys.path.insert(0, str(TOOLKIT_DIR))
sys.path.insert(0, str(WEBGFX_DIR))

from project import Project
from webgfx import Webgfx


class ArchitectureTest(unittest.TestCase):
    def test_project_uses_requested_target_architecture(self):
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory(prefix="webgfx-architecture-") as temp:
            try:
                with mock.patch("project.detect_project", return_value="dawn"), mock.patch(
                    "project.configure_depot_tools_path", return_value=None
                ):
                    project = Project(
                        root_dir=temp,
                        result_dir=str(Path(temp) / "result"),
                        target_arch="arm64",
                    )

                self.assertEqual(project.target_cpu, "arm64")
                self.assertEqual(project.out_dir, "out/release_arm64")
            finally:
                os.chdir(original_dir)

    def test_webgfx_forwards_target_architecture_to_project(self):
        original_dir = os.getcwd()
        with tempfile.TemporaryDirectory(prefix="webgfx-architecture-") as temp:
            try:
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "webgfx.py",
                        "--root-dir",
                        temp,
                        "--target",
                        "dawn",
                        "--target-arch",
                        "arm64",
                    ],
                ), mock.patch("webgfx.detect_project", return_value="dawn"), mock.patch(
                    "webgfx.configure_depot_tools_path", return_value=None
                ), mock.patch("webgfx.Project") as project:
                    Webgfx()

                    self.assertEqual(project.call_args.kwargs["target_arch"], "arm64")
            finally:
                os.chdir(original_dir)


if __name__ == "__main__":
    unittest.main()
