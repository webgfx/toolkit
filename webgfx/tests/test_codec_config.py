from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


WEBGFX_DIR = Path(__file__).resolve().parents[1]
TOOLKIT_DIR = WEBGFX_DIR.parent
sys.path.insert(0, str(TOOLKIT_DIR))
sys.path.insert(0, str(WEBGFX_DIR))

from project import Project, _apply_gn_arg_overrides


class CodecConfigTest(unittest.TestCase):
    def test_apply_gn_arg_overrides_replaces_and_appends(self):
        with tempfile.TemporaryDirectory(prefix="webgfx-codecs-") as temp:
            args_path = Path(temp) / "args.gn"
            args_path.write_text(
                'proprietary_codecs = false\nffmpeg_branding = "Chromium"',
                encoding="utf-8",
            )

            _apply_gn_arg_overrides(
                args_path,
                {
                    "proprietary_codecs": "true",
                    "ffmpeg_branding": '"Chrome"',
                    "enable_nacl": "false",
                },
            )

            self.assertEqual(
                args_path.read_text(encoding="utf-8"),
                'proprietary_codecs = true\n'
                'ffmpeg_branding = "Chrome"\n'
                'enable_nacl = false\n',
            )

    def test_makefile_enforces_product_codec_branding_after_autogn(self):
        for product, branding, out_dir in (
            ("chromium", "Chrome", "out/release_x64"),
            ("edge", "Edge", "out/win_x64_release_developer_build"),
        ):
            with self.subTest(product=product), tempfile.TemporaryDirectory(
                prefix=f"webgfx-{product}-codecs-"
            ) as temp:
                root = Path(temp)
                source = root / "src"
                args_path = source / out_dir / "args.gn"
                args_path.parent.mkdir(parents=True)
                args_path.write_text(
                    'proprietary_codecs = false\nffmpeg_branding = "Chromium"\n',
                    encoding="utf-8",
                )

                project = object.__new__(Project)
                project.fuzzer = False
                project.is_debug = False
                project.project = product
                project.target_cpu = "x64"
                project.build_type = "release"
                project.root_dir = str(root)
                project.repo_dir = str(source)
                project.out_dir = out_dir
                project.exit_on_error = False

                with mock.patch.object(project, "_patch_autogn"), mock.patch(
                    "project.os.system", return_value=0
                ) as system, mock.patch.object(project, "_execute") as execute:
                    project.makefile()

                self.assertIn("--proprietary_codecs=true", system.call_args.args[0])
                self.assertIn(
                    f'--ffmpeg_branding="{branding}"',
                    system.call_args.args[0],
                )
                args_text = args_path.read_text(encoding="utf-8")
                self.assertIn("proprietary_codecs = true", args_text)
                self.assertIn(f'ffmpeg_branding = "{branding}"', args_text)
                execute.assert_called_once_with(
                    f"gn gen {out_dir}", exit_on_error=False
                )


if __name__ == "__main__":
    unittest.main()
