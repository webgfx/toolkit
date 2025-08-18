# pylint: disable=line-too-long, missing-function-docstring, missing-module-docstring, missing-class-docstring, disable=wrong-import-position

import argparse
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

from util.base import Util, Program
from misc.testhelper import TestResult
from misc.project import Project


class Webgfx(Program):
    SKIP_CASES = {
        # Util.LINUX: ['WebglConformance_conformance2_textures_misc_tex_3d_size_limit'],
        Util.LINUX: [],
    }
    SEPARATOR = ": "

    def __init__(self):
        parser = argparse.ArgumentParser(description="webgfx")

        parser.add_argument("--target", dest="target", help="target", default="all")
        parser.add_argument("--sync", dest="sync", help="sync", action="store_true")
        parser.add_argument("--makefile", dest="makefile", help="makefile", action="store_true")
        parser.add_argument("--makefile-local", dest="makefile_local", help="makefile without rbe", action="store_true")
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
            "--run-chrome-channel",
            dest="run_chrome_channel",
            help="run chrome channel",
            default="build",
        )
        parser.add_argument(
            "--run-filter",
            dest="run_filter",
            help="WebGL CTS suite to run against",
            default="all",
        )
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
            "--run-combo",
            dest="run_combo",
            help='run backend, split by comma, like "webgl,"',
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
        parser.add_argument("--browser-dir", dest="browser_dir", help="browser dir", default="cr")

        parser.add_argument("--upload", dest="upload", help="upload", action="store_true")
        parser.add_argument("--download", dest="download", help="download", action="store_true")

        parser.epilog = """
examples:
{0} {1} --batch
{0} {1} --batch --target angle
{0} {1} --batch --target dawn
{0} {1} --target angle --run --run-filter EXTBlendFuncExtendedDrawTest
{0} {1} --target webgl --run --run-combo 2
""".format(
            Util.PYTHON, parser.prog
        )

        super().__init__(parser)
        args = self.args

        self.browser_dir = args.browser_dir
        # strip the ending "\"
        root_dir = self.root_dir.strip("\\")
        self.result_dir = f"{root_dir}/result/{self.timestamp}"

        self.run_log = f"{self.result_dir}/run.log"
        Util.ensure_nofile(self.run_log)
        self.run_chrome_channel = args.run_chrome_channel
        self.run_filter = args.run_filter
        self.run_verbose = args.run_verbose
        self.run_combo = args.run_combo
        self.run_no_angle = args.run_no_angle
        self.run_rev = args.run_rev
        if self.run_rev == "default":
            if args.backup or args.batch:
                self.run_rev = "backup"
            else:
                self.run_rev = "out"
        if args.run_jobs == 0:
            if args.run_dry:
                self.run_jobs = 1
            else:
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

        has_chromium_backup = False
        for target in self.targets:
            if target in ['webgl', 'webgpu']:
                project = Project(root_dir=f'{self.root_dir}/{self.browser_dir}', result_dir=self.result_dir)
            else:
                project = Project(root_dir=f'{self.root_dir}/{target}', result_dir=self.result_dir)

            if args.sync or args.batch:
                project.sync()
            if args.makefile or args.batch:
                project.makefile(local=args.makefile_local)
            if args.build or args.batch:
                project.build(target)
            if args.backup or args.batch:
                if target in ['webgl', 'webgpu'] and has_chromium_backup:
                    continue
                project.backup([target])
                if target in ['webgl', 'webgpu']:
                    has_chromium_backup = True
            if args.download:
                project.download()
            if args.run or args.batch:
                self.run(project, target)
            if args.upload:
                project.upload()

        if args.run or args.batch or args.report:
            self.report()

    def run(self, project, target):
        if self.run_combo == "all":
            if target in ["dawn","webgpu"]:
                combos = [0]
            else:
                combos = []
        else:
            combos = list(map(int, self.run_combo.split()))

        project.run(
            target=target,
            combos=combos,
            rev=self.run_rev,
            run_dry=self.args.run_dry,
            run_filter=self.run_filter,
            validation=self.args.run_dawn_validation,
            jobs=self.run_jobs,
        )

    def report(self):
        if self.args.report:
            self.result_dir = self.args.report

        regression_count = 0
        summary = "Final summary:\n"
        details = "Final details:\n"
        for result_file in os.listdir(self.result_dir):
            if "angle" in result_file or "webgl" in result_file or "webgpu" in result_file:
                test_type = "gtest_angle"
            elif "dawn" in result_file:
                test_type = "dawn"
            else:
                continue

            result = TestResult(f"{self.result_dir}/{result_file}", test_type)
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

        report_file = f"{self.result_dir}/report.txt"
        Util.ensure_nofile(report_file)
        Util.append_file(report_file, summary)
        Util.append_file(report_file, details)

        if self.args.email or self.args.batch:
            gpu_name, _, _, _, _ = Util.get_gpu_info()
            subject = f"[webgfx report] {self.timestamp} | {Util.HOST_NAME} | {gpu_name}"
            content = summary + "\n" + details + "\n"
            if os.path.exists(self.run_log):
                content += run_log_content
            Util.send_email(subject, content)


if __name__ == "__main__":
    Webgfx()
