# pylint: disable=line-too-long, missing-function-docstring, missing-module-docstring, missing-class-docstring, wildcard-import, unused-wildcard-import, disable=wrong-import-position

import os
import re
import subprocess
import sys

HOST_OS = sys.platform
if HOST_OS == "win32":
    lines = subprocess.Popen(
        "dir %s" % __file__.replace("/", "\\"), shell=True, stdout=subprocess.PIPE
    ).stdout.readlines()
    for tmp_line in lines:
        match = re.search(r"\[(.*)\]", tmp_line.decode("utf-8"))
        if match:
            SCRIPT_DIR = os.path.dirname(match.group(1)).replace("\\", "/")
            break
    else:
        SCRIPT_DIR = sys.path[0]
else:
    lines = subprocess.Popen("ls -l %s" % __file__, shell=True, stdout=subprocess.PIPE).stdout.readlines()
    for tmp_line in lines:
        match = re.search(r".* -> (.*)", tmp_line.decode("utf-8"))
        if match:
            SCRIPT_DIR = os.path.dirname(match.group(1))
            break
    else:
        SCRIPT_DIR = sys.path[0]

sys.path.append(SCRIPT_DIR)
sys.path.append(SCRIPT_DIR + "/..")

from util.base import *
from misc.testhelper import *
from misc.gnp2 import Gnp2


