import os
import re
import shutil

from util.base import Util, Program, ChromiumRepo, Timer


class Project(Program):
    # angle == angle_e2e
    # dawn == dawn_e2e
    BUILD_TARGET_DICT = {
        "angle": "angle_end2end_tests",
        "angle_perf": "angle_perftests",
        "angle_unit": "angle_unittests",
        "dawn": "dawn_end2end_tests",
        "webgl": "chrome/test:telemetry_gpu_integration_test",
        "webgpu": "chrome/test:telemetry_gpu_integration_test",
    }
    BACKUP_TARGET_DICT = {
        "angle": "angle_end2end_tests",
        "angle_perf": "angle_perftests",
        "angle_unit": "angle_unittests",
        "dawn": "dawn_end2end_tests",
        "chrome": "//chrome:chrome",
        "gl_tests": "//gpu:gl_tests",
        "vulkan_tests": "//gpu/vulkan:vulkan_tests",
        "webgpu_blink_web_tests": "//:webgpu_blink_web_tests",
        "webgl": "//chrome/test:telemetry_gpu_integration_test",
        "webgpu": "//chrome/test:telemetry_gpu_integration_test",
        "gl_unittests": "//ui/gl:gl_unittests",
    }
    SEPARATOR = ": "

    def __init__(self, root_dir, result_dir, is_debug=False):
        super().__init__()
        project = os.path.basename(root_dir)
        # handle project chromium
        if "chromium" in project or "chrome" in project or "cr" in project or "edge" in project:
            project = "chromium"
        self.project = project

        if project == "chromium":
            self.repo = ChromiumRepo(root_dir)

        self.project_backup_dir = f"{Util.BACKUP_DIR}/{self.project}"
        self.server_backup_dir = f"\\\\{Util.BACKUP_SERVER}\\backup\\{self.target_cpu}\\{Util.HOST_OS}\\{self.project}"

        if is_debug:
            build_type = "debug"
        else:
            build_type = "release"
        self.build_type = build_type

        self.is_debug = is_debug
        self.out_dir = f"out/{self.build_type}_{self.target_cpu}"
        self.exit_on_error = False
        self.root_dir = root_dir
        self.result_dir = result_dir
        self.run_log = f"{self.result_dir}/run.log"

        if project == "chromium":
            self.repo_dir = f"{root_dir}/src"
        else:
            self.repo_dir = root_dir

        if os.path.exists(self.repo_dir):
            Util.chdir(self.repo_dir)

    def sync(self, verbose=False):
        self._execute("git pull --no-recurse-submodules", exit_on_error=self.exit_on_error)
        cmd = f"gclient sync -j{Util.CPU_COUNT}"
        if verbose:
            cmd += " -v"
        self._execute(cmd=cmd, exit_on_error=self.exit_on_error)

    def makefile(
        self,
        dcheck=True,
        is_component_build=False,
        treat_warning_as_error=True,
        disable_official_build=False,
        vulkan_only=False,
        target_os=Util.HOST_OS,
        symbol_level=-1,
        local=False,
    ):
        if symbol_level == -1:
            if self.is_debug:
                symbol_level = 2
            else:
                symbol_level = 2

        if self.project == 'chromium':
            cmd = f'autogn {self.target_cpu} {self.build_type} -a {self.root_dir}'
            if is_component_build:
                cmd += " --is-component-build=true"
            if not local:
                cmd += " --use-remoteexec"
            cmd += f' --proprietary_codecs=true --ffmpeg_branding=\\"Chrome\\" --symbol_level={symbol_level}'
            Util.info(cmd)
            os.system(cmd)
            return

        if local:
            gn_args = ""
        else:
            gn_args = "use_remoteexec=true"

        if self.is_debug:
            gn_args += " is_debug=true"
        else:
            gn_args += " is_debug=false"

        if dcheck:
            gn_args += " dcheck_always_on=true"
        else:
            gn_args += " dcheck_always_on=false"

        if is_component_build:
            gn_args += " is_component_build=true"
        else:
            gn_args += " is_component_build=false"

        if treat_warning_as_error:
            gn_args += " treat_warnings_as_errors=true"
        else:
            gn_args += " treat_warnings_as_errors=false"

        gn_args += f" symbol_level={symbol_level}"

        if self.project == "chromium":
            if symbol_level == 0:
                gn_args += " blink_symbol_level=0 v8_symbol_level=0"

            gn_args += " enable_nacl=false proprietary_codecs=true"

            # for windows, it has to use "" instead of ''
            if Util.HOST_OS == Util.WINDOWS:
                gn_args += ' ffmpeg_branding=\\"Chrome\\"'
            else:
                gn_args += ' ffmpeg_branding="Chrome"'

            if not disable_official_build:
                gn_args += " is_official_build=true use_cfi_icall=false chrome_pgo_phase=0"

        if vulkan_only:
            if self.project == "angle":
                # angle_enable_glsl=false angle_enable_essl=false angle_enable_hlsl=false
                gn_args += " angle_enable_gl=false angle_enable_metal=false angle_enable_d3d9=false angle_enable_d3d11=false angle_enable_null=false"
            elif self.project == "dawn":
                gn_args += (
                    " dawn_enable_d3d12=false dawn_enable_metal=false dawn_enable_null=false dawn_enable_opengles=false"
                )

        if target_os == Util.ANDROID:
            if Util.HOST_OS == Util.WINDOWS:
                gn_args += ' target_os=\\"android\\" target_cpu=\\"x64\\"'
            else:
                gn_args += ' target_os="android" target_cpu="x64"'

        if Util.HOST_OS == Util.WINDOWS:
            gn_args += f' target_cpu=\\"{self.target_cpu}\\"'

        if self.project == "dawn" and target_os == Util.WINDOWS:
            gn_args += " dawn_use_swiftshader=false"
            # Below gn args couldn't be set
            # gn_args += ' dawn_supports_glfw_for_windowing=false dawn_use_glfw=false dawn_use_windows_ui=false tint_build_cmd_tools=false tint_build_tests=false'

        cmd = f'gn gen {self.out_dir} --args="{gn_args}"'
        Util.info(cmd)
        os.system(cmd)

    def build(self, target):
        build_targets = []
        if target in self.BUILD_TARGET_DICT.keys():
            build_targets.append(self.BUILD_TARGET_DICT[target])
        else:
            build_targets.append(target)
        if target in ['webgl', 'webgpu'] and 'chrome' not in build_targets:
            build_targets.append('chrome')
        cmd = f'autoninja {" ".join(build_targets)} -C {self.out_dir}'
        Util.info(cmd)
        os.system(cmd)

    def backup(self, targets, backup_inplace=False, backup_symbol=False):
        if ('webgl' in targets or 'webgpu' in targets) and 'chrome' not in targets:
            targets.append('chrome')

        if self.project == "chromium":
            rev = self.repo.get_working_dir_rev()
            rev_dir = Util.cal_backup_dir(rev)
        else:
            rev_dir = Util.cal_backup_dir()
        backup_path = f"{self.project_backup_dir}/{rev_dir}"
        Util.ensure_dir(self.project_backup_dir)

        Util.info("Begin to backup %s" % rev_dir)
        if os.path.exists(backup_path) and not backup_inplace:
            Util.info('Backup folder "%s" alreadys exists' % backup_path)
            os.rename(backup_path, f"{backup_path}-{Util.get_datetime()}")

        tmp_files = []
        for target in targets:
            backup_target = target
            if backup_target in self.BACKUP_TARGET_DICT.keys():
                backup_target = self.BACKUP_TARGET_DICT[backup_target]

            if target.startswith("angle"):
                backup_target = f"//src/tests:{backup_target}"
            elif target.startswith("dawn"):
                if self.project == "chromium":
                    backup_target = f"//third_party/dawn/src/dawn/tests:{backup_target}"
                else:
                    backup_target = f"//src/dawn/tests:{backup_target}"

            target_files = (
                self._execute(
                    f"gn desc {self.out_dir} {backup_target} runtime_deps",
                    exit_on_error=self.exit_on_error,
                    return_out=True,
                )[1]
                .rstrip("\n")
                .split("\n")
            )
            if target_files[0].startswith("WARNING"):
                target_files = target_files[1:]
            tmp_files = Util.union_list(tmp_files, target_files)

        exclude_files = []
        if 'angle' in targets:
            exclude_files.extend(
                [
                    "gen/third_party/devtools-frontend/src/front_end",
                    "gen/third_party/devtools-frontend/src/inspector_overlay",
                    "pyproto/google/protobuf",
                    "locales",
                    'bin',
                    'dbgcore.dll',
                    'dbghelp.dll',
                    'libGLESv2_vulkan_secondaries.dll',
                    '../../.vpython3',
                    '../../build',
                    '../../testing',
                    '../../src/tests/py_utils',
                    '../../infra',
                    # swiftshader specific
                    'vk_swiftshader.dll',
                    'vk_swiftshader_icd.json',
                    # vulkan specific
                ]
            )

        if 'chrome' in targets:
            exclude_files.extend(
                [
                    "locales",
                    "gen/third_party/devtools-frontend/src/front_end",
                    "gen/third_party/devtools-frontend/src/inspector_overlay",
                    "obj/",
                    "pyproto/google/protobuf",
                    "../../testing/test_env.py",
                    "../../testing/location_tags.json",
                ]
            )

        if 'dawn' in targets:
            exclude_files.extend(
                [
                    "../..",
                    "bin/",
                    "vk",
                    "vulkan",
                    "Vk",
                    "dbg",
                    "libEGL",
                    "libGLESv2",
                    "d3dcompiler_47.dll",
                ]
            )

        if 'webgl' in targets or 'webgpu' in targets:
            exclude_files.extend(
                [
                    "gen/third_party/dawn/third_party/webgpu-cts",
                    "gen/third_party/dawn/webgpu-cts",
                ]
            )

        src_files = []
        for tmp_file in tmp_files:
            tmp_file = tmp_file.rstrip("\r")
            if not backup_symbol and tmp_file.endswith(".pdb"):
                continue

            if tmp_file.startswith("./"):
                tmp_file = tmp_file[2:]

            if self.target_os == Util.CHROMEOS and not tmp_file.startswith("../../"):
                continue

            for exclude_file in exclude_files:
                if re.match(exclude_file, tmp_file):
                    break
            else:
                src_files.append(f"{self.out_dir}/{tmp_file}")

        # Add extra files
        src_files += [
            # f"{self.out_dir}/args.gn",
        ]

        if "angle" in targets:
            src_files += [
                # f"{self.out_dir}/../../infra/specs/angle.json",
            ]

        if "chrome" in targets:
            src_files += [
                f"{self.out_dir}/locales/*.pak",
                f"{self.out_dir}/gen/third_party/devtools-frontend/src/front_end",
                f"{self.out_dir}/gen/third_party/devtools-frontend/src/inspector_overlay",
                f"{self.out_dir}/pyproto/google/protobuf",
            ]

            # if Util.HOST_OS == Util.WINDOWS:
            #    src_files += [
            #        "infra/config/generated/builders/try/dawn-win10-x64-deps-rel/targets/chromium.dawn.json",
            #        "infra/config/generated/builders/try/gpu-fyi-try-win10-intel-rel-64/targets/chromium.gpu.fyi.json",
            #    ]
            # elif Util.HOST_OS == Util.LINUX:
            #    src_files += [
            #        "infra/config/generated/builders/try/dawn-linux-x64-deps-rel/targets/chromium.dawn.json",
            #        "infra/config/generated/builders/try/gpu-fyi-try-linux-intel-rel/targets/chromium.gpu.fyi.json",
            #    ]

        if 'webgpu' in targets:
            src_files += [
                f"{self.out_dir}/gen/third_party/dawn/third_party/webgpu-cts/",
                f"{self.out_dir}/gen/third_party/dawn/webgpu-cts",
            ]

        # handle src_files with glob patterns
        expanded_src_files = []
        for src_file in src_files:
            if '*' in src_file or '?' in src_file:
                # Handle glob patterns
                import glob

                matched_files = glob.glob(src_file)
                if matched_files:
                    expanded_src_files.extend(matched_files)
                else:
                    # If no matches found, keep the original pattern (will be handled as missing file)
                    expanded_src_files.append(src_file)
            else:
                # Regular file path, no glob pattern
                expanded_src_files.append(src_file)

        src_files = expanded_src_files
        # print(src_files)
        # exit(0)

        src_file_count = len(src_files)
        for index, src_file in enumerate(src_files):
            dst_file = f"{backup_path}/{src_file}"

            # dst_file can be subfolder of another dst_file, so only file can be skipped
            if backup_inplace and os.path.isfile(dst_file):
                Util.info(f"[{index + 1}/{src_file_count}] skip {dst_file}")
                continue

            Util.ensure_dir(os.path.dirname(dst_file))
            Util.info(f"[{index + 1}/{src_file_count}] {src_file}")

            try:
                if os.path.isdir(src_file):
                    # For directories, use copytree with proper symlink handling
                    shutil.copytree(
                        src_file, dst_file, dirs_exist_ok=True, symlinks=False, ignore_dangling_symlinks=True
                    )
                else:
                    # For all files, use copy2 to preserve metadata and permissions
                    shutil.copy2(src_file, dst_file)

                    # Apply Chrome LPAC sandbox permissions for Windows executables
                    if Util.HOST_OS == Util.WINDOWS and src_file.endswith('.exe'):
                        self._apply_chrome_sandbox_permissions(dst_file)

            except (OSError, IOError, PermissionError, FileNotFoundError, shutil.Error) as e:
                Util.warning(f"Failed to copy [{src_file}] to [{dst_file}]: {e}")

        # Postprocess the backup
        if self.project == 'dawn':
            shutil.copytree(
                f'{backup_path}/{self.out_dir}',
                backup_path,
                dirs_exist_ok=True,
                symlinks=False,
                ignore_dangling_symlinks=True,
            )
            shutil.rmtree(f'{backup_path}/out')

    def run(self, target, combos, rev, run_dry=False, run_filter="all", validation='disabled', jobs=1, warp=None, index=0):
        if rev not in ["out", "backup"]:
            Util.impossible()

        # Copy WARP DLL if specified, or remove it if not
        if warp in ['old', 'new']:
            self._copy_warp_dll(warp)
        else:
            self._remove_warp_dll()

        if rev == "out":
            project_rev_dir = self.repo_dir
        else:
            project_rev_name, _ = Util.get_backup_dir(self.project_backup_dir, "latest")
            project_rev_dir = f"{self.project_backup_dir}/{project_rev_name}"
            # TestExpectation.update("webgpu_cts_tests", target_rev_dir)

        if target == "webgl":
            if Util.HOST_OS == Util.WINDOWS:
                all_combos = ["1.0.4", "2.0.1"]
            elif Util.HOST_OS in [Util.LINUX, Util.DARWIN]:
                all_combos = ["2.0.1"]
        elif target == "webgpu":
            all_combos = ["d3d12", "d3d11"]
        elif target == 'angle':
            all_combos = ["d3d11"]
        elif target == 'dawn':
            all_combos = ["d3d12", "d3d11", "vulkan"]
        elif target in ['context_lost', "webcodecs", 'pixel', 'trace']:
            all_combos = ["d3d11"]

        if combos == []:
            combos = [i for i in range(len(all_combos))]

        for idx in combos:
            combo = all_combos[idx]
            # Prepare the cmd
            run_args = ""
            if target in ['angle', 'dawn']:
                if run_dry:
                    if target == 'angle':
                        run_args = "--gtest_filter=*AlphaFuncTest*D3D11*"
                    elif target == 'dawn':
                        run_args = "--gtest_filter=*BindGroupTests*"
                elif run_filter != "all":
                    run_args = f"--gtest_filter=*{run_filter}*"
                elif Util.HOST_OS == Util.WINDOWS:
                    if target == 'angle':
                        run_args = "--gtest_filter=*/*D3D11*"

                if target == "angle":
                    run_args += " --test-launcher-bot-mode"

                if target == 'dawn':
                    result_file = f"{self.result_dir}/{target}-{combo}-{index}.json"
                    run_args += f" --gtest_output=json:{result_file} --enable-backend-validation={validation} --backend={combo} --exclusive-device-type-preference=discrete,integrated"

                    _, _, _, device_id, _ = Util.get_gpu_info()
                    # 0C36: Qualcomm 8380
                    if device_id in ['0C36']:
                        run_args += " --test-launcher-bot-mode"

                    # cmd += ' --run-suppressed-tests'
                    # for output, Chrome build uses --gtest_output=json:%s, standalone build uses --test-launcher-summary-output=%s

                if target in self.BUILD_TARGET_DICT.keys():
                    cmd = self.BUILD_TARGET_DICT[target]
                else:
                    cmd = target

                if run_args:
                    cmd += f' {run_args}'

            elif target in ["webgl", "webgpu", "context_lost", "webcodecs", "pixel", "trace"]:
                # Locally update related conformance_expectations.txt
                # if combo == "1.0.4":
                #    TestExpectation.update("webgl_cts_tests", target_rev_dir)
                # elif combo == "2.0.1":
                #    TestExpectation.update("webgl2_cts_tests", target_rev_dir)

                run_args = f"--browser=release_{self.target_cpu}"

                if run_dry:
                    # run_args += ' --test-filter=*copy-texture-image-same-texture*::*ext-texture-norm16*'
                    if target == "webgl":
                        run_args += " --test-filter=*conformance/attribs*"
                    elif target == "webgpu":
                        run_args += " --test-filter=*webgpu:api,operation,render_pipeline,pipeline_output_targets:color,attachments:*"
                elif run_filter != "all":
                    escaped_filter = run_filter.replace('"', '\\"')
                    run_args += f" --test-filter=*{escaped_filter}*"

                # if self.run_verbose:
                #    run_args += " --verbose"

                if target == "context_lost":
                    jobs = 1
                run_args += f" --jobs={jobs} --stable-jobs"
                cmd = "vpython3.bat content/test/gpu/run_gpu_integration_test.py"
                if target == "webgl":
                    cmd += f" webgl{combo[0]}_conformance --webgl-conformance-version={combo}"
                elif target == "webgpu":
                    if combo == "d3d11":
                        cmd += f" webgpu_compat_cts"
                    else:
                        cmd += f" webgpu_cts"
                    cmd += f" --retry-limit 1"
                elif target in ["context_lost", "webcodecs", "pixel"]:
                    cmd += f" {target}"
                elif target in ["trace"]:
                    cmd += f" {target}_test"
                cmd += f" {run_args}"
                result_file = ""

                extra_browser_args = "--disable-backgrounding-occluded-windows --force_high_performance_gpu"
                #if target == "webgl":
                #    extra_browser_args += " --use-cmd-decoder=passthrough --use-gl=angle --use-angle=d3d11"
                if target == "webgpu" and combo == "d3d11":
                    extra_browser_args += (
                        " --enable-unsafe-webgpu --use-webgpu-adapter=d3d11 --enable-features=WebGPUCompatibilityMode"
                    )
                elif target == "context_lost":
                    extra_browser_args += " --js-flags=--expose-gc --use-cmd-decoder=passthrough --use-gl=angle"
                elif target == "webcodecs":
                    extra_browser_args += " --js-flags=--expose-gc"
                elif target == "pixel":
                    extra_browser_args += " --js-flags=--expose-gc --use-cmd-decoder=passthrough --use-gl=angle"
                elif target == "trace":
                    extra_browser_args += " --js-flags=--expose-gc"

                result_file = f"{self.result_dir}/{target}-{combo}-{index}.log"

                if warp and target == 'webgl':
                    #extra_browser_args += " --use-angle=d3d11-warp"
                    extra_browser_args += " --enable-features=AllowD3D11WarpFallback --disable-gpu"
                    #extra_browser_args += " --ignore-gpu-blocklist"
                cmd += f' --extra-browser-args="{extra_browser_args}"'
                cmd += f" --write-full-results-to {result_file}"

            # Run a combo
            if target in ["angle"]:
                run_dir = f"{project_rev_dir}/{self.out_dir}"
            elif target in ["dawn"]:
                if rev == "out":
                    run_dir = f"{project_rev_dir}/{self.out_dir}"
                else:
                    run_dir = project_rev_dir
            else:
                run_dir = project_rev_dir
            Util.chdir(run_dir, verbose=True)

            timer = Timer()
            Util.info(cmd)
            os.system(cmd)
            Util.append_file(self.run_log, f"{target}-{combo} run{self.SEPARATOR}{timer.stop()}")

            # Postprocess the result
            if target == "angle":
                if rev == "out":
                    output_file = f"{self.repo_dir}/out/release_{self.target_cpu}/output.json"
                    # TestExpectation.update('angle_end2end_tests', f'{self.repo_dir}')
                else:
                    output_file = (
                        f"{self.project_backup_dir}/{project_rev_name}/out/release_{self.target_cpu}/output.json"
                    )
                    # TestExpectation.update("angle_end2end_tests", f"{self.repo_dir}/backup/{project_rev_dir}")

                result_file = f"{self.result_dir}/{target}-{combo}-{index}.json"
                if os.path.exists(output_file):
                    shutil.move(output_file, result_file)
                else:
                    Util.ensure_file(result_file)

            if rev == "out":
                if self.project == "chromium":
                    repo_rev = self.repo.get_working_dir_rev()
                else:
                    repo_rev = 0
                Util.append_file(self.run_log, f"{target} rev{self.SEPARATOR}out ({Util.cal_backup_dir(repo_rev)})")
            else:
                Util.append_file(self.run_log, f"{target} rev{self.SEPARATOR}backup ({project_rev_name})")

            if os.path.exists(self.root_dir):
                Util.chdir(self.root_dir)

    def upload(self):  # pylint: disable=unused-argument
        """
        Upload the latest backup to the remote server.
        Finds the latest version in backup directory and uploads it if not already present on server.

        Args:
            target: The target type (angle, dawn, chrome, etc.) - currently unused but kept for API compatibility
            rev: The revision (typically 'latest' to get the most recent backup) - currently unused but kept for API compatibility
        """
        # Only support Windows
        if Util.HOST_OS != Util.WINDOWS:
            Util.warning(f"Upload function only supports Windows, current OS: {Util.HOST_OS}")
            return

        # Get the latest backup directory name
        if not os.path.exists(self.project_backup_dir):
            Util.warning(f"Backup directory {self.project_backup_dir} does not exist")
            return

        try:
            rev_name, _ = Util.get_backup_dir(self.project_backup_dir, 'latest')
        except (ValueError, IndexError, OSError) as e:
            Util.warning(f"No backup found in {self.project_backup_dir}: {e}")
            return

        if not rev_name:
            Util.warning(f"No valid backup found in {self.project_backup_dir}")
            return

        Util.info(f"Found latest backup: {rev_name}")

        # Create archive file name for Windows (.zip)
        archive_file = f"{rev_name}.zip"

        # Check if backup already exists on shared folder
        server_archive_path = f"{self.server_backup_dir}\\{archive_file}"

        Util.info(f"Checking server path: {server_archive_path}")

        if os.path.exists(server_archive_path):
            Util.info(f"Backup {archive_file} already exists on server")
            return

        # Create archive if it doesn't exist locally
        local_backup_path = f"{self.project_backup_dir}/{rev_name}"
        local_archive_path = f"{self.project_backup_dir}/{archive_file}"

        if not os.path.exists(local_archive_path):
            Util.info(f"Creating archive: {archive_file}")

            if not os.path.exists(local_backup_path):
                Util.error(f"Backup directory {local_backup_path} does not exist")
                return

            # Change to backup directory to create relative paths in archive
            original_dir = os.getcwd()
            Util.chdir(self.project_backup_dir)

            try:
                # Create zip archive
                # Use local import to avoid conflict with zipfile import at module level
                import zipfile as zf

                with zf.ZipFile(local_archive_path, 'w', zf.ZIP_DEFLATED) as zipf:
                    for root, _, files in os.walk(rev_name):
                        for file in files:
                            file_path = os.path.join(root, file)
                            archive_path = os.path.relpath(file_path, '.')
                            zipf.write(file_path, archive_path)
                Util.info(f"Created zip archive: {archive_file}")

            finally:
                Util.chdir(original_dir)
        else:
            Util.info(f"Archive already exists locally: {archive_file}")

        # Upload to server via shared folder
        if os.path.exists(local_archive_path):
            Util.info(f"Uploading {archive_file} to server...")

            # Ensure remote directory exists
            Util.ensure_dir(self.server_backup_dir)

            # Copy the archive to shared folder
            try:
                shutil.copy2(local_archive_path, server_archive_path)
                Util.info(f"Successfully uploaded {archive_file} to server")
            except (OSError, IOError, PermissionError) as e:
                Util.error(f"Failed to upload {archive_file} to server: {e}")
        else:
            Util.error(f"Archive file {local_archive_path} does not exist")

    def download(self):  # pylint: disable=unused-argument
        """
        Download the latest backup from the remote server.
        Finds the latest version on server and downloads it if not already present locally.
        """
        # Only support Windows
        if Util.HOST_OS != Util.WINDOWS:
            Util.warning(f"Download function only supports Windows, current OS: {Util.HOST_OS}")
            return

        # Get server backup directory
        if not os.path.exists(self.server_backup_dir):
            Util.warning(f"Server backup directory does not exist: {self.server_backup_dir}")
            return

        Util.info(f"Checking server directory: {self.server_backup_dir}")

        # Find the latest backup on server
        try:
            server_files = os.listdir(self.server_backup_dir)
            zip_files = [f for f in server_files if f.endswith('.zip')]

            if not zip_files:
                Util.warning(f"No backup files found on server in {self.server_backup_dir}")
                return

            # Extract revision names and find the latest
            latest_rev = -1
            latest_file = None

            for zip_file in zip_files:
                # Remove .zip extension to get revision name
                rev_name = zip_file[:-4]
                # Extract revision number using the backup pattern
                match = re.search(Util.BACKUP_PATTERN, rev_name)
                if match:
                    rev_num = int(match.group(2))
                    if rev_num > latest_rev:
                        latest_rev = rev_num
                        latest_file = zip_file

            if not latest_file:
                Util.warning("No valid backup files found on server")
                return

            Util.info(f"Found latest backup on server: {latest_file}")

        except (OSError, PermissionError) as e:
            Util.error(f"Failed to access server directory {self.server_backup_dir}: {e}")
            return

        # Check if backup already exists locally
        rev_name = latest_file[:-4]  # Remove .zip extension
        local_backup_path = f"{self.project_backup_dir}/{rev_name}"
        local_archive_path = f"{self.project_backup_dir}/{latest_file}"
        server_archive_path = f"{self.server_backup_dir}\\{latest_file}"

        # Check if we already have this backup locally (either extracted or as archive)
        if os.path.exists(local_backup_path):
            Util.info(f"Backup {rev_name} already exists locally (extracted)")
            return

        if os.path.exists(local_archive_path):
            Util.info(f"Backup archive {latest_file} already exists locally")
            # Extract if directory doesn't exist
            if not os.path.exists(local_backup_path):
                Util.info(f"Extracting existing archive: {latest_file}")
                self._extract_backup_archive(local_archive_path, rev_name)
            return

        # Download the backup
        Util.info(f"Downloading {latest_file} from server...")

        # Ensure local backup directory exists
        Util.ensure_dir(self.project_backup_dir)

        try:
            # Copy the archive from shared folder
            shutil.copy2(server_archive_path, local_archive_path)
            Util.info(f"Successfully downloaded {latest_file} from server")

            # Extract the archive
            Util.info(f"Extracting archive: {latest_file}")
            self._extract_backup_archive(local_archive_path, rev_name)

        except (OSError, IOError, PermissionError) as e:
            Util.error(f"Failed to download {latest_file} from server: {e}")

    def _extract_backup_archive(self, archive_path, rev_name):
        """
        Extract a backup archive to the backup directory.

        Args:
            archive_path: Path to the archive file
            rev_name: Name of the revision directory to extract to
        """
        if not os.path.exists(archive_path):
            Util.error(f"Archive file does not exist: {archive_path}")
            return

        extract_path = f"{self.project_backup_dir}/{rev_name}"

        # Change to backup directory for extraction
        original_dir = os.getcwd()
        Util.chdir(self.project_backup_dir)

        try:
            # Extract zip archive
            import zipfile as zf

            with zf.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall('.')
            Util.info(f"Successfully extracted archive to: {extract_path}")

        except (zf.BadZipFile, OSError, IOError) as e:
            Util.error(f"Failed to extract archive {archive_path}: {e}")
        finally:
            Util.chdir(original_dir)

    def _copy_warp_dll(self, warp):
        """
        Copy WARP DLL from warp/ folder to the output directory.
        """
        warp_dll = 'd3d10warp.dll'
        script_dir = os.path.dirname(os.path.abspath(__file__))
        warp_src_dir = f'{script_dir}/warp/{warp}'
        src = f'{warp_src_dir}/{warp_dll}'
        dst = f'{self.repo_dir}/{self.out_dir}/{warp_dll}'

        if not os.path.exists(src):
            Util.error(f'WARP DLL not found: {src}')
            return

        Util.info(f'Copying {warp} WARP DLL from {src} to {dst}')
        shutil.copy2(src, dst)

    def _remove_warp_dll(self):
        """
        Remove WARP DLL from the output directory if it exists.
        """
        warp_dll = 'd3d10warp.dll'
        dst = f'{self.repo_dir}/{self.out_dir}/{warp_dll}'

        if os.path.exists(dst):
            Util.info(f'Removing WARP DLL: {dst}')
            os.remove(dst)

    def _apply_chrome_sandbox_permissions(self, exe_path):
        """
        Apply Chrome LPAC sandbox permissions to an executable.

        Args:
            exe_path: Path to the executable to fix
        """
        import subprocess

        filename = os.path.basename(exe_path)
        # Util.info(f"Applying Chrome sandbox permissions: {filename}")

        try:
            # Take ownership and reset permissions
            ownership_cmds = [
                f'takeown /f "{exe_path}" /a',
                f'icacls "{exe_path}" /reset /q',
                f'icacls "{exe_path}" /inheritance:r /q',
            ]

            for cmd in ownership_cmds:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)

            # Apply standard permissions
            standard_permissions = [
                f'icacls "{exe_path}" /grant "NT AUTHORITY\\SYSTEM:(F)" /q',
                f'icacls "{exe_path}" /grant "BUILTIN\\Administrators:(F)" /q',
                f'icacls "{exe_path}" /grant "BUILTIN\\Users:(RX)" /q',
                f'icacls "{exe_path}" /grant "NT AUTHORITY\\Authenticated Users:(RX)" /q',
            ]

            success_count = 0
            for cmd in standard_permissions:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    success_count += 1

            # Apply LPAC permissions (try alternatives in order of known compatibility)
            lpac_alternatives = [
                f'icacls "{exe_path}" /grant "ALL APPLICATION PACKAGES:(RX)" /q',
                f'icacls "{exe_path}" /grant "*S-1-15-2-1:(RX)" /q',
                f'icacls "{exe_path}" /grant "*S-1-15-2-2:(RX)" /q',
            ]

            lpac_success = False
            for lpac_cmd in lpac_alternatives:
                result = subprocess.run(lpac_cmd, shell=True, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    lpac_success = True
                    # permission_name = lpac_cmd.split('grant')[1].split(':(')[0].strip().replace('"', '')
                    # Util.info(f"✓ LPAC permission applied: {permission_name}")
                    break

            # Set integrity level and clean up attributes
            cleanup_cmds = [
                f'icacls "{exe_path}" /setintegritylevel medium /q',
                f'attrib -r -h -s -a "{exe_path}"',
            ]

            for cmd in cleanup_cmds:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)

            if lpac_success:
                file_size = os.path.getsize(exe_path)
                # Util.info(f"✓ Sandbox-compatible executable ready: {filename} ({file_size:,} bytes)")
                pass
            else:
                Util.warning(f"⚠ LPAC permissions failed for: {filename}")

        except (OSError, subprocess.SubprocessError, FileNotFoundError) as e:
            Util.error(f"Sandbox permission fix failed for {filename}: {e}")
