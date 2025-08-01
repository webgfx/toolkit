import os
import platform
import re
import subprocess
import sys

from util.base import *  # pylint: disable=unused-wildcard-import


class Project(Program):
    # angle == angle_e2e
    # dawn == dawn_e2e
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

    def __init__(self, root_dir, results_dir, is_debug=False):
        super().__init__()
        project = os.path.basename(root_dir)
        # handle project chromium
        if "chromium" in project or "chrome" in project or "cr" in project or "edge" in project:
            project = "chromium"
        self.project = project

        if project == "chromium":
            self.repo = ChromiumRepo(root_dir)
            self.backup_dir = f"{root_dir}/backup"
        else:
            self.backup_dir = f"{root_dir}/backup"

        if is_debug:
            build_type = "debug"
        else:
            build_type = "release"
        self.build_type = build_type

        self.is_debug = is_debug
        self.out_dir = f"out/{self.build_type}_{self.target_cpu}"
        self.exit_on_error = False
        self.root_dir = root_dir
        self.results_dir = results_dir
        self.run_log = f"{self.results_dir}/run.log"

        if project == "chromium":
            Util.chdir(f"{root_dir}/src")
        else:
            Util.chdir(root_dir)

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
    ):
        if symbol_level == -1:
            if self.is_debug:
                symbol_level = 2
            else:
                symbol_level = 0
        self.symbol_level = symbol_level

        if self.project == 'chromium':
            cmd = f'autogn {self.target_cpu} {self.build_type} --use-remoteexec -a {self.root_dir}'
            print(cmd)
            os.system(cmd)
            return

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

    def build(self):
        if self.project == 'angle':
            cmd = f'autoninja angle_end2end_tests -C {self.out_dir}'
        elif self.project == "chromium":
            cmd = f'autoninja chrome chrome/test:telemetry_gpu_integration_test -C {self.out_dir}'
        elif self.project == "dawn":
            cmd = f'autoninja dawn_end2end_tests -C {self.out_dir}'
        else:
            cmd = ''
            Util.impossible()
        os.system(cmd)

    def backup(self, targets, backup_inplace=False, backup_symbol=False):
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
                    "gen/third_party/devtools-frontend/src/front_end",
                    "gen/third_party/devtools-frontend/src/inspector_overlay",
                    "pyproto/google/protobuf",
                    "locales",
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
                    "d3dcompiler_47",
                ]
            )

        if "webgl" in targets or "webgpu" in targets:
            exclude_files.extend(
                [
                    # "gen/",
                    # "obj/",
                    "../../testing/test_env.py",
                    "../../testing/location_tags.json",
                    "gen/third_party/dawn/third_party/webgpu-cts",
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

        # print(src_files)
        # exit(0)
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
                f"{self.out_dir}/gen/third_party/devtools-frontend/src/front_end",
                f"{self.out_dir}/gen/third_party/devtools-frontend/src/inspector_overlay",
                f"{self.out_dir}/pyproto/google/protobuf",
                f"{self.out_dir}/locales/*.pak",
                # extra files
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

        if "webgl" in targets or "webgpu" in targets:
            src_files += [
                f"{self.out_dir}/gen/third_party/dawn/third_party/webgpu-cts/",
            ]

        src_file_count = len(src_files)
        for index, src_file in enumerate(src_files):
            dst_file = f"{backup_path}/{src_file}"

            # dst_file can be subfolder of another dst_file, so only file can be skipped
            if backup_inplace and os.path.isfile(dst_file):
                Util.info(f"[{index + 1}/{src_file_count}] skip {dst_file}")
                continue

            print(dst_file)
            Util.ensure_dir(os.path.dirname(dst_file))
            if os.path.isdir(src_file) or '*' in src_file:
                dst_file = os.path.dirname(dst_file.rstrip("/"))

            Util.info(f"[{index + 1}/{src_file_count}] {src_file}")
            cmd = f"cp -rf {src_file} {dst_file}"
            os.system(cmd)

            # if os.path.isdir(src_file):
            #    try:
            #        shutil.copytree(src_file, dst_file, dirs_exist_ok=True)
            #    except Exception as e:
            #        Util.warning(f"Failed to copy directory [{src_file}] to [{dst_file}]: {e}")
            # else:
            #    # shutil.copyfile(src_file, dst_file)
            #    cmd = f"cp -rf {src_file} {dst_file}"
            #    os.system(cmd)

            # permission denied
            # shutil.copyfile(file, dst_dir)

        # Postprocess the backup
        if self.project == 'dawn':
            Util.chdir(backup_path)
            Util.copy_files(self.out_dir, ".")
            shutil.rmtree("out")
            Util.chdir(self.root_dir, verbose=True)

    def run(self, target, combos, rev, run_dry=False, filter="all", validation='disabled', jobs=1):
        project_dir = self.root_dir
        project_backup_dir = f"{project_dir}/backup"
        if rev == "out":
            if target in ["angle", "dawn"]:
                project_rev_dir = project_dir
            else:
                project_rev_dir = f"{project_dir}/src"
        else:
            project_rev_name, _ = Util.get_backup_dir(project_backup_dir, "latest")
            project_rev_dir = f"{project_backup_dir}/{project_rev_name}"
            # TestExpectation.update("webgpu_cts_tests", target_rev_dir)

        if target == "webgl":
            if Util.HOST_OS == Util.WINDOWS:
                all_combos = ["1.0.3", "2.0.1"]
            elif Util.HOST_OS in [Util.LINUX, Util.DARWIN]:
                all_combos = ["2.0.1"]
        elif target == "webgpu":
            all_combos = ["d3d12"]
        elif target == 'angle':
            all_combos = ["d3d11"]
        elif target == 'dawn':
            all_combos = ["d3d12"]

        if combos == []:
            combos = [i for i in range(len(all_combos))]

        for index in combos:
            combo = all_combos[index]
            # Prepare the cmd
            run_args = ""
            if target in ['angle', 'dawn']:
                if run_dry:
                    if target == 'angle':
                        run_args = "--gtest_filter=*AlphaFuncTest*D3D11*"
                    elif target == 'dawn':
                        run_args = "--gtest_filter=*BindGroupTests*"
                elif filter != "all":
                    run_args = f"--gtest_filter=*{filter}*"
                elif Util.HOST_OS == Util.WINDOWS:
                    if target == 'angle':
                        run_args = "--gtest_filter=*D3D11*:-*SwiftShader*"

                if target == "angle":
                    run_args += " --test-launcher-bot-mode"

                if target == 'dawn':
                    result_file = f"{self.results_dir}/{target}-{combo}.json"
                    run_args += f" --gtest_output=json:{result_file} --enable-backend-validation={validation} --backend={combo} --exclusive-device-type-preference=discrete,integrated"
                    # cmd += ' --run-suppressed-tests'
                    # for output, Chrome build uses --gtest_output=json:%s, standalone build uses --test-launcher-summary-output=%s

                if target in self.BUILD_TARGET_DICT.keys():
                    cmd = self.BUILD_TARGET_DICT[target]
                else:
                    cmd = target

                if run_args:
                    cmd += f' {run_args}'

            elif target in ["webgl", "webgpu"]:
                # Locally update related conformance_expectations.txt
                # if combo == "1.0.3":
                #    TestExpectation.update("webgl_cts_tests", target_rev_dir)
                # elif combo == "2.0.1":
                #    TestExpectation.update("webgl2_cts_tests", target_rev_dir)

                run_args = "--disable-log-uploads"
                if rev in ["out", "backup"]:
                    Util.chdir(project_rev_dir, verbose=True)
                    run_args += f" --browser=release_{self.target_cpu}"
                else:
                    run_args += f" --browser={rev}"

                if run_dry:
                    # run_args += ' --test-filter=*copy-texture-image-same-texture*::*ext-texture-norm16*'
                    if target == "webgl":
                        run_args += " --test-filter=*conformance/attribs*"
                    elif target == "webgpu":
                        run_args += " --test-filter=*webgpu:api,operation,render_pipeline,pipeline_output_targets:color,attachments:*"
                elif filter != "all":
                    run_args += f" --test-filter=*{filter}*"

                # if self.run_verbose:
                #    run_args += " --verbose"

                run_args += f" --jobs={jobs}"
                cmd = "vpython3.bat content/test/gpu/run_gpu_integration_test.py"
                if target == "webgl":
                    cmd += f" webgl{combo[0]}_conformance {run_args} --webgl-conformance-version={combo}"
                elif target == "webgpu":
                    cmd += f" webgpu_cts --passthrough --stable-jobs {run_args}"
                result_file = ""
                extra_browser_args = "--disable-backgrounding-occluded-windows --js-flags=--expose-gc --force_high_performance_gpu --no-sandbox"
                if Util.HOST_OS == Util.LINUX:
                    result_file = f"{self.results_dir}/{target}-{combo}.log"
                elif Util.HOST_OS == Util.WINDOWS:
                    if target == "webgl":
                        extra_browser_args += f" --use-angle=d3d11"
                    result_file = f"{self.results_dir}/{target}-{combo}.log"
                # warp
                # extra_browser_args += " --enable-features=AllowD3D11WarpFallback --disable-gpu"
                cmd += f' --extra-browser-args="{extra_browser_args}"'
                cmd += f" --write-full-results-to {result_file}"

            # Run a combo
            if target == "angle":
                run_dir = f"{project_rev_dir}/{self.out_dir}"
            else:
                run_dir = project_rev_dir
            Util.chdir(run_dir, verbose=True)

            timer = Timer()
            Util.info(cmd)
            os.system(cmd)
            Util.append_file(self.run_log, f"{target}-{combo} run: {timer.stop()}")

            # Postprocess the result
            if target == "angle":
                if rev == "out":
                    output_file = f"{project_dir}/out/release_{self.target_cpu}/output.json"
                    # TestExpectation.update('angle_end2end_tests', f'{project_dir}')
                else:
                    output_file = f"{project_backup_dir}/{project_rev_name}/out/release_{self.target_cpu}/output.json"
                    # TestExpectation.update("angle_end2end_tests", f"{project_dir}/backup/{project_rev_dir}")

                result_file = f"{self.results_dir}/{target}-{combo}.json"
                if os.path.exists(output_file):
                    shutil.move(output_file, result_file)
                else:
                    Util.ensure_file(result_file)

            if rev == "out":
                Util.append_file(self.run_log, f"{target} rev: out")
            else:
                Util.append_file(self.run_log, f"{target} rev: {project_rev_name}")

            Util.chdir(self.root_dir, verbose=True)
