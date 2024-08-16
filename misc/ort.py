"""
git clone --recursive https://github.com/Microsoft/onnxruntime
install cmake, node.js, python, ninja

[usage]
python ort.py --build

[reference]
https://onnxruntime.ai/docs/build/web.html
https://gist.github.com/fs-eire/a55b2c7e10a6864b9602c279b8b75dce
"""

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


class Ort(Program):
    def __init__(self):
        parser = argparse.ArgumentParser(description="ORT")

        parser.add_argument("--sync", dest="sync", help="sync", action="store_true")
        parser.add_argument("--build", dest="build", help="build", action="store_true")
        parser.add_argument(
            "--build-small", dest="build_small", help="build if only WebGPU EP is changed", action="store_true"
        )
        parser.add_argument(
            "--build-type",
            dest="build_type",
            help="build type, can be Debug, MinSizeRel, Release or RelWithDebInfo",
            default="MinSizeRel",
        )
        parser.add_argument(
            "--build-skip-wasm",
            dest="build_skip_wasm",
            help="build skip wasm",
            action="store_true",
        )
        parser.add_argument(
            "--build-skip-ci",
            dest="build_skip_ci",
            help="build skip ci",
            action="store_true",
        )
        parser.add_argument(
            "--build-skip-pull-wasm",
            dest="build_skip_pull_wasm",
            help="build skip pull wasm",
            action="store_true",
        )
        parser.add_argument("--lint", dest="lint", help="lint", action="store_true")

        parser.epilog = """
examples:
{0} {1} --build
""".format(
            Util.PYTHON, parser.prog
        )

        super().__init__(parser)
        self._handle_ops()

    def sync(self):
        pass

    def build(self):
        timer = Timer()
        root_dir = self.root_dir

        Util.chdir(root_dir, verbose=True)
        if Util.HOST_OS == Util.WINDOWS:
            build_cmd = "build.bat"
            os_dir = "Windows"
        else:
            build_cmd = "./build.sh"
            os_dir = "Linux"

        build_type = self.args.build_type
        build_dir = f"build/{os_dir}"

        if not self.args.build_skip_wasm and not self.args.build_small:
            # --enable_wasm_debug_info may cause unit test crash
            cmd = f"{build_cmd} --config {build_type} --build_wasm --enable_wasm_simd --enable_wasm_threads --parallel --skip_tests --skip_submodule_sync --disable_wasm_exception_catching --use_jsep --target onnxruntime_webassembly --disable_rtti"
            Util.execute(cmd, show_cmd=True, show_duration=True)

        if not self.args.build_skip_ci:
            Util.chdir(f"{root_dir}/js", verbose=True)
            Util.execute("npm ci", show_cmd=True)

            Util.chdir(f"{root_dir}/js/common", verbose=True)
            Util.execute("npm ci", show_cmd=True)

            Util.chdir(f"{root_dir}/js/web", verbose=True)
            Util.execute("npm ci", show_cmd=True)

        if not self.args.build_skip_pull_wasm and not self.args.build_small:
            Util.chdir(f"{root_dir}/js/web", verbose=True)
            Util.execute("npm run pull:wasm", show_cmd=True, exit_on_error=False)

        file_name = "ort-wasm-simd-threaded"
        Util.copy_file(
            f"{root_dir}/{build_dir}/{build_type}",
            f"{file_name}.jsep.mjs",
            f"{root_dir}/js/web/dist",
            f"{file_name}.jsep.mjs",
            need_bk=False,
            show_cmd=True,
        )
        Util.copy_file(
            f"{root_dir}/{build_dir}/{build_type}",
            f"{file_name}.jsep.wasm",
            f"{root_dir}/js/web/dist",
            f"{file_name}.jsep.wasm",
            need_bk=False,
            show_cmd=True,
        )

        Util.chdir(f"{root_dir}/js/web", verbose=True)
        Util.execute("npm run build", show_cmd=True)

        Util.info(f"{timer.stop()} was spent to build")

    def lint(self):
        Util.chdir(f"{self.root_dir}/js", verbose=True)
        Util.execute("npm run lint", show_cmd=True)

    def _handle_ops(self):
        args = self.args
        if args.sync:
            self.sync()
        if args.build:
            self.build()
        if args.build_small:
            self.build()
        if args.lint:
            self.lint()


if __name__ == "__main__":
    Ort()
