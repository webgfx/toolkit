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

        parser.add_argument("--build-web", dest="build_web", help="build web", action="store_true")
        parser.add_argument("--build-wasm64", dest="build_wasm64", help="build wasm64", action="store_true")
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

        parser.add_argument("--build-native", dest="build_native", help="build native", action="store_true")
        parser.add_argument("--build-cuda", dest="build_cuda", help="build cuda", action="store_true")
        parser.add_argument(
            "--cuda-home",
            dest="cuda_home",
            help="cuda home",
            default="C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6",
        )
        parser.add_argument(
            "--cudnn-home", dest="cudnn_home", help="cudnn home", default="C:/Program Files/NVIDIA/CUDNN/v9.0"
        )

        parser.add_argument("--build-genai", dest="build_genai", help="build genai", action="store_true")

        parser.add_argument("--build-small", dest="build_small", help="skip the major build", action="store_true")
        parser.add_argument(
            "--build-type",
            dest="build_type",
            help="build type, can be Debug, MinSizeRel, Release or RelWithDebInfo",
            default="default",
        )
        parser.add_argument("--lint", dest="lint", help="lint", action="store_true")
        parser.add_argument("--split-model", dest="split_model", help="split model for a external data file")

        parser.epilog = """
examples:
{0} {1} --build
""".format(
            Util.PYTHON, parser.prog
        )

        super().__init__(parser)

        Util.chdir(self.root_dir, verbose=True)
        if Util.HOST_OS == Util.WINDOWS:
            self.build_cmd = "build.bat"
            os_dir = "Windows"
        else:
            self.build_cmd = "./build.sh"
            os_dir = "Linux"

        self.build_type = self.args.build_type
        self.build_dir = f"build/{os_dir}"
        self.install_dir = f'{Util.PROJECT_DIR}/ort-wgpu-install'
        Util.ensure_dir(self.install_dir)

        self._handle_ops()

    def split_model(self):
        import onnx

        model_path = self.args.split_model
        model_name = os.path.basename(model_path).replace('.onnx', '')
        Util.chdir(os.path.dirname(model_path), verbose=True)
        onnx_model = onnx.load(f'{model_name}.onnx')
        onnx.save_model(
            onnx_model,
            f'{model_name}-ext.onnx',
            save_as_external_data=True,
            all_tensors_to_one_file=True,
            location=f'{model_name}-ext.data',
            size_threshold=1024,
            convert_attribute=False,
        )

    def sync(self):
        pass

    def build_cuda(self):
        timer = Timer()
        if self.build_type == 'default':
            self.build_type = 'Debug'
        cmd = f'{self.build_cmd} --config {self.build_type} --use_cuda --compile_no_warning_as_error --enable_cuda_nhwc_ops --skip_tests --cuda_home "{self.args.cuda_home}" --cudnn_home "{self.args.cudnn_home}"'
        Util.execute(cmd, show_cmd=True, show_duration=True)
        Util.info(f"{timer.stop()} was spent to build")

    def build_genai(self):
        # branch gs/wgpu
        timer = Timer()
        if self.build_type == 'default':
            self.build_type = 'Release'
        cmd = f'{self.build_cmd} --config {self.build_type} --use_webgpu'
        Util.execute(cmd, show_cmd=True, show_duration=True)
        Util.info(f"{timer.stop()} was spent to build")

    def build_web(self):
        timer = Timer()

        if self.build_type == 'default':
            self.build_type = 'MinSizeRel'
        if not self.args.build_skip_wasm and not self.args.build_small:
            # --enable_wasm_debug_info may cause unit test crash
            cmd = f"{self.build_cmd} --config {self.build_type} --build_wasm --enable_wasm_simd --enable_wasm_threads --parallel --skip_tests --skip_submodule_sync --use_jsep --target onnxruntime_webassembly"
            if self.args.build_type == "Debug":
                cmd += " --enable_wasm_debug_info"
            else:
                cmd += " --disable_wasm_exception_catching --disable_rtti"

            if self.args.build_wasm64:
                cmd += " --enable_wasm_memory64 --compile_no_warning_as_error"
            Util.execute(cmd, show_cmd=True, show_duration=True)

        if not self.args.build_skip_ci:
            Util.chdir(f"{self.root_dir}/js", verbose=True)
            Util.execute("npm ci", show_cmd=True)

            Util.chdir(f"{self.root_dir}/js/common", verbose=True)
            Util.execute("npm ci", show_cmd=True)

            Util.chdir(f"{self.root_dir}/js/web", verbose=True)
            Util.execute("npm ci", show_cmd=True)

        if not self.args.build_skip_pull_wasm and not self.args.build_small:
            Util.chdir(f"{self.root_dir}/js/web", verbose=True)
            Util.execute("npm run pull:wasm", show_cmd=True, exit_on_error=False)

        file_name = "ort-wasm-simd-threaded"
        Util.copy_file(
            f"{self.root_dir}/{self.build_dir}/{self.build_type}",
            f"{file_name}.jsep.mjs",
            f"{self.root_dir}/js/web/dist",
            f"{file_name}.jsep.mjs",
            need_bk=False,
            show_cmd=True,
        )
        Util.copy_file(
            f"{self.root_dir}/{self.build_dir}/{self.build_type}",
            f"{file_name}.jsep.wasm",
            f"{self.root_dir}/js/web/dist",
            f"{file_name}.jsep.wasm",
            need_bk=False,
            show_cmd=True,
        )

        Util.chdir(f"{self.root_dir}/js/web", verbose=True)
        Util.execute("npm run build", show_cmd=True)

        Util.info(f"{timer.stop()} was spent to build")

    def build_native(self):
        timer = Timer()
        if self.build_type == 'default':
            self.build_type = 'Release'

        if not self.args.build_small:
            cmd = f'{self.build_cmd} --config {self.build_type} --parallel --skip_tests --use_webgpu --build_nodejs --build_shared_lib --cmake_generator "Visual Studio 17 2022"'
            cmd += ' --cmake_extra_defines onnxruntime_BUILD_UNIT_TESTS=OFF --enable_pybind --build_wheel'
            #cmd += " --use_dml --skip_submodule_sync"
            Util.execute(cmd, show_cmd=True, show_duration=True)
            Util.info(f"{timer.stop()} was spent to build")

        Util.chdir(f"{self.root_dir}/{self.build_dir}", verbose=True)
        Util.execute(
            f'cmake --install {self.build_type} --config {self.build_type} --prefix {self.install_dir}/{self.build_type}', show_cmd=True, show_duration=True
        )
        Util.chdir(f"{self.install_dir}/{self.build_type}", verbose=True)

        Util.copy_files('bin', 'lib')
        Util.copy_files('include/onnxruntime', 'include')

    def lint(self):
        Util.chdir(f"{self.root_dir}/js", verbose=True)
        Util.execute("npm run lint", show_cmd=True)

    def _handle_ops(self):
        args = self.args
        if args.sync:
            self.sync()
        if args.build_cuda:
            self.build_cuda()
        if args.build_genai:
            self.build_genai()
        if args.build_web:
            self.build_web()
        if args.build_native:
            self.build_native()
        if args.lint:
            self.lint()
        if args.split_model:
            self.split_model()


if __name__ == "__main__":
    Ort()
