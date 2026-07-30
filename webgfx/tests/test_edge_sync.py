import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WEBGFX_DIR = Path(__file__).resolve().parents[1]
TOOLKIT_DIR = WEBGFX_DIR.parent
sys.path.insert(0, str(TOOLKIT_DIR))
sys.path.insert(0, str(WEBGFX_DIR))

from edge_sync import EdgeSyncError, EdgeSyncFix
from project import configure_depot_tools_path, detect_project


def run_git(repo, *arguments):
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


class DepotToolsPathTest(unittest.TestCase):
    def test_webgfx_prints_depot_tools_first(self):
        with tempfile.TemporaryDirectory(prefix="webgfx-startup-") as temp:
            root = Path(temp)
            edge_root = root / "edge"
            edge_tools = root / "depot_tools_edge"
            edge_root.mkdir()
            (edge_tools / "scripts").mkdir(parents=True)
            (edge_root / ".gclient").write_text(
                '"url": "https://microsoft.visualstudio.com/DefaultCollection/Edge/_git/chromium.src"',
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(WEBGFX_DIR / "webgfx.py"),
                    "--target",
                    "chrome",
                    "--root-dir",
                    str(edge_root),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(result.stdout.splitlines()[0], f"[INFO] Using depot_tools: {edge_tools}")

    def test_project_specific_depot_tools_are_prepended(self):
        original_path = os.environ.get("PATH", "")
        with tempfile.TemporaryDirectory(prefix="webgfx-path-") as temp:
            root = Path(temp)
            edge_root = root / "edge"
            chromium_root = root / "cr"
            edge_tools = root / "depot_tools_edge"
            chromium_tools = root / "depot_tools_cr"
            for path in (
                edge_root,
                chromium_root,
                edge_tools / "scripts",
                chromium_tools / "scripts",
            ):
                path.mkdir(parents=True)

            try:
                for project, project_root, expected_tools in (
                    ("edge", edge_root, edge_tools),
                    ("chromium", chromium_root, chromium_tools),
                ):
                    os.environ["PATH"] = original_path
                    selected = configure_depot_tools_path(str(project_root), project)
                    path_entries = os.environ["PATH"].split(os.pathsep)
                    self.assertEqual(os.path.normcase(selected), os.path.normcase(str(expected_tools)))
                    self.assertEqual(
                        [os.path.normcase(path) for path in path_entries[:2]],
                        [
                            os.path.normcase(str(expected_tools)),
                            os.path.normcase(str(expected_tools / "scripts")),
                        ],
                    )
            finally:
                os.environ["PATH"] = original_path

    def test_metadata_detects_neutral_edge_and_chromium_roots(self):
        with tempfile.TemporaryDirectory(prefix="webgfx-detect-") as temp:
            root = Path(temp)
            edge_root = root / "browser-one"
            chromium_root = root / "browser-two"
            edge_tools = root / "depot_tools_edge"
            chromium_tools = root / "depot_tools_cr"
            edge_root.mkdir()
            chromium_root.mkdir()
            (edge_tools / "scripts").mkdir(parents=True)
            (chromium_tools / "scripts").mkdir(parents=True)
            (edge_root / ".gclient").write_text(
                '"url": "https://microsoft.visualstudio.com/DefaultCollection/Edge/_git/chromium.src"',
                encoding="utf-8",
            )
            (chromium_root / ".gclient").write_text(
                '"url": "https://chromium.googlesource.com/chromium/src.git"',
                encoding="utf-8",
            )

            self.assertEqual(detect_project(str(edge_root)), "edge")
            self.assertEqual(detect_project(str(chromium_root)), "chromium")
            self.assertEqual(
                configure_depot_tools_path(str(edge_root), detect_project(str(edge_root))),
                str(edge_tools),
            )
            self.assertEqual(
                configure_depot_tools_path(str(chromium_root), detect_project(str(chromium_root))),
                str(chromium_tools),
            )

    def test_symlinked_neutral_root_finds_real_sibling_depot_tools(self):
        original_path = os.environ.get("PATH", "")
        with tempfile.TemporaryDirectory(prefix="webgfx-symlink-") as temp:
            root = Path(temp)
            enlistments = root / "enlistments"
            aliases = root / "aliases"
            edge_root = enlistments / "browser-one"
            edge_tools = enlistments / "depot_tools_edge"
            edge_alias = aliases / "current-browser"
            edge_root.mkdir(parents=True)
            (edge_tools / "scripts").mkdir(parents=True)
            aliases.mkdir()
            (edge_root / ".gclient").write_text(
                '"url": "https://microsoft.visualstudio.com/DefaultCollection/Edge/_git/chromium.src"',
                encoding="utf-8",
            )
            try:
                os.symlink(edge_root, edge_alias, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlinks are unavailable: {error}")

            try:
                self.assertEqual(detect_project(str(edge_alias)), "edge")
                self.assertEqual(
                    configure_depot_tools_path(str(edge_alias), detect_project(str(edge_alias))),
                    str(edge_tools),
                )
            finally:
                os.environ["PATH"] = original_path


class EdgeSyncFixTest(unittest.TestCase):
    def test_apply_is_idempotent_and_revert_works_offline(self):
        old_global = os.environ.get("GIT_CONFIG_GLOBAL")
        old_no_system = os.environ.get("GIT_CONFIG_NOSYSTEM")
        with tempfile.TemporaryDirectory(prefix="webgfx-edge-sync-") as temp:
            root = Path(temp)
            edge_root = root / "edge"
            source = edge_root / "src"
            seed = root / "seed"
            remote = root / "remote.git"
            global_config = root / "global.gitconfig"
            edge_root.mkdir()
            global_config.touch()

            try:
                os.environ["GIT_CONFIG_GLOBAL"] = str(global_config)
                os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
                subprocess.run(["git", "config", "--global", "pull.ff", "false"], check=True)
                subprocess.run(["git", "config", "--global", "maintenance.auto", "true"], check=True)
                subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, check=True)
                subprocess.run(["git", "init", "-b", "main", str(seed)], capture_output=True, check=True)
                run_git(seed, "config", "user.name", "Test")
                run_git(seed, "config", "user.email", "test@example.com")
                run_git(seed, "commit", "--allow-empty", "-m", "main")
                run_git(seed, "remote", "add", "origin", str(remote))
                run_git(seed, "push", "-u", "origin", "main")
                run_git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
                run_git(seed, "branch", "topic")
                run_git(seed, "branch", "release")
                run_git(seed, "push", "origin", "topic", "release")
                subprocess.run(["git", "clone", str(remote), str(source)], capture_output=True, check=True)
                run_git(source, "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*")
                run_git(source, "branch", "local-work")
                run_git(source, "tag", "keep-me")

                original_refs = run_git(
                    source,
                    "for-each-ref",
                    "--format=%(refname)%09%(objectname)%09%(symref)",
                    "refs/remotes/origin",
                )
                messages = []
                sync_fix = EdgeSyncFix(str(edge_root), output=messages.append)
                update_refs = sync_fix._update_refs
                update_calls = 0

                def fail_first_update(commands):
                    nonlocal update_calls
                    update_calls += 1
                    if update_calls == 1:
                        raise EdgeSyncError("injected apply failure")
                    return update_refs(commands)

                sync_fix._update_refs = fail_first_update
                with self.assertRaisesRegex(EdgeSyncError, "original state was restored automatically"):
                    sync_fix.apply()
                sync_fix._update_refs = update_refs
                self.assertEqual(
                    run_git(
                        source,
                        "for-each-ref",
                        "--format=%(refname)%09%(objectname)%09%(symref)",
                        "refs/remotes/origin",
                    ),
                    original_refs,
                )
                self.assertEqual(run_git(source, "config", "--get", "pull.ff"), ["false"])

                backup = sync_fix.apply()

                self.assertEqual(
                    len(run_git(source, "for-each-ref", "--format=%(refname)", "refs/remotes/origin")),
                    2,
                )
                self.assertEqual(run_git(source, "config", "--local", "--get", "pull.ff"), ["only"])
                self.assertIsNone(sync_fix.apply())
                self.assertEqual(len(os.listdir(os.path.dirname(backup))), 2)

                fixed_refs = run_git(
                    source,
                    "for-each-ref",
                    "--format=%(refname)%09%(objectname)%09%(symref)",
                    "refs/remotes/origin",
                )
                malformed_backup = root / "malformed-backup"
                shutil.copytree(backup, malformed_backup)
                (malformed_backup / "remote-refs.tsv").write_text("not-a-ref\n", encoding="utf-8")
                with self.assertRaisesRegex(EdgeSyncError, "Malformed remote-ref backup"):
                    sync_fix.revert(str(malformed_backup))
                self.assertEqual(
                    run_git(
                        source,
                        "for-each-ref",
                        "--format=%(refname)%09%(objectname)%09%(symref)",
                        "refs/remotes/origin",
                    ),
                    fixed_refs,
                )
                self.assertEqual(run_git(source, "config", "--local", "--get", "pull.ff"), ["only"])

                restore_ref_snapshot = sync_fix._restore_ref_snapshot
                restore_calls = 0

                def fail_first_restore(snapshot):
                    nonlocal restore_calls
                    restore_calls += 1
                    if restore_calls == 1:
                        raise EdgeSyncError("injected restore failure")
                    return restore_ref_snapshot(snapshot)

                sync_fix._restore_ref_snapshot = fail_first_restore
                with self.assertRaisesRegex(EdgeSyncError, "original state was restored automatically"):
                    sync_fix.revert(backup)
                sync_fix._restore_ref_snapshot = restore_ref_snapshot
                self.assertEqual(
                    run_git(
                        source,
                        "for-each-ref",
                        "--format=%(refname)%09%(objectname)%09%(symref)",
                        "refs/remotes/origin",
                    ),
                    fixed_refs,
                )
                self.assertEqual(run_git(source, "config", "--local", "--get", "pull.ff"), ["only"])

                shutil.move(remote, str(remote) + ".offline")
                sync_fix.revert()

                self.assertEqual(
                    run_git(
                        source,
                        "for-each-ref",
                        "--format=%(refname)%09%(objectname)%09%(symref)",
                        "refs/remotes/origin",
                    ),
                    original_refs,
                )
                self.assertEqual(run_git(source, "config", "--get", "pull.ff"), ["false"])
                self.assertEqual(run_git(source, "config", "--get", "maintenance.auto"), ["true"])
                self.assertIn(
                    "refs/heads/local-work",
                    run_git(source, "for-each-ref", "--format=%(refname)", "refs/heads"),
                )
                self.assertIn(
                    "refs/tags/keep-me",
                    run_git(source, "for-each-ref", "--format=%(refname)", "refs/tags"),
                )
            finally:
                if old_global is None:
                    os.environ.pop("GIT_CONFIG_GLOBAL", None)
                else:
                    os.environ["GIT_CONFIG_GLOBAL"] = old_global
                if old_no_system is None:
                    os.environ.pop("GIT_CONFIG_NOSYSTEM", None)
                else:
                    os.environ["GIT_CONFIG_NOSYSTEM"] = old_no_system


if __name__ == "__main__":
    unittest.main()