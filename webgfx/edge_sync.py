import datetime
import json
import os
import re
import subprocess


class EdgeSyncError(RuntimeError):
    pass


class EdgeSyncFix:
    REMOTE = "origin"
    MAIN_FETCH = "+refs/heads/main:refs/remotes/origin/main"
    BACKUP_VERSION = 2
    REF_BATCH_SIZE = 5000

    def __init__(self, edge_path, output=print):
        self.git_root = self._resolve_git_root(edge_path)
        edge_root = os.path.dirname(self.git_root) if os.path.basename(self.git_root).lower() == "src" else self.git_root
        remote_url = self._git("remote", "get-url", self.REMOTE)[0].lower()
        gclient_path = os.path.join(edge_root, ".gclient")
        gclient = ""
        if os.path.isfile(gclient_path):
            with open(gclient_path, encoding="utf-8", errors="replace") as input_file:
                gclient = input_file.read().lower()
        is_edge_remote = "microsoft.visualstudio.com" in remote_url and "/edge/_git/" in remote_url
        is_edge_gclient = "microsoft.visualstudio.com" in gclient and "/edge/_git/" in gclient
        if os.path.basename(os.path.realpath(edge_root)).lower() != "edge" and not is_edge_remote and not is_edge_gclient:
            raise EdgeSyncError(f"Edge sync fix requires an Edge checkout, not '{self.git_root}'.")
        self.edge_root = edge_root
        self.output = output

    @staticmethod
    def _resolve_git_root(edge_path):
        requested_path = os.path.abspath(edge_path)
        for candidate in (requested_path, os.path.join(requested_path, "src")):
            if not os.path.isdir(candidate):
                continue
            result = subprocess.run(
                ["git", "-C", candidate, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return os.path.normpath(result.stdout.strip())
        raise EdgeSyncError(f"No Git checkout found at '{edge_path}' or its 'src' subdirectory.")

    def _git(self, *arguments, input_text=None, allowed_exit_codes=(0,)):
        encoded_input = input_text.encode("utf-8") if input_text is not None else None
        result = subprocess.run(
            ["git", "-C", self.git_root, *arguments],
            input=encoded_input,
            capture_output=True,
            text=encoded_input is None,
            check=False,
        )
        stdout = result.stdout.decode("utf-8") if encoded_input is not None else result.stdout
        stderr = result.stderr.decode("utf-8") if encoded_input is not None else result.stderr
        if result.returncode not in allowed_exit_codes:
            command = "git " + " ".join(arguments)
            details = stderr.strip() or stdout.strip()
            raise EdgeSyncError(f"{command} failed with exit code {result.returncode}: {details}")
        return stdout.splitlines()

    def _local_config(self, name):
        return self._git("config", "--local", "--get-all", name, allowed_exit_codes=(0, 1))

    def _replace_local_config(self, name, values):
        self._git("config", "--local", "--unset-all", name, allowed_exit_codes=(0, 1, 5))
        for value in values:
            self._git("config", "--local", "--add", name, str(value))

    def _ref_records(self):
        return self._git(
            "for-each-ref",
            "--format=%(refname)%09%(objectname)%09%(symref)",
            f"refs/remotes/{self.REMOTE}",
        )

    def _ref_names(self):
        return self._git("for-each-ref", "--format=%(refname)", f"refs/remotes/{self.REMOTE}")

    def _update_refs(self, commands):
        if not commands:
            return
        input_text = "\n".join(["option no-deref", *commands]) + "\n"
        self._git("update-ref", "--stdin", input_text=input_text)

    def _is_applied(self):
        allowed_refs = {
            f"refs/remotes/{self.REMOTE}/HEAD",
            f"refs/remotes/{self.REMOTE}/main",
        }
        return (
            self._local_config(f"remote.{self.REMOTE}.fetch") == [self.MAIN_FETCH]
            and self._local_config(f"remote.{self.REMOTE}.tagOpt") == ["--no-tags"]
            and self._local_config("pull.ff") == ["only"]
            and self._local_config("maintenance.auto") == ["false"]
            and set(self._ref_names()) == allowed_refs
        )

    def _create_backup(self, config, ref_records, backup_group="backups"):
        git_dir = os.path.normpath(self._git("rev-parse", "--absolute-git-dir")[0])
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_dir = os.path.join(git_dir, "edge-sync-analysis", backup_group, timestamp)
        os.makedirs(backup_dir)

        config_path = os.path.join(backup_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as output_file:
            json.dump(config, output_file, indent=2)
            output_file.write("\n")

        refs_path = os.path.join(backup_dir, "remote-refs.tsv")
        with open(refs_path, "w", encoding="utf-8", newline="\n") as output_file:
            if ref_records:
                output_file.write("\n".join(ref_records) + "\n")
        return backup_dir

    @staticmethod
    def _validated_config_values(config, name, required=False):
        if name not in config:
            if required:
                raise EdgeSyncError(f"Backup does not contain required field '{name}'.")
            return None
        value = config[name]
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
        raise EdgeSyncError(f"Backup field '{name}' must be a string or list of strings.")

    def _current_config_values(self):
        return {
            f"remote.{self.REMOTE}.fetch": self._local_config(f"remote.{self.REMOTE}.fetch"),
            f"remote.{self.REMOTE}.tagOpt": self._local_config(f"remote.{self.REMOTE}.tagOpt"),
            "pull.ff": self._local_config("pull.ff"),
            "maintenance.auto": self._local_config("maintenance.auto"),
        }

    def _backup_config(self, config_values, backup_type=None):
        config = {
            "formatVersion": self.BACKUP_VERSION,
            "remote": self.REMOTE,
            "fetch": config_values[f"remote.{self.REMOTE}.fetch"],
            "tagOpt": config_values[f"remote.{self.REMOTE}.tagOpt"],
            "pullFF": config_values["pull.ff"],
            "maintenanceAuto": config_values["maintenance.auto"],
            "remoteRefsFile": "remote-refs.tsv",
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if backup_type:
            config["backupType"] = backup_type
        return config

    def _parse_ref_records(self, records, validate_objects=True):
        names = set()
        direct_updates = []
        symbolic_refs = []
        object_names = set()
        prefix = f"refs/remotes/{self.REMOTE}/"
        for record in records:
            parts = record.split("\t", 2)
            if len(parts) != 3:
                raise EdgeSyncError(f"Malformed remote-ref backup record: {record}")
            ref_name, object_name, symref = parts
            if not ref_name.startswith(prefix) or any(character.isspace() for character in ref_name):
                raise EdgeSyncError(f"Out-of-scope or malformed remote ref: {ref_name}")
            if ref_name in names:
                raise EdgeSyncError(f"Duplicate remote ref in backup: {ref_name}")
            if not re.fullmatch(r"[0-9a-fA-F]{40,64}", object_name):
                raise EdgeSyncError(f"Invalid object ID for {ref_name}: {object_name}")
            names.add(ref_name)
            object_names.add(object_name)
            if symref:
                symbolic_refs.append((ref_name, symref))
            else:
                direct_updates.append(f"update {ref_name} {object_name}")

        for ref_name, target in symbolic_refs:
            if target not in names or not target.startswith(prefix):
                raise EdgeSyncError(f"Symbolic ref {ref_name} targets missing or out-of-scope ref {target}.")
        if f"refs/remotes/{self.REMOTE}/main" not in names:
            raise EdgeSyncError("Remote-ref backup does not contain origin/main.")

        if validate_objects and object_names:
            object_list = sorted(object_names)
            results = self._git(
                "cat-file",
                "--batch-check=%(objectname) %(objecttype)",
                input_text="\n".join(object_list) + "\n",
            )
            if len(results) != len(object_list) or any(result.endswith(" missing") for result in results):
                raise EdgeSyncError("Remote-ref backup references objects missing from this checkout.")

        return {
            "records": records,
            "names": names,
            "direct_updates": direct_updates,
            "symbolic_refs": symbolic_refs,
        }

    def _load_backup(self, backup_dir):
        config_path = os.path.join(backup_dir, "config.json")
        if not os.path.isfile(config_path):
            raise EdgeSyncError(f"Backup '{backup_dir}' does not contain config.json.")
        try:
            with open(config_path, encoding="utf-8-sig") as input_file:
                config = json.load(input_file)
        except (OSError, json.JSONDecodeError) as error:
            raise EdgeSyncError(f"Could not read backup config '{config_path}': {error}") from error
        if not isinstance(config, dict) or config.get("remote") != self.REMOTE:
            raise EdgeSyncError(f"Backup '{backup_dir}' is not for remote '{self.REMOTE}'.")
        format_version = config.get("formatVersion", 1)
        if not isinstance(format_version, int) or format_version < 1 or format_version > self.BACKUP_VERSION:
            raise EdgeSyncError(f"Unsupported backup format version: {format_version}")

        fetch_key = f"remote.{self.REMOTE}.fetch"
        tag_key = f"remote.{self.REMOTE}.tagOpt"
        expected_config = {
            fetch_key: self._validated_config_values(config, "fetch", required=True),
            tag_key: self._validated_config_values(config, "tagOpt", required=True),
        }
        pull_ff = self._validated_config_values(config, "pullFF")
        maintenance_auto = self._validated_config_values(config, "maintenanceAuto")
        if pull_ff is not None:
            expected_config["pull.ff"] = pull_ff
        if maintenance_auto is not None:
            expected_config["maintenance.auto"] = maintenance_auto

        refs_file = config.get("remoteRefsFile")
        snapshot = None
        if refs_file is not None:
            if not isinstance(refs_file, str) or os.path.basename(refs_file) != refs_file:
                raise EdgeSyncError("Backup remoteRefsFile must be a relative file name.")
            refs_path = os.path.join(backup_dir, refs_file)
            if not os.path.isfile(refs_path):
                raise EdgeSyncError(f"Backup ref snapshot is missing: {refs_path}")
            with open(refs_path, encoding="utf-8") as input_file:
                records = [line.rstrip("\r\n") for line in input_file if line.strip()]
            snapshot = self._parse_ref_records(records)
        elif format_version >= self.BACKUP_VERSION:
            raise EdgeSyncError("Version-2 backup does not identify a remote-ref snapshot.")
        return expected_config, snapshot

    def _restore_config(self, expected_config):
        for name, values in expected_config.items():
            self._replace_local_config(name, values)

    def _verify_state(self, expected_config, snapshot=None):
        for name, expected_values in expected_config.items():
            if self._local_config(name) != [str(value) for value in expected_values]:
                raise EdgeSyncError(f"Restore verification failed for local config '{name}'.")
        if snapshot is not None and self._ref_records() != snapshot["records"]:
            raise EdgeSyncError("Restore verification failed for local remote-tracking refs.")

    def apply(self):
        self._git("remote", "get-url", self.REMOTE)
        self._git("show-ref", "--verify", "--quiet", f"refs/remotes/{self.REMOTE}/main")
        if self._is_applied():
            self.output(f"Edge sync fix is already applied and verified: {self.git_root}")
            return None

        fetch_key = f"remote.{self.REMOTE}.fetch"
        tag_key = f"remote.{self.REMOTE}.tagOpt"
        current_config = self._current_config_values()
        ref_records = self._ref_records()
        current_snapshot = self._parse_ref_records(ref_records, validate_objects=False)
        refs_before = [record.split("\t", 1)[0] for record in ref_records]
        branches_before = self._git("for-each-ref", "--format=%(refname)", "refs/heads")
        tags_before = self._git("for-each-ref", "--format=%(refname)", "refs/tags")
        config = self._backup_config(current_config, backup_type="pre-apply")
        backup_dir = self._create_backup(config, ref_records)
        self.output(f"Edge sync backup created before changes: {backup_dir}")

        try:
            self._replace_local_config(fetch_key, [self.MAIN_FETCH])
            self._replace_local_config(tag_key, ["--no-tags"])
            self._replace_local_config("maintenance.auto", ["false"])
            self._replace_local_config("pull.ff", ["only"])

            refs_to_delete = [
                ref_name
                for ref_name in refs_before
                if ref_name
                not in {
                    f"refs/remotes/{self.REMOTE}/HEAD",
                    f"refs/remotes/{self.REMOTE}/main",
                }
            ]
            self._update_refs([f"delete {ref_name}" for ref_name in refs_to_delete])
            self._git("remote", "set-head", self.REMOTE, "main")
            self._git("pack-refs", "--all", "--prune")

            if not self._is_applied():
                raise EdgeSyncError("Final Edge sync configuration or remote refs did not verify.")
            if branches_before != self._git("for-each-ref", "--format=%(refname)", "refs/heads"):
                raise EdgeSyncError("Local branches changed while applying the Edge sync fix.")
            if tags_before != self._git("for-each-ref", "--format=%(refname)", "refs/tags"):
                raise EdgeSyncError("Local tags changed while applying the Edge sync fix.")
        except Exception as apply_error:
            try:
                self._restore_config(current_config)
                self._restore_ref_snapshot(current_snapshot)
                self._verify_state(current_config, current_snapshot)
            except Exception as rollback_error:
                raise EdgeSyncError(
                    f"Apply and automatic rollback both failed. Recover from '{backup_dir}'. "
                    f"Apply error: {apply_error}. Rollback error: {rollback_error}"
                ) from rollback_error
            raise EdgeSyncError(
                f"Apply failed; the original state was restored automatically. "
                f"Backup: '{backup_dir}'. Error: {apply_error}"
            ) from apply_error

        self.output(f"Edge sync fix applied: {len(refs_before)} -> {len(self._ref_names())} remote-tracking refs")
        self.output(f"Backup for --edge-sync-fix revert: {backup_dir}")
        return backup_dir

    def _latest_backup(self):
        git_dir = self._git("rev-parse", "--absolute-git-dir")[0]
        backups_dir = os.path.join(git_dir, "edge-sync-analysis", "backups")
        if not os.path.isdir(backups_dir):
            raise EdgeSyncError(f"No Edge sync backups found under '{backups_dir}'.")
        backups = [
            os.path.join(backups_dir, name)
            for name in os.listdir(backups_dir)
            if os.path.isfile(os.path.join(backups_dir, name, "config.json"))
        ]
        if not backups:
            raise EdgeSyncError(f"No Edge sync backups found under '{backups_dir}'.")
        return max(backups, key=os.path.getmtime)

    def _restore_ref_snapshot(self, snapshot):
        current_names = set(self._ref_names())
        for offset in range(0, len(snapshot["direct_updates"]), self.REF_BATCH_SIZE):
            self._update_refs(snapshot["direct_updates"][offset : offset + self.REF_BATCH_SIZE])
        for ref_name, target in snapshot["symbolic_refs"]:
            self._git("symbolic-ref", ref_name, target)
        self._update_refs([f"delete {ref_name}" for ref_name in sorted(current_names - snapshot["names"])])
        self._git("pack-refs", "--all", "--prune")

    def revert(self, backup_dir=None):
        backup_dir = os.path.abspath(backup_dir) if backup_dir else self._latest_backup()
        expected_config, target_snapshot = self._load_backup(backup_dir)

        current_config = self._current_config_values()
        current_records = self._ref_records()
        current_snapshot = self._parse_ref_records(current_records, validate_objects=False)
        safety_backup = self._create_backup(
            self._backup_config(current_config, backup_type="pre-revert"),
            current_records,
            backup_group="restore-safety",
        )
        self.output(f"Pre-revert safety backup created before changes: {safety_backup}")

        try:
            self._restore_config(expected_config)
            if target_snapshot is not None:
                self._restore_ref_snapshot(target_snapshot)
            else:
                self.output("Older backup has no remote-ref snapshot; current remote-tracking refs were left unchanged.")
            self._verify_state(expected_config, target_snapshot)
        except Exception as restore_error:
            try:
                self._restore_config(current_config)
                self._restore_ref_snapshot(current_snapshot)
                self._verify_state(current_config, current_snapshot)
            except Exception as rollback_error:
                raise EdgeSyncError(
                    f"Revert and automatic rollback both failed. Recover from '{safety_backup}'. "
                    f"Revert error: {restore_error}. Rollback error: {rollback_error}"
                ) from rollback_error
            raise EdgeSyncError(
                f"Revert failed; the original state was restored automatically. "
                f"Target backup: '{backup_dir}'. Error: {restore_error}"
            ) from restore_error

        self.output(f"Edge sync state restored from: {backup_dir}")
        self.output(f"Pre-revert safety backup: {safety_backup}")
        return backup_dir