class WebgfxTest(Program):
    SKIP_CASES = {
        # Util.LINUX: ['WebglConformance_conformance2_textures_misc_tex_3d_size_limit'],
        Util.LINUX: [],
    }
    SEPARATOR = "|"

    def __init__(self):
        parser = argparse.ArgumentParser(description="Webgfx tests")

        parser.add_argument("--target", dest="target", help="target", default="all")
        parser.add_argument("--sync", dest="sync", help="sync", action="store_true")
        parser.add_argument("--makefile", dest="makefile", help="makefile", action="store_true")
        parser.add_argument("--build", dest="build", help="build", action="store_true")

        parser.add_argument(
            "--build-skip-chrome",
            dest="build_skip_chrome",
            help="build skip chrome",
            action="store_true",
        )
        parser.add_argument("--backup", dest="backup", help="backup", action="store_true")
        parser.add_argument(
            "--backup-inplace",
            dest="backup_inplace",
            help="backup inplace",
            action="store_true",
        )
        parser.add_argument(
            "--backup-skip-chrome",
            dest="backup_skip_chrome",
            help="backup skip chrome",
            action="store_true",
        )
        parser.add_argument("--run", dest="run", help="run", action="store_true")
        parser.add_argument("--run-warp", dest="run_warp", help="run warp", action="store_true")
        parser.add_argument(
            "--run-rev",
            dest="run_rev",
            help="run rev, can be out or backup",
            default="default",
        )
        parser.add_argument(
            "--run-angle-rev",
            dest="test_angle_rev",
            help="ANGLE revision",
            default="latest",
        )
        parser.add_argument(
            "--run-chrome-channel",
            dest="run_chrome_channel",
            help="run chrome channel",
            default="build",
        )
        parser.add_argument(
            "--run-mesa-rev",
            dest="run_mesa_rev",
            help="mesa revision",
            default="latest",
        )
        parser.add_argument(
            "--run-filter",
            dest="run_filter",
            help="WebGL CTS suite to run against",
            default="all",
        )  # For smoke run, we may use conformance/attribs
        parser.add_argument(
            "--run-verbose",
            dest="run_verbose",
            help="verbose mode of run",
            action="store_true",
        )
        parser.add_argument(
            "--run-dawn-validation",
            dest="run_dawn_validation",
            help="run dawn validation, can be disabled, partial or full",
            default="disabled",
        )
        parser.add_argument(
            "--run-target",
            dest="run_target",
            help='run target, split by comma, like "0,2"',
            default="all",
        )
        parser.add_argument(
            "--run-no-angle",
            dest="run_no_angle",
            help="run without angle",
            action="store_true",
        )
        parser.add_argument("--run-jobs", dest="run_jobs", help="run jobs", default=0)
        parser.add_argument("--run-dry", dest="run_dry", help="dry run", action="store_true")
        parser.add_argument("--run-manual", dest="run_manual", help="run manual", action="store_true")
        parser.add_argument("--report", dest="report", help="report")
        parser.add_argument(
            "--report-max-fail",
            dest="report_max_fail",
            help="max fail in report",
            default=1000,
            type=int,
        )

        parser.add_argument("--batch", dest="batch", help="batch", action="store_true")
        parser.add_argument("--email", dest="email", help="email", action="store_true")

        parser.epilog = """
examples:
{0} {1} --batch
{0} {1} --batch --target angle
{0} {1} --batch --target dawn
{0} {1} --target angle --run --run-filter EXTBlendFuncExtendedDrawTest
{0} {1} --target webgl --run --run-webgl-target 2
""".format(
            Util.PYTHON, parser.prog
        )

        python_ver = Util.get_python_ver()
        if python_ver[0] == 3:
            super().__init__(parser)
        else:
            super(ChromeDrop, self).__init__(parser)

        args = self.args

        if args.disable_rbe:
            self.rbe = False
        else:
            self.rbe = True
        # Util.prepend_depot_tools_path(self.rbe)

        self.browser_folder = "cr"
        # strip the ending "\"
        root_dir = self.root_dir.strip("\\")
        self.results_dir = f"{root_dir}/results/{self.timestamp}"

        self.run_log = f"{self.results_dir}/run.log"
        Util.ensure_nofile(self.run_log)
        self.run_chrome_channel = args.run_chrome_channel
        self.run_filter = args.run_filter
        self.run_verbose = args.run_verbose
        self.run_target = args.run_target
        self.run_no_angle = args.run_no_angle
        self.run_rev = args.run_rev
        if self.run_rev == "default":
            if args.backup or args.batch:
                self.run_rev = "backup"
            else:
                self.run_rev = "out"
        if args.run_jobs == 0:
            _, _, _, _, vendor_id = Util.get_gpu_info()
            if vendor_id == Util.VENDOR_ID_INTEL:
                self.run_jobs = 1
            else:
                self.run_jobs = 4
        else:
            self.run_jobs = args.run_jobs

        self.target_os = args.target_os
        if not self.target_os:
            self.target_os = Util.HOST_OS

        if args.target == "all":
            self.targets = ["angle", "dawn", "webgl", "webgpu"]
        else:
            self.targets = args.target.split(",")

        targets = []
        if "webgl" in self.targets:
            targets += ["webgl"]
        if "webgpu" in self.targets:
            targets += ["webgpu"]
        target = ",".join(targets)

        if args.run or args.batch:
            gpu_name, gpu_driver_date, gpu_driver_ver, gpu_device_id, _ = Util.get_gpu_info()
            Util.append_file(self.run_log, f"GPU name{self.SEPARATOR}{gpu_name}")
            Util.append_file(self.run_log, f"GPU driver date{self.SEPARATOR}{gpu_driver_date}")
            Util.append_file(self.run_log, f"GPU driver version{self.SEPARATOR}{gpu_driver_ver}")
            Util.append_file(self.run_log, f"GPU device id{self.SEPARATOR}{gpu_device_id}")
            os_ver = Util.get_os_info()
            Util.append_file(self.run_log, f"OS version{self.SEPARATOR}{os_ver}")

        for target in self.targets:
            gnp = Gnp2(root_dir=f'{self.root_dir}/{target}')
            if args.sync or args.batch:
                gnp.sync()
            if args.makefile or args.batch:
                gnp.makefile()
            if args.build or args.batch:
                gnp.build(target)
            if args.backup or args.batch:
                gnp.backup(target)
            if args.run or args.batch:
                self.run(gnp, target)

        if args.run or args.batch or args.report:
            self.report()

    def run(self, gnp, target):
        if "angle" == target:
            angle_dir = f"{self.root_dir}/{target}"
            if self.run_rev == "out":
                output_file = f"{angle_dir}/out/release_{self.target_cpu}/output.json"
                # TestExpectation.update('angle_end2end_tests', f'{angle_dir}')
            else:
                rev_name, _ = Util.get_backup_dir(f"{angle_dir}/backup", "latest")
                output_file = f"{angle_dir}/backup/{rev_name}/out/release_{self.target_cpu}/output.json"
                # TestExpectation.update("angle_end2end_tests", f"{angle_dir}/backup/{rev_name}")

            timer = Timer()
            gnp.run(target, rev=self.run_rev, run_dry=self.args.run_dry)
            Util.append_file(self.run_log, f"ANGLE Run: {timer.stop()}")

            result_file = f"{self.results_dir}/angle.json"
            if os.path.exists(output_file):
                shutil.move(output_file, result_file)
            else:
                Util.ensure_file(result_file)

            if self.run_rev == "out":
                Util.append_file(self.run_log, f"ANGLE Rev{self.SEPARATOR}out")
            else:
                Util.append_file(self.run_log, f"ANGLE Rev{self.SEPARATOR}{rev_name}")

        if "dawn" == target:
            all_backends = []
            if Util.HOST_OS == Util.WINDOWS:
                all_backends = ["d3d12"]
            elif Util.HOST_OS == Util.LINUX:
                all_backends = ["vulkan"]
            test_backends = []
            if self.run_target == "all":
                test_backends = all_backends
            else:
                for i in self.run_target.split(","):
                    test_backends.append(all_backends[int(i)])

            for backend in test_backends:
                result_file = f"{self.results_dir}/dawn-{backend}.json"
                timer = Timer()
                gnp.run(target, rev=self.run_rev, result_file=result_file, backend=backend, run_dry=self.args.run_dry)
                Util.append_file(self.run_log, f"Dawn-{backend} run: {timer.stop()}")

            if self.run_rev == "out":
                Util.append_file(self.run_log, f"Dawn Rev{self.SEPARATOR}out")
            else:
                rev_name, _ = Util.get_backup_dir(f"{self.root_dir}/{target}/backup", "latest")
                Util.append_file(self.run_log, f"Dawn Rev{self.SEPARATOR}{rev_name}")

        if "webgl" == target:
            common_cmd1 = "vpython3.bat content/test/gpu/run_gpu_integration_test.py"
            common_cmd2 = " --disable-log-uploads"
            if self.run_chrome_channel == "build":
                self.chrome_rev = self.run_rev
                if self.run_rev == "out":
                    chrome_rev_dir = self.chrome_dir
                else:
                    chrome_rev_dir, _ = Util.get_backup_dir(self.chrome_backup_dir, "latest")
                    chrome_rev_dir = f"{self.chrome_backup_dir}/{chrome_rev_dir}"
                Util.chdir(chrome_rev_dir, verbose=True)
                Util.info(f"Use Chrome at {chrome_rev_dir}")

                if Util.HOST_OS == Util.WINDOWS:
                    chrome = f"out\\release_{self.target_cpu}\\chrome.exe"
                else:
                    if os.path.exists(f"out/release_{self.target_cpu}/chrome"):
                        chrome = f"out/release_{self.target_cpu}/chrome"
                    else:
                        chrome = "out/Default/chrome"

                common_cmd2 += f" --browser=release_{self.target_cpu}"
            else:
                common_cmd2 += f" --browser={self.run_chrome_channel}"
                Util.chdir(self.chrome_dir)
                self.chrome_rev = self.run_chrome_channel
                if Util.HOST_OS == Util.DARWIN:
                    if self.run_chrome_channel == "canary":
                        chrome = '"/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"'
                    else:
                        Util.error("run_chrome_channel is not supported")
                elif Util.HOST_OS == Util.LINUX:
                    if self.run_chrome_channel == "canary":
                        chrome = "/usr/bin/google-chrome-unstable"
                    elif self.run_chrome_channel == "stable":
                        chrome = "/usr/bin/google-chrome-stable"
                    else:
                        Util.error("run_chrome_channel is not supported")
                else:
                    Util.error("run_chrome_channel is not supported")

            if self.args.run_manual:
                param = "--enable-experimental-web-platform-features --disable-gpu-process-for-dx12-vulkan-info-collection --disable-domain-blocking-for-3d-apis --disable-gpu-process-crash-limit --disable-blink-features=WebXR --js-flags=--expose-gc --disable-gpu-watchdog --autoplay-policy=no-user-gesture-required --disable-features=UseSurfaceLayerForVideo --enable-net-benchmarking --metrics-recording-only --no-default-browser-check --no-first-run --ignore-background-tasks --enable-gpu-benchmarking --deny-permission-prompts --autoplay-policy=no-user-gesture-required --disable-background-networking --disable-component-extensions-with-background-pages --disable-default-apps --disable-search-geolocation-disclosure --enable-crash-reporter-for-testing --disable-component-update"
                param += " --use-gl=angle"
                if Util.HOST_OS == Util.LINUX and self.run_no_angle:
                    param += " --use-gl=desktop"
                self._execute(
                    f"{chrome} {param} http://<server>/workspace/project/WebGL/sdk/tests/webgl-conformance-tests.html?version=2.0.1"
                )
                return

            if self.run_filter != "all":
                common_cmd2 += f" --test-filter=*{self.run_filter}*"
            if self.args.run_dry:
                # common_cmd2 += ' --test-filter=*copy-texture-image-same-texture*::*ext-texture-norm16*'
                common_cmd2 += " --test-filter=*conformance/attribs*"

            if Util.HOST_OS in self.SKIP_CASES:
                skip_filter = self.SKIP_CASES[Util.HOST_OS]
                for skip_tmp in skip_filter:
                    common_cmd2 += f" --skip={skip_tmp}"
            if self.run_verbose:
                common_cmd2 += " --verbose"

            common_cmd2 += f" --jobs={self.run_jobs}"

            Util.ensure_dir(self.results_dir)

            COMB_INDEX_WEBGL = 0
            COMB_INDEX_BACKEND = 1
            if Util.HOST_OS in [Util.LINUX, Util.DARWIN]:
                all_combs = ["2.0.1"]
            elif Util.HOST_OS == Util.WINDOWS:
                all_combs = ["1.0.3", "2.0.1"]

            test_combs = []
            if self.run_target == "all":
                test_combs = all_combs
            else:
                for i in self.run_target.split(","):
                    test_combs.append(all_combs[int(i)])

            if self.args.run_warp:
                use_angle = "d3d11-warp"
            else:
                use_angle = "d3d11"

            for comb in test_combs:
                # Locally update related conformance_expectations.txt
                if comb == "1.0.3":
                    TestExpectation.update("webgl_cts_tests", chrome_rev_dir)
                elif comb == "2.0.1":
                    TestExpectation.update("webgl2_cts_tests", chrome_rev_dir)
                extra_browser_args = "--disable-backgrounding-occluded-windows"
                if Util.HOST_OS == Util.LINUX and self.run_no_angle:
                    extra_browser_args += ",--use-gl=desktop"
                cmd = common_cmd1 + f" webgl{comb[0]}_conformance {common_cmd2} --webgl-conformance-version={comb}"
                result_file = ""
                if Util.HOST_OS == Util.LINUX:
                    result_file = f"{self.results_dir}/webgl-{comb}.log"
                elif Util.HOST_OS == Util.WINDOWS:
                    extra_browser_args += f" --use-angle={use_angle}"
                    result_file = f"{self.results_dir}/webgl-{comb}-{use_angle}.log"

                if self.args.run_warp:
                    extra_browser_args += " --enable-features=AllowD3D11WarpFallback --disable-gpu"
                if extra_browser_args:
                    cmd += f' --extra-browser-args="{extra_browser_args}"'
                cmd += f" --write-full-results-to {result_file}"
                timer = Timer()
                self._execute(cmd, exit_on_error=False, show_duration=True)
                Util.append_file(self.run_log, f"WebGL {comb} run: {timer.stop()}")

            if self.run_rev == "out":
                Util.append_file(self.run_log, f"Chrome Rev{self.SEPARATOR}out")
            else:
                rev_name, _ = Util.get_backup_dir(f"{os.path.dirname(self.chrome_dir)}/backup", "latest")
                Util.append_file(self.run_log, f"Chrome Rev{self.SEPARATOR}{rev_name}")

        if "webgpu" == target:
            cmd = "vpython3.bat content/test/gpu/run_gpu_integration_test.py webgpu_cts --passthrough --stable-jobs"
            cmd += " --disable-log-uploads"
            if self.run_chrome_channel == "build":
                if self.run_rev == "out":
                    chrome_rev_dir = self.chrome_dir
                else:
                    chrome_rev_dir, _ = Util.get_backup_dir(self.chrome_backup_dir, "latest")
                    chrome_rev_dir = f"{self.chrome_backup_dir}/{chrome_rev_dir}"
                    # Locally update expectations.txt and slow_tests.txt in webgpu_cts_tests
                    TestExpectation.update("webgpu_cts_tests", chrome_rev_dir)
                Util.chdir(chrome_rev_dir, verbose=True)
                Util.info(f"Use Chrome at {chrome_rev_dir}")

                if Util.HOST_OS == Util.WINDOWS:
                    chrome = f"out\\release_{self.target_cpu}\\chrome.exe"
                else:
                    if os.path.exists(f"out/release_{self.target_cpu}/chrome"):
                        chrome = f"out/release_{self.target_cpu}/chrome"
                    else:
                        chrome = "out/Default/chrome"

                cmd += f" --browser=release_{self.target_cpu}"
            else:
                cmd += f" --browser={self.run_chrome_channel}"
                Util.chdir(self.chrome_dir)
                self.chrome_rev = self.run_chrome_channel
                if Util.HOST_OS == Util.DARWIN:
                    if self.run_chrome_channel == "canary":
                        chrome = '"/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"'
                    else:
                        Util.error("run_chrome_channel is not supported")
                elif Util.HOST_OS == Util.LINUX:
                    if self.run_chrome_channel == "canary":
                        chrome = "/usr/bin/google-chrome-unstable"
                    elif self.run_chrome_channel == "stable":
                        chrome = "/usr/bin/google-chrome-stable"
                    else:
                        Util.error("run_chrome_channel is not supported")
                else:
                    Util.error("run_chrome_channel is not supported")

            if self.run_filter != "all":
                cmd += f" --test-filter=*{self.run_filter}*"
            if self.args.run_dry:
                cmd += (
                    " --test-filter=*webgpu:api,operation,render_pipeline,pipeline_output_targets:color,attachments:*"
                )

            if self.run_verbose:
                cmd += " --verbose"

            cmd += f" --jobs={self.run_jobs}"

            Util.ensure_dir(self.results_dir)

            extra_browser_args = "--js-flags=--expose-gc --force_high_performance_gpu"
            result_file = f"{self.results_dir}/webgpu.log"

            if extra_browser_args:
                cmd += f' --extra-browser-args="{extra_browser_args}"'
            cmd += f" --write-full-results-to {result_file}"
            timer = Timer()
            self._execute(cmd, exit_on_error=False, show_duration=True)
            Util.append_file(self.run_log, f"WebGPU run: {timer.stop()}")

            if self.run_rev == "out":
                Util.append_file(self.run_log, f"Chrome Rev{self.SEPARATOR}out")
            else:
                rev_name, _ = Util.get_backup_dir(f"{os.path.dirname(self.chrome_dir)}/backup", "latest")
                Util.append_file(self.run_log, f"Chrome Rev{self.SEPARATOR}{rev_name}")

    def report(self):
        if self.args.report:
            self.results_dir = self.args.report

        regression_count = 0
        summary = "Final summary:\n"
        details = "Final details:\n"
        for result_file in os.listdir(self.results_dir):
            if "angle" in result_file or "webgl" in result_file or "webgpu" in result_file:
                test_type = "gtest_angle"
            elif "dawn" in result_file:
                test_type = "dawn"
            else:
                continue

            result = TestResult(f"{self.results_dir}/{result_file}", test_type)
            regression_count += len(result.pass_fail)
            result_str = f"{os.path.splitext(result_file)[0]}: PASS_FAIL {len(result.pass_fail)}, FAIL_PASS {len(result.fail_pass)}, FAIL_FAIL {len(result.fail_fail)} PASS_PASS {len(result.pass_pass)}\n"
            summary += result_str
            if result.pass_fail:
                result_str += "\n[PASS_FAIL]\n%s\n\n" % "\n".join(result.pass_fail[: self.args.report_max_fail])
            details += result_str

        Util.info(details)
        Util.info(summary)
        if os.path.exists(self.run_log):
            run_log_content = open(self.run_log, encoding="utf-8").read()
            Util.info(run_log_content)

        report_file = f"{self.results_dir}/report.txt"
        Util.ensure_nofile(report_file)
        Util.append_file(report_file, summary)
        Util.append_file(report_file, details)

        if self.args.email or self.args.batch:
            subject = f"[Chrome Drop] {Util.HOST_NAME} {self.timestamp}"
            content = summary + "\n" + details + "\n"
            if os.path.exists(self.run_log):
                content += run_log_content
            Util.send_email(subject, content)


if __name__ == "__main__":
    WebgfxTest()
