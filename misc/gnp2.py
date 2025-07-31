import os
import platform
import re
import subprocess
import sys

from util.base import *  # pylint: disable=unused-wildcard-import


class Gnp2(Program):
    BUILD_TARGET_DICT = {
        "angle": "angle_end2end_tests",
        "angle_perf": "angle_perftests",
        "angle_unit": "angle_unittests",
        "dawn": "dawn_end2end_tests",
        # For chrome drop
        "webgl": "chrome/test:telemetry_gpu_integration_test",
        "webgpu": "chrome/test:telemetry_gpu_integration_test",
    }
    BACKUP_TARGET_DICT = {
        "angle": "angle_end2end_tests",
        "angle_perf": "angle_perftests",
        "angle_unit": "angle_unittests",
        "dawn": "dawn_end2end_tests",
        "chrome": "//chrome:chrome",
        "chromedriver": "//chrome/test/chromedriver:chromedriver",
        "gl_tests": "//gpu:gl_tests",
        "vulkan_tests": "//gpu/vulkan:vulkan_tests",
        "telemetry_gpu_integration_test": "//chrome/test:telemetry_gpu_integration_test",
        "webgpu_blink_web_tests": "//:webgpu_blink_web_tests",
        # For chrome drop
        "webgl": "//chrome/test:telemetry_gpu_integration_test",
        "webgpu": "//chrome/test:telemetry_gpu_integration_test",
    }

    def __init__(self, root_dir, is_debug=False, symbol_level=-1):
        super().__init__()

        project = os.path.basename(root_dir)
        # handle repo chromium
        if project == "src":
            project = os.path.basename(os.path.dirname(root_dir))
        if "chromium" in project or "chrome" in project or "cr" in project or "edge" in project:
            project = "chromium"
        self.project = project

        if project == "chromium":
            self.repo = ChromiumRepo(root_dir)
            self.backup_dir = "%s/backup" % os.path.dirname(root_dir)
        else:
            self.backup_dir = "%s/backup" % root_dir

        if is_debug:
            build_type = "debug"
        else:
            build_type = "release"
        self.build_type = build_type

        if symbol_level == -1:
            if is_debug:
                symbol_level = 2
            else:
                symbol_level = 0
        self.symbol_level = symbol_level

        self.out_dir = f"out/{self.build_type}_{self.target_cpu}"

        if self.project == "angle":
            default_target = "angle"
        elif self.project == "chromium":
            if self.target_os == "android":
                default_target = "chrome_public_apk"
            else:
                default_target = "chrome"
        elif self.project == "dawn":
            default_target = "dawn"
        else:
            default_target = ""
        self.default_target = default_target

        self.exit_on_error = False
        self.root_dir = root_dir
        if project == "chromium":
            Util.chdir(f"{root_dir}/src")
        else:
            Util.chdir(root_dir)

    def sync(self):
        self._execute("git pull --no-recurse-submodules", exit_on_error=self.exit_on_error)
        self._execute_gclient(cmd_type="sync")

    def makefile(
        self,
        is_debug=False,
        dcheck=True,
        is_component_build=False,
        treat_warning_as_error=True,
        disable_official_build=False,
        vulkan_only=False,
        target_os=Util.HOST_OS,
    ):
        Util.print_cwd()
        if self.project == 'chromium':
            cmd = f'autogn {self.target_cpu} {self.build_type} --use-remoteexec -a {self.root_dir.replace('\\src', '').replace('\\', '/')}'
            print(cmd)
            self._execute(f'{cmd}', exit_on_error=self.exit_on_error)
            return

        gn_args = "use_remoteexec=true"
        if is_debug:
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

        gn_args += f" symbol_level={self.symbol_level}"

        if self.project == "chromium":
            if self.symbol_level == 0:
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
            gn_args += " dawn_use_swiftshader=false dawn_enable_vulkan=false"
            # Below gn args couldn't be set
            # gn_args += ' dawn_supports_glfw_for_windowing=false dawn_use_glfw=false dawn_use_windows_ui=false tint_build_cmd_tools=false tint_build_tests=false'

        cmd = f'gn gen {self.out_dir} --args="{gn_args}"'
        Util.info(cmd)
        os.system(cmd)

    def build(self, target=None):
        if self.project == 'angle':
            cmd = f'autoninja angle_end2end_tests -C {self.out_dir}'
        elif self.project == "chromium":
            # cmd = f'autoninja chrome chrome/test:telemetry_gpu_integration_test -C {self.out_dir}'
            cmd = f'cd {self.out_dir} && autoninja chrome chrome/test:telemetry_gpu_integration_test'
        elif self.project == "dawn":
            cmd = f'autoninja dawn_end2end_tests -C {self.out_dir}'
        os.system(cmd)

    def backup(self, target, backup_inplace=False, backup_symbol=False):
        if self.project == "chromium":
            rev = self.repo.get_working_dir_rev()
            rev_dir = Util.cal_backup_dir(rev)
        else:
            rev_dir = Util.cal_backup_dir()
        backup_path = f"{self.backup_dir}/{rev_dir}"
        Util.ensure_dir(self.backup_dir)

        Util.info("Begin to backup %s" % rev_dir)
        if os.path.exists(backup_path) and not backup_inplace:
            Util.info('Backup folder "%s" alreadys exists' % backup_path)
            os.rename(backup_path, "%s-%s" % (backup_path, Util.get_datetime()))

        if target:
            targets = target.split(",")
        else:
            targets = [self.default_target]

        for key, value in self.BACKUP_TARGET_DICT.items():
            if key in targets:
                targets[targets.index(key)] = value

        for index, target in enumerate(targets):
            if target.startswith("angle"):
                targets[index] = "//src/tests:%s" % target
            elif target.startswith("dawn"):
                if self.project == "chromium":
                    targets[index] = "//third_party/dawn/src/dawn/tests:%s" % target
                else:
                    targets[index] = "//src/dawn/tests:%s" % target

        if "webgpu-cts" in targets:
            # Util.chdir(self.root_dir + '/third_party/webgpu-cts/src')
            # Util.execute('npm install && npm run standalone')
            targets.remove("webgpu-cts")
            Util.ensure_dir(f"{backup_path}/gen/third_party/dawn/third_party/webgpu-cts/src")
            Util.ensure_dir(f"{backup_path}/gen/third_party/dawn/third_party/webgpu-cts/resources")
            Util.copy_files(
                f"{self.root_dir}/third_party/webgpu-cts/src/out",
                f"{backup_path}/gen/third_party/dawn/third_party/webgpu-cts/src",
            )

            Util.ensure_nodir(f"{backup_path}/gen/third_party/dawn/third_party/webgpu-cts/src/resources")

            Util.copy_files(
                f"{self.root_dir}/third_party/webgpu-cts/src/src/resources",
                f"{backup_path}/gen/third_party/dawn/third_party/webgpu-cts/resources",
            )

            Util.ensure_dir(f"{backup_path}/gen/third_party/dawn/webgpu-cts")
            Util.copy_file(
                f"{self.root_dir}/third_party/dawn/webgpu-cts",
                "test_page.html",
                f"{backup_path}/gen/third_party/dawn/webgpu-cts",
                need_bk=False,
            )
            Util.copy_file(
                f"{self.root_dir}/third_party/dawn/webgpu-cts",
                "test_runner.js",
                f"{backup_path}/gen/third_party/dawn/webgpu-cts",
                need_bk=False,
            )

        tmp_files = []
        for target in targets:
            target_files = (
                self._execute(
                    f"gn desc {self.out_dir} {target} runtime_deps",
                    exit_on_error=self.exit_on_error,
                    return_out=True,
                )[1]
                .rstrip("\n")
                .split("\n")
            )
            tmp_files = Util.union_list(tmp_files, target_files)

        # 'gen/', 'obj/', '../../testing/test_env.py', '../../testing/location_tags.json', '../../.vpython'
        exclude_files = []
        if self.project == 'dawn':
            # Even if we don't build them, they still show up from gn desc. So we need to remove them manually.
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
                    "d3dcompiler_47",
                ]
            )
        elif target == "webgl":
            pass
        elif target == "webgpu":
            exclude_files.extend(
                [
                    "gen/",
                    "obj/",
                    "../../testing/test_env.py",
                    "../../testing/location_tags.json",
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
                src_files.append("%s/%s" % (self.out_dir, tmp_file))

        if self.project == "angle":
            src_files += [
                f"{self.out_dir}/args.gn",
                f"{self.out_dir}/../../infra/specs/angle.json",
            ]
        elif self.project == "chromium" and "webgpu-cts" not in backup_target.split(","):
            src_files += [f"{self.out_dir}/args.gn"]
            if Util.HOST_OS == Util.WINDOWS:
                src_files += [
                    "infra/config/generated/builders/try/dawn-win10-x64-deps-rel/targets/chromium.dawn.json",
                    "infra/config/generated/builders/try/gpu-fyi-try-win10-intel-rel-64/targets/chromium.gpu.fyi.json",
                ]
            elif Util.HOST_OS == Util.LINUX:
                src_files += [
                    "infra/config/generated/builders/try/dawn-linux-x64-deps-rel/targets/chromium.dawn.json",
                    "infra/config/generated/builders/try/gpu-fyi-try-linux-intel-rel/targets/chromium.gpu.fyi.json",
                ]

        src_file_count = len(src_files)
        for index, src_file in enumerate(src_files):
            dst_file = "%s/%s" % (backup_path, src_file)
            # dst_file can be subfolder of another dst_file, so only file can be skipped
            if backup_inplace and os.path.isfile(dst_file):
                Util.info(f"[{index + 1}/{src_file_count}] skip {dst_file}")
                continue
            Util.ensure_dir(os.path.dirname(dst_file))
            if os.path.isdir(src_file):
                dst_file = os.path.dirname(dst_file.rstrip("/"))
            cmd = "cp -rf %s %s" % (src_file, dst_file)
            Util.info("[%s/%s] %s" % (index + 1, src_file_count, cmd))
            self._execute(cmd, exit_on_error=False, show_cmd=False)

            # permission denied
            # shutil.copyfile(file, dst_dir)

        if self.project == 'dawn':
            Util.chdir(backup_path)
            Util.copy_files(self.out_dir, ".")
            shutil.rmtree("out")
            Util.chdir(self.root_dir, verbose=True)

    def run(self, target, rev, result_file=None, backend=None, filter="all", run_dry=False, validation='disabled'):
        if target == 'angle':
            run_args = ""
            if run_dry:
                run_args = "--gtest_filter=*AlphaFuncTest*"
            elif filter != "all":
                run_args = f"--gtest_filter=*{filter}*"
            elif Util.HOST_OS == Util.WINDOWS:
                run_args = "--gtest_filter=*D3D11*"
            else:
                run_args = ""

        elif target == 'dawn':
            run_args = f" --gtest_output=json:{result_file}"
            if run_dry:
                run_args += " --gtest_filter=*BindGroupTests*"
            elif filter != "all":
                run_args += f" --gtest_filter=*{filter}*"
            run_args += f" --enable-backend-validation={validation}"
            run_args += f" --backend={backend}"

        if rev == "out":
            run_dir = self.out_dir
        else:
            rev_name, _ = Util.get_backup_dir("backup", "latest")
            if target == "dawn":
                run_dir = f"backup/{rev_name}"
            else:
                run_dir = f"backup/{rev_name}/{self.out_dir}"

        Util.chdir(run_dir, verbose=True)
        if target:
            targets = target.split(",")
        else:
            targets = [self.default_target]

        for key, value in self.BUILD_TARGET_DICT.items():
            if key in targets:
                targets[targets.index(key)] = value

        for target in targets:
            self._run(target, run_args)

        Util.chdir(self.root_dir, verbose=True)

    def _execute_gclient(self, cmd_type, verbose=False):
        cmd = f"gclient {cmd_type} -j{Util.CPU_COUNT}"
        if verbose:
            cmd += " -v"
        self._execute(cmd=cmd, exit_on_error=self.exit_on_error)

    def _run(self, target, run_args):
        if target == "telemetry_gpu_integration_test":
            cmd = f"vpython3.bat ../../content/test/gpu/run_gpu_integration_test.py"
        elif target == "webgpu_blink_web_tests":
            cmd = "bin/run_webgpu_blink_web_tests"
            if Util.HOST_OS == Util.WINDOWS:
                cmd += ".bat"
                # Workaround for content shell crash on Windows when building webgpu_blink_web_tests with is_official_build which is configured in makefile().
                # cmd += ' --additional-driver-flag=--disable-gpu-sandbox'
        else:
            cmd = "%s/%s%s" % (os.getcwd(), target, Util.EXEC_SUFFIX)
        if Util.HOST_OS == Util.WINDOWS:
            cmd = Util.format_slash(cmd)

        if run_args:
            cmd += f' {run_args}'

        if Util.HOST_OS == Util.LINUX:
            if target == "telemetry_gpu_integration_test":
                cmd += " --browser=exact --browser-executable=./chrome"
            if target not in [
                "telemetry_gpu_integration_test",
                "webgpu_blink_web_tests",
            ]:
                cmd = "./" + cmd

        if target in ["angle_end2end_tests", "angle_white_box_tests"]:
            if "test-launcher-bot-mode" not in cmd:
                cmd += " --test-launcher-bot-mode"

        if self.project == "dawn":
            if "exclusive-device-type-preference" not in cmd:
                cmd += " --exclusive-device-type-preference=discrete,integrated"
            if Util.HOST_OS == Util.LINUX:
                cmd += " --backend=vulkan"
            # cmd += ' --run-suppressed-tests'
            # for output, Chrome build uses --gtest_output=json:%s, standalone build uses --test-launcher-summary-output=%s

        self._execute(cmd, exit_on_error=self.exit_on_error)
