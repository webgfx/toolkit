import os
import platform
import re
import subprocess
import sys

HOST_OS = sys.platform
if HOST_OS == 'win32':
    lines = subprocess.Popen('dir %s' % __file__.replace(
        '/', '\\'), shell=True, stdout=subprocess.PIPE).stdout.readlines()
    for line in lines:
        match = re.search(r'\[(.*)\]', line.decode('utf-8'))
        if match:
            script_dir = os.path.dirname(match.group(1)).replace('\\', '/')
            break
    else:
        script_dir = sys.path[0]
else:
    lines = subprocess.Popen(
        'ls -l %s' % __file__, shell=True, stdout=subprocess.PIPE).stdout.readlines()
    for line in lines:
        match = re.search(r'.* -> (.*)', line.decode('utf-8'))
        if match:
            script_dir = os.path.dirname(match.group(1))
            break
    else:
        script_dir = sys.path[0]

sys.path.append(script_dir)
sys.path.append(script_dir + '/..')

from util.base import *  # pylint: disable=unused-wildcard-import
from misc.testhelper import *

class GPUTest(Program):
    GPUTEST_FOLDER = 'gputest'

    PROJECT_INFO_INDEX_ROOT_DIR = 0
    PROJECT_INFO_INDEX_CONFIG_FILES = 1
    CHROMIUM_CONFIG_FILES = []
    if Util.HOST_OS == Util.WINDOWS:
        CHROMIUM_CONFIG_FILES = [
            'infra/config/generated/builders/try/dawn-win10-x64-deps-rel/targets/chromium.dawn.json',
            'infra/config/generated/builders/try/gpu-fyi-try-win10-intel-rel-64/targets/chromium.gpu.fyi.json'
        ]
    elif Util.HOST_OS == Util.LINUX:
        CHROMIUM_CONFIG_FILES = [
            'infra/config/generated/builders/try/dawn-linux-x64-deps-rel/targets/chromium.dawn.json',
            'infra/config/generated/builders/try/gpu-fyi-try-linux-intel-rel/targets/chromium.gpu.fyi.json'
        ]
    PROJECT_INFO = {
        'angle': ['%s/%s/angle' % (Util.PROJECT_DIR, GPUTEST_FOLDER), ['infra/specs/angle.json']],
        'chromium': ['%s/%s/chromium/src' % (Util.PROJECT_DIR, GPUTEST_FOLDER), CHROMIUM_CONFIG_FILES],
    }

    SKIP_CASES_INDEX_OS = 0
    SKIP_CASES_INDEX_VIRTUAL_NAME = 1
    SKIP_CASES_INDEX_CASES = 2
    SKIP_CASES = [
        #[Util.WINDOWS, 'dawn_end2end_validation_layers_tests'],
        #[Util.LINUX, 'dawn_end2end_tests', 'SwapChainTests.SwitchPresentMode/Vulkan_Intel_R_UHD_Graphics_630_CFL_GT2'],
    ]

    REAL_TYPE_INFO_INDEX_FILTER = 0
    REAL_TYPE_INFO_INDEX_EXTRA_ARGS = 1
    REAL_TYPE_INFO = {
        'gtest_angle': ['--gtest_filter', ''], # --cfi-diag=0
        'gtest_chrome': ['--gtest_filter', ''], # --cfi-diag=0
        'telemetry_gpu_integration_test': ['--test-filter', '--retry-limit 1 --retry-only-retry-on-failure-tests'],
        'webgpu_blink_web_tests': ['--isolated-script-test-filter', ''],
    }

    VIRTUAL_NAME_INFO_INDEX_REAL_TYPE = 0
    VIRTUAL_NAME_INFO_INDEX_DRYRUN = 1
    VIRTUAL_NAME_INFO_INDEX_EXTRA_ARGS = 2
    VIRTUAL_NAME_INFO = {
        'angle_end2end_tests': ['gtest_angle', 'EGLAndroidFrameBufferTargetTest'],
        'angle_white_box_tests': ['gtest_angle', 'VulkanDescriptorSetTest.AtomicCounterReadLimitedDescriptorPool'],

        'dawn_end2end_skip_validation_tests': ['gtest_chrome', 'BindGroupTests', '--adapter-vendor-id=0x8086'],
        'dawn_end2end_tests': ['gtest_chrome', 'ComputeStorageBufferBarrierTests', ''],
        'dawn_end2end_tests_runsuppressed': ['gtest_chrome', 'AlignSmall', ''],
        'dawn_end2end_validation_layers_tests': ['gtest_chrome', 'BindGroupTests'],
        'dawn_end2end_wire_tests': ['gtest_chrome', 'BindGroupTests'],
        'dawn_perf_tests': ['gtest_chrome', 'BufferUploadPerf.Run/Vulkan_Intel', '--override-steps=1'],
        'vulkan_tests': ['gtest_chrome', 'BasicVulkanTest'],

        'info_collection_tests': ['telemetry_gpu_integration_test', 'InfoCollection_basic'],
        'trace_test': ['telemetry_gpu_integration_test', 'OverlayModeTraceTest_DirectComposition_Video_Disable_Overlays'],
        'webgl2_conformance_d3d11_passthrough_tests': ['telemetry_gpu_integration_test', 'conformance/attribs'],
        'webgl_conformance_d3d11_passthrough_tests': ['telemetry_gpu_integration_test', 'conformance/attribs'],
        'webgl2_conformance_gl_passthrough_tests': ['telemetry_gpu_integration_test', 'conformance/attribs'],
        'webgl_conformance_gl_passthrough_tests': ['telemetry_gpu_integration_test', 'conformance/attribs'],
        'webgpu_cts_tests': ['telemetry_gpu_integration_test', 'webgpu:idl,constants,flags:*'],
        'webgpu_cts_with_validation_tests': ['telemetry_gpu_integration_test', 'webgpu:idl,constants,flags:*'],
        'webgpu_blink_web_tests': ['webgpu_blink_web_tests', 'wpt_internal/webgpu/adapter_single_use.https.html'],
        'webgpu_blink_web_tests_with_backend_validation': ['webgpu_blink_web_tests', 'wpt_internal/webgpu/adapter_single_use.https.html'],
    }

    CONFIG_FILE = 'config.json'

    index = 0
    TARGET_INDEX_OS = index
    index += 1
    TARGET_INDEX_PROJECT = index
    index += 1
    TARGET_INDEX_VIRTUAL_NAME = index
    index += 1
    TARGET_INDEX_REAL_NAME = index
    index += 1
    TARGET_INDEX_REAL_TYPE = index
    index += 1
    TARGET_INDEX_RUN_ARGS = index
    index += 1
    TARGET_INDEX_SHARD_COUNT = index
    TARGET_INDEX_MAX = index

    RESULT_FILE_SUFFIX = '.json'
    RESULT_FILE_PATTERN = r'^.*-(.*)%s$' % RESULT_FILE_SUFFIX
    MAX_FAIL_IN_REPORT = 30000

    SEPARATOR = '|'


    def __init__(self):
        parser = argparse.ArgumentParser(description='GPU Test')

        parser.add_argument('--debug', dest='debug', help='debug', action='store_true')
        parser.add_argument('--target', dest='target', help='target', default='all')
        parser.add_argument('--email', dest='email', help='email', action='store_true')
        parser.add_argument('--email-to', dest='email_to', help='email to')
        parser.add_argument('--location', dest='location', help='local for local backup, remote for remote backup and source for source code', default='default')
        parser.add_argument('--repeat', dest='repeat', help='repeat', type=int, default=1)
        parser.add_argument('--list', dest='list', help='list', action='store_true')
        parser.add_argument('--sync', dest='sync', help='sync', action='store_true')
        #parser.add_argument('--sync-skip-roll-dawn', dest='sync_skip_roll_dawn', help='sync skip roll dawn', action='store_true')
        parser.add_argument('--sync-roll-dawn', dest='sync_roll_dawn', help='sync roll dawn', action='store_true')
        parser.add_argument('--build', dest='build', help='build', action='store_true')
        parser.add_argument('--build-skip-backup', dest='build_skip_backup', help='build skip backup', action='store_true')
        parser.add_argument('--backup', dest='backup', help='backup', action='store_true')
        parser.add_argument('--upload', dest='upload', help='upload', action='store_true')
        parser.add_argument('--run', dest='run', help='run', action='store_true')
        parser.add_argument('--run-mesa-rev', dest='run_mesa_rev', help='run mesa revision, can be system, latest or any specific revision', default='system')
        parser.add_argument('--dryrun', dest='dryrun', help='dryrun', action='store_true')
        parser.add_argument('--dryrun-with-shard', dest='dryrun_with_shard', help='dryrun with shard', action='store_true')

        parser.epilog = '''
examples:
{0} {1} --sync --build --backup --upload --email
{0} {1} --run --email
{0} {1} --run --location=source --email
'''.format(Util.PYTHON, parser.prog)

        python_ver = Util.get_python_ver()
        if python_ver[0] == 3:
            super().__init__(parser)
        else:
            super(GPUTest, self).__init__(parser)

        args = self.args

        self.projects = sorted(self.PROJECT_INFO.keys())
        self.result_dir = '%s/%s/%s' % (ScriptRepo.IGNORE_DIR, self.GPUTEST_FOLDER, self.timestamp)
        Util.ensure_dir(self.result_dir)
        self.exec_log = '%s/exec.log' % self.result_dir
        Util.ensure_nofile(self.exec_log)
        Util.append_file(self.exec_log, 'OS%s%s' % (self.SEPARATOR, Util.HOST_OS_RELEASE))
        self.targets = []
        self.build_type_cap = 'Release'
        if args.location == 'default':
            if args.run:
                args.location = 'remote'
            else:
                args.location = 'source'

        if args.sync:
            self.sync()
        self._update_target()
        if args.list:
            self.list()
        if args.build:
            self.build()
        if args.backup:
            self.backup()
        if args.upload:
            self.upload()
        if args.run:
            self.run()

        self._report()

    def sync(self):
        all_timer = Timer()
        del_projects = []

        for project in self.projects:
            timer = Timer()
            root_dir = self.PROJECT_INFO[project][self.PROJECT_INFO_INDEX_ROOT_DIR]
            cmd = '%s %s --root-dir %s --sync --sync-reset --runhooks' % (Util.PYTHON, self.GNP_SCRIPT, root_dir)
            if self.args.proxy:
                cmd += ' --proxy %s' % (self.args.proxy)
            dryrun = self.args.dryrun
            if self._execute(cmd, exit_on_error=False, dryrun=dryrun)[0]:
                error_info = 'Project %s sync failed' % project
                self._send_email(subject=error_info)
                Util.error(error_info)
                del_projects.append(project)

            if project == 'aquarium' and self.args.sync_roll_dawn:
                Util.chdir('%s/third_party/dawn' % root_dir)
                self._execute('git checkout master && git pull', dryrun=dryrun)
                Util.info('Roll Dawn in Aquarium to %s on %s' % (Util.get_working_dir_hash(), Util.get_working_dir_date()))

            self._log_exec(timer.stop(), 'Sync %s' % project, cmd)

        if del_projects:
            self.projects = Util.diff_list(self.projects, del_projects)
        self._log_exec(all_timer.stop(), 'Total Sync')

    def list(self):
        for index, target in enumerate(self.os_targets):
            print('%s: %s' % (index, target[self.TARGET_INDEX_VIRTUAL_NAME]))

    def build(self):
        self._op('build')

    def backup(self):
        self._op('backup')

    def upload(self):
        self._op('upload')

    def _op(self, op):
        all_timer = Timer()

        del_projects = []
        projects = []
        project_targets = {}
        for target_index in self.target_indexes:
            if target_index < len(self.os_targets) and target_index >= 0:
                project = self.os_targets[target_index][self.TARGET_INDEX_PROJECT]
                if project not in self.projects:
                    continue
                real_name = self.os_targets[target_index][self.TARGET_INDEX_REAL_NAME]
                if project not in projects:
                    projects.append(project)
                    project_targets[project] = [real_name]
                elif real_name not in project_targets[project]:
                    project_targets[project].append(real_name)

        for project in projects:
            timer = Timer()
            root_dir = self.PROJECT_INFO[project][self.PROJECT_INFO_INDEX_ROOT_DIR]

            if op == 'build':
                cmd = '%s %s --root-dir %s --disable-component-build --makefile --build --build-target %s' % (Util.PYTHON, self.GNP_SCRIPT, root_dir, ','.join(project_targets[project]))
            elif op == 'backup':
                cmd = '%s %s --root-dir %s --backup --backup-target %s' % (Util.PYTHON, self.GNP_SCRIPT, root_dir, ','.join(project_targets[project]))
            elif op == 'upload':
                cmd = '%s %s --root-dir %s --upload' % (Util.PYTHON, self.GNP_SCRIPT, root_dir)

            if self._execute(cmd, exit_on_error=False, dryrun=self.args.dryrun)[0]:
                error_info = 'Project %s %s failed' % (project, op)
                self._send_email(subject=error_info)
                Util.error(error_info)
                del_projects.append(project)

            self._log_exec(timer.stop(), '%s %s' % (op.capitalize(), project), cmd)

        if del_projects:
            self.projects = Util.diff_list(self.projects, del_projects)
        self._log_exec(all_timer.stop(), 'Total %s' % op.capitalize())

    def run(self):
        all_timer = Timer()
        args = self.args

        if Util.HOST_OS == Util.LINUX and self.args.run_mesa_rev == 'latest':
            if True:
                cmd = '%s %s --root-dir %s --sync --build' % (Util.PYTHON, Util.MESA_SCRIPT, Util.PROJECT_MESA_DIR)
                dryrun = self.args.dryrun
                if self._execute(cmd, exit_on_error=False, dryrun=dryrun)[0]:
                    error_info = 'Project Mesa build failed'
                    self._send_email(subject=error_info)
                    Util.warning(error_info)
                rev_name, _ = Util.set_mesa(Util.PROJECT_MESA_BACKUP_DIR, self.args.run_mesa_rev)

            else:
                if self.args.location == 'remote':
                    rev_name, rev = Util.get_server_backup('mesa', self.args.run_mesa_rev)
                else:
                    rev_name, rev = Util.get_local_backup('mesa', self.args.run_mesa_rev)
                rev_name, _ = Util.set_mesa('%s/%s/%s' % (Util.BACKUP_DIR, 'mesa', rev_name), self.args.run_mesa_rev)

            Util.append_file(self.exec_log, 'Mesa Revision%s%s' % (self.SEPARATOR, rev_name))

        gpu_name, gpu_driver_date, gpu_driver_ver, gpu_device_id = Util.get_gpu_info()
        Util.append_file(self.exec_log, f'GPU name{self.SEPARATOR}{gpu_name}')
        Util.append_file(self.exec_log, f'GPU driver date{self.SEPARATOR}{gpu_driver_date}')
        Util.append_file(self.exec_log, f'GPU driver version{self.SEPARATOR}{gpu_driver_ver}')
        Util.append_file(self.exec_log, f'GPU device id{self.SEPARATOR}{gpu_device_id}')
        os_ver = Util.get_os_info()
        Util.append_file(self.exec_log, f'OS version{self.SEPARATOR}{os_ver}')

        PROJECT_RUN_INFO_INDEX_ROOT_DIR = 0
        PROJECT_RUN_INFO_INDEX_DATE = 1
        PROJECT_RUN_INFO_INDEX_REV = 2
        project_run_info = {}
        for project in self.projects:
            if self.args.location == 'source':
                root_dir = self.PROJECT_INFO[project][self.PROJECT_INFO_INDEX_ROOT_DIR]
                if project == 'chromium':
                    date = ChromiumRepo(root_dir).get_working_dir_date()
                    rev = ChromiumRepo(root_dir).get_working_dir_rev()
                else:
                    Util.chdir(root_dir)
                    date = Util.get_working_dir_date()
                    rev = Util.get_working_dir_rev()
                project_run_info[project] = [root_dir, date, rev]
            else:
                relative_path = '%s/%s' % (self.GPUTEST_FOLDER, project)
                rev_name, date, rev = Util.get_local_backup(relative_path, 'latest')
                project_run_info[project] = ['%s/%s/%s' % (Util.BACKUP_DIR, relative_path, rev_name), date, rev]

        logged_projects = []
        for index, target_index in enumerate(self.target_indexes):
            project = self.os_targets[target_index][self.TARGET_INDEX_PROJECT]
            project_run_root_dir = project_run_info[project][PROJECT_RUN_INFO_INDEX_ROOT_DIR]
            if project not in logged_projects:
                logged_projects.append(project)
                info = '%s Date%s%s' % (project.capitalize(), self.SEPARATOR, project_run_info[project][PROJECT_RUN_INFO_INDEX_DATE])
                Util.append_file(self.exec_log, info)
                info = '%s Revision%s%s' % (project.capitalize(), self.SEPARATOR, project_run_info[project][PROJECT_RUN_INFO_INDEX_REV])
                Util.append_file(self.exec_log, info)

            virtual_name = self.os_targets[target_index][self.TARGET_INDEX_VIRTUAL_NAME]
            skip = False
            for skip_case in self.SKIP_CASES:
                if Util.HOST_OS == skip_case[self.SKIP_CASES_INDEX_OS] and virtual_name == skip_case[self.SKIP_CASES_INDEX_VIRTUAL_NAME] and len(skip_case) == self.SKIP_CASES_INDEX_VIRTUAL_NAME + 1:
                    skip = True
                    break
            if skip:
                continue

            # Locally update expectation files for Intel GPUs
            TestExpectation.update(virtual_name, project_run_root_dir)

            real_name = self.os_targets[target_index][self.TARGET_INDEX_REAL_NAME]
            real_type = self.os_targets[target_index][self.TARGET_INDEX_REAL_TYPE]
            config_cmd = '%s %s --run --root-dir %s --run-target %s --run-rev out' % (Util.PYTHON, self.GNP_SCRIPT, project_run_root_dir, real_name)
            if Util.HOST_OS == Util.LINUX:
                config_cmd += ' --run-mesa-rev %s' % self.args.run_mesa_rev
            run_args = self.os_targets[target_index][self.TARGET_INDEX_RUN_ARGS]
            virtual_names_to_remove = []
            for tmp_virtual_name in self.VIRTUAL_NAME_INFO:
                if self.VIRTUAL_NAME_INFO[tmp_virtual_name][self.VIRTUAL_NAME_INFO_INDEX_REAL_TYPE] == 'gtest_angle':
                    virtual_names_to_remove.append(tmp_virtual_name)
            for i, run_arg in reversed(list(enumerate(run_args))):
                if run_arg.startswith('--extra-browser-args'):
                    run_arg = run_arg.replace('--extra-browser-args=', '').replace('--enable-logging=stderr ', '')
                    run_args[i] = '--extra-browser-args=\\\"%s --disable-backgrounding-occluded-windows\\\"' % run_arg
                elif run_arg == '--browser=release_x64':
                    run_args[i] = '--browser=release'
                elif run_arg.startswith('--gtest-benchmark-name') or run_arg.startswith('--git-revision'):
                    run_args.remove(run_arg)
                elif run_arg in ['-v', '--show-stdout', '--print-test-stdout']:
                    run_args.remove(run_arg)
                elif run_arg in virtual_names_to_remove:
                    run_args.remove(run_arg)
                elif run_arg == '--target=Release_x64':
                    run_args[i] = '--target=release'
            if virtual_name == 'angle_end2end_tests' and not args.dryrun:
                if Util.HOST_OS == Util.WINDOWS:
                    run_args.append('--gtest_filter=*D3D11*')
                elif Util.HOST_OS == Util.LINUX:
                    run_args.append('--gtest_filter=*OpenGL*:*Vulkan*')
            if virtual_name in ['info_collection_tests', 'trace_test']:
                _, _, _, gpu_device_id = Util.get_gpu_info()
                if virtual_name == 'info_collection_tests' and gpu_device_id not in run_args:
                    run_args += ['--expected-device-id', gpu_device_id]
                # All hardware support overlay config for Intel devices
                # Json format: https://source.chromium.org/chromium/chromium/src/+/main:content/test/gpu/gpu_tests/overlay_support.py;l=476
                overlay_config_json = f'{project_run_root_dir}/out/{self.build_type_cap}/{gpu_device_id}.json'
                if not os.path.exists(overlay_config_json):
                    overlay_config_json_content = {
                        "0x8086": {
                            f"0x{gpu_device_id}": [
                                {
                                    "function": "WithDirectComposition"
                                },
                                {
                                    "function": "WithHardwareNV12Support"
                                },
                                {
                                    "function": "WithHardwareYUY2Support"
                                },
                                {
                                    "function": "WithHardwareBGRA8Support"
                                },
                                {
                                    "function": "WithZeroCopyConfig",
                                    "args": {
                                        "supports_scaled_video": False,
                                        "supported_codecs": [
                                            "H264", "VP9"
                                        ]
                                    }
                                }
                            ],
                        },
                    }
                    with open(overlay_config_json, 'w', encoding='utf-8') as outfile:
                        json.dump(overlay_config_json_content, outfile)
                run_args += ['--extra-overlay-config-json', overlay_config_json]

            config_args = ''
            if run_args:
                config_args = ' '.join(run_args)

            real_type_extra_args = self.REAL_TYPE_INFO[real_type][self.REAL_TYPE_INFO_INDEX_EXTRA_ARGS]
            if real_type_extra_args:
                config_args += ' %s' % real_type_extra_args
            if len(self.VIRTUAL_NAME_INFO[virtual_name]) > self.VIRTUAL_NAME_INFO_INDEX_EXTRA_ARGS:
                virtual_name_extra_args = self.VIRTUAL_NAME_INFO[virtual_name][self.VIRTUAL_NAME_INFO_INDEX_EXTRA_ARGS]
                if virtual_name_extra_args:
                    config_args += ' %s' % virtual_name_extra_args

            dryrun_cond = self.VIRTUAL_NAME_INFO[virtual_name][self.VIRTUAL_NAME_INFO_INDEX_DRYRUN]
            if args.dryrun and dryrun_cond:
                if real_type not in ['aquarium', 'webgpu_blink_web_tests']:
                    dryrun_cond = '*%s*' % dryrun_cond
                config_args += ' %s=%s' % (self.REAL_TYPE_INFO[real_type][self.REAL_TYPE_INFO_INDEX_FILTER], dryrun_cond)
            else:
                for skip_case in self.SKIP_CASES:
                    if Util.HOST_OS == skip_case[self.SKIP_CASES_INDEX_OS] and virtual_name == skip_case[self.SKIP_CASES_INDEX_VIRTUAL_NAME] and len(skip_case) == self.SKIP_CASES_INDEX_CASES + 1:
                        config_args += ' %s=-%s' % (self.REAL_TYPE_INFO[real_type][self.REAL_TYPE_INFO_INDEX_FILTER], skip_case[self.SKIP_CASES_INDEX_CASES])

            if real_type in ['telemetry_gpu_integration_test', 'webgpu_blink_web_tests']:
                shard_count_arg = '--total-shards'
                shard_index_arg = '--shard-index'
                output_arg = '--write-full-results-to'
            elif real_type in ['gtest_chrome']:
                output_arg = '--test-launcher-summary-output'

            shard_count = int(self.os_targets[target_index][self.TARGET_INDEX_SHARD_COUNT])
            if real_type in ['gtest_angle', 'gtest_chrome']:
                shard_count = 1

            for shard_index in range(shard_count):
                shard_args = ''
                op = '%s' % target_index

                if shard_count > 1:
                    shard_args += ' %s=%s %s=%s' % (shard_count_arg, shard_count, shard_index_arg, shard_index)
                    shard_count_str = str(shard_count)
                    shard_count_str_len = len(shard_count_str)
                    op += '-shard%s' % str(shard_index).zfill(shard_count_str_len)
                op += '-%s' % virtual_name
                result_file = '%s/%s%s' % (self.result_dir, op, self.RESULT_FILE_SUFFIX)

                if real_type in ['aquarium']:
                    shard_args += ' > %s' % result_file
                elif real_type in ['gtest_chrome', 'telemetry_gpu_integration_test']:
                    shard_args += ' %s=%s' % (output_arg, result_file)
                    Util.ensure_file(result_file)

                cmd = '%s --run-args="%s%s"' % (config_cmd, config_args, shard_args)
                timer = Timer()
                self._execute(cmd, exit_on_error=False)
                self._log_exec(timer.stop(), 'Run %s' % op, cmd)

                if real_type in ['gtest_angle', 'webgpu_blink_web_tests']:
                    if real_type == 'gtest_angle':
                        output_file = '%s/out/%s/output%s' % (project_run_root_dir, self.build_type_cap, self.RESULT_FILE_SUFFIX)
                    elif real_type == 'webgpu_blink_web_tests':
                        output_file = '%s/out/%s/layout-test-results/full_results%s' % (project_run_root_dir, self.build_type_cap, self.RESULT_FILE_SUFFIX)
                    if os.path.exists(output_file):
                        shutil.move(output_file, result_file)
                    else:
                        Util.ensure_file(result_file)
                if args.dryrun and not args.dryrun_with_shard:
                    break

        self._log_exec(all_timer.stop(), 'Total Run')

    def batch(self):
        self.sync()
        self.build()
        self.run()

    def _report(self):
        html = '''<head>
  <meta http-equiv="content-type" content="text/html; charset=windows-1252">
  <style type="text/css">
    table {
      border: 2px solid black;
      border-collapse: collapse;
      border-spacing: 0;
      text-align: left;
    }
    table tr td {
      border: 1px solid black;
      vertical-align: top;
    }
  </style>
</head>
<body>
  <h2>Overall</h2>
    <ul>'''
        for line in open(self.exec_log):
            fields = line.rstrip('\n').split(self.SEPARATOR)
            name = fields[0]
            if not re.match('run', name, re.I):
                html += '''
      <li>%s: %s</li>''' % (name, fields[1])
        html += '''
      <li>Report: %s</li>
    </ul>''' % self.timestamp

        has_details = False
        details_html = '''
  <h2>Details</h2>
  <table>
    <tr>
      <td><strong>Name</strong>  </td>
      <td><strong>Time</strong></td>
      <td><strong>PASS_FAIL</strong></td>
      <td><strong>FAIL_PASS</strong></td>
      <td><strong>FAIL_FAIL</strong></td>
      <td><strong>PASS_PASS</strong></td>
    </tr>'''

        regression_count = 0
        for line in open(self.exec_log):
            fields = line.split(self.SEPARATOR)
            name = fields[0]
            if re.match('run', name, re.I):
                has_details = True
                op = name[4:]
                result_file = '%s/%s%s' % (self.result_dir, op, self.RESULT_FILE_SUFFIX)
                result = self._parse_result(result_file)
                # Get virtual target name from the op string (12-shard0-webgpu_cts_tests for example)
                last_dash = op.rfind('-')
                virtual_name = op[last_dash + 1:]
                # Count the pass_fail number to fail_fail in dawn_end2end_tests_runsuppressed, because the suppressed tests are expected fail.
                # There may be regressions that will be calculated into fail_fail cases, but it doesn't matter, dawn_end2end_tests could cover
                # the regressions and we won't miss them. In dawn_end2end_tests_runsuppressed we only care about the fail_pass cases.
                if virtual_name == 'dawn_end2end_tests_runsuppressed':
                    result.fail_fail.extend(result.pass_fail)
                    result.pass_fail.clear()
                # Move expected failures from pass_fail to fail_fail except dawn_end2end_tests_runsuppressed
                else:
                    expectations = TestExpectation.LOCAL_EXPECTATIONS.get(virtual_name)
                    if expectations:
                        for test in reversed(result.pass_fail):
                            expectation = f'[ {Util.HOST_OS} ] {test}'
                            if expectation in expectations:
                                result.fail_fail.append(test)
                                result.pass_fail.remove(test)

                regression_count += len(result.pass_fail)
                time = fields[1]
                pass_fail_info = '%s<p>%s' % (len(result.pass_fail), '<p>'.join(result.pass_fail[:self.MAX_FAIL_IN_REPORT]))
                fail_pass_info = '%s<p>%s' % (len(result.fail_pass), '<p>'.join(result.fail_pass[:self.MAX_FAIL_IN_REPORT]))
                fail_fail_info = len(result.fail_fail)
                if re.search('aquarium', op) and result.pass_pass:
                    pass_pass_info = '%s<p>%s' % (len(result.pass_pass), '<p>'.join(result.pass_pass[:self.MAX_FAIL_IN_REPORT]))
                else:
                    pass_pass_info = len(result.pass_pass)

                if result.pass_fail:
                    color = 'red'
                else:
                    color = 'green'
            else:
                continue

            details_html += '''
    <tr style="color:%s">
      <td>%s</td>
      <td>%s</td>
      <td>%s</td>
      <td>%s</td>
      <td>%s</td>
      <td>%s</td>
    </tr>''' % (color, name, time, pass_fail_info, fail_pass_info, fail_fail_info, pass_pass_info)

        details_html += '''
  </table>'''

        if has_details:
            html += details_html
        html += '''
</body>'''
        report_file = '%s/report.html' % self.result_dir
        Util.ensure_nofile(report_file)
        Util.append_file(report_file, html)
        subject = 'Regression %s' % regression_count

        self._send_email(subject, html)

    def _update_target(self):
        targets = []
        recorded_os_virtual_name = []
        if self.args.debug:
            recorded_virtual_name = []

        for project in self.projects:
            if self.args.location == 'source':
                config_dir = self.PROJECT_INFO[project][self.PROJECT_INFO_INDEX_ROOT_DIR]
            else:
                relative_path = '%s/%s' % (self.GPUTEST_FOLDER, project)
                if self.args.location == 'local':
                    rev_name, _, _ = Util.get_local_backup(relative_path, 'latest')
                elif self.args.location == 'remote':
                    rev_name, _, _ = Util.get_server_backup(relative_path, 'latest')

                config_dir = '%s/%s/%s' % (Util.BACKUP_DIR, relative_path, rev_name)

            if project == 'aquarium':
                os_backends = {
                    Util.WINDOWS: ['d3d12', 'dawn_d3d12', 'dawn_vulkan'],
                    Util.LINUX: ['dawn_vulkan']
                }
                for os in os_backends:
                    for backend in os_backends[os]:
                        targets.append([os, 'aquarium', 'aquarium_%s' % backend, 'aquarium', 'aquarium', ['--test-time 30', '--num-fish 30000', '--enable-msaa', '--turn-off-vsync', '--integrated-gpu', '--window-size=1920,1080', '--print-log', '--backend %s' % backend], 1])
                continue

            # projects other than Aquarium
            config_files = self.PROJECT_INFO[project][self.PROJECT_INFO_INDEX_CONFIG_FILES]
            for config_file in config_files:
                config_file = '%s/%s' % (config_dir, config_file)
                configs = Util.load_json(config_file)
                for config in configs:
                    if not re.search('intel', config, re.IGNORECASE):
                        continue
                    if re.search('angle-chromium', config):
                        continue

                    if re.search('linux', config, re.IGNORECASE):
                        target_os = Util.LINUX
                    elif re.search('win10', config, re.IGNORECASE):
                        target_os = Util.WINDOWS
                    else:
                        continue

                    if self.args.debug:
                        Util.debug(config)

                    target_types = configs[config]
                    for target_type in target_types:
                        for target_detail in target_types[target_type]:
                            if 'name' in target_detail:
                                tmp_name = target_detail['name']
                            else:
                                tmp_name = ''
                            if 'test' in target_detail:
                                tmp_test = target_detail['test']
                            else:
                                tmp_test = ''
                            if 'isolate_name' in target_detail:
                                tmp_isolate_name = target_detail['isolate_name']
                            else:
                                tmp_isolate_name = ''

                            virtual_name = tmp_name or tmp_test
                            real_name = tmp_isolate_name or tmp_test or tmp_name

                            if virtual_name not in self.VIRTUAL_NAME_INFO.keys():
                                continue

                            if self.args.debug:
                                Util.debug(virtual_name)

                            if self.args.debug and virtual_name not in recorded_virtual_name:
                                recorded_virtual_name.append(virtual_name)

                            if [target_os, virtual_name] in recorded_os_virtual_name:
                                continue
                            else:
                                recorded_os_virtual_name.append([target_os, virtual_name])

                            # init
                            target = [0] * (self.TARGET_INDEX_MAX + 1)
                            target[self.TARGET_INDEX_OS] = target_os
                            target[self.TARGET_INDEX_PROJECT] = project
                            target[self.TARGET_INDEX_VIRTUAL_NAME] = virtual_name
                            target[self.TARGET_INDEX_REAL_NAME] = real_name
                            target[self.TARGET_INDEX_REAL_TYPE] = self.VIRTUAL_NAME_INFO[virtual_name][self.VIRTUAL_NAME_INFO_INDEX_REAL_TYPE]
                            if 'args' in target_detail:
                                target_run_args = target_detail['args']
                            else:
                                target_run_args = []
                            target[self.TARGET_INDEX_RUN_ARGS] = target_run_args
                            if 'swarming' in target_detail and 'shards' in target_detail['swarming']:
                                target_shard_count = target_detail['swarming']['shards']
                            else:
                                target_shard_count = 1
                            target[self.TARGET_INDEX_SHARD_COUNT] = target_shard_count
                            targets.append(target)

                            # dawn_end2end_tests suppressed tests
                            if target[self.TARGET_INDEX_VIRTUAL_NAME] == 'dawn_end2end_tests':
                                target_runsuppressed = [0] * (self.TARGET_INDEX_MAX + 1)
                                target_runsuppressed[self.TARGET_INDEX_OS] = target_os
                                target_runsuppressed[self.TARGET_INDEX_PROJECT] = 'chromium'
                                target_runsuppressed[self.TARGET_INDEX_VIRTUAL_NAME] = virtual_name + '_runsuppressed'
                                target_runsuppressed[self.TARGET_INDEX_REAL_NAME] = real_name
                                target_runsuppressed[self.TARGET_INDEX_REAL_TYPE] = self.VIRTUAL_NAME_INFO[virtual_name][self.VIRTUAL_NAME_INFO_INDEX_REAL_TYPE]
                                target_runsuppressed[self.TARGET_INDEX_RUN_ARGS] = target_run_args + ['--run-suppressed-tests', '--bot-mode']
                                target_runsuppressed[self.TARGET_INDEX_SHARD_COUNT] = target_shard_count
                                targets.append(target_runsuppressed)

        targets = sorted(targets, key=operator.itemgetter(self.TARGET_INDEX_OS, self.TARGET_INDEX_PROJECT, self.TARGET_INDEX_REAL_TYPE, self.TARGET_INDEX_VIRTUAL_NAME))
        Util.dump_json('%s/%s/config.json' % (ScriptRepo.IGNORE_DIR, self.GPUTEST_FOLDER), targets)
        self.targets = targets

        if self.args.debug:
            Util.debug(len(recorded_virtual_name))
            recorded_virtual_name = sorted(recorded_virtual_name)
            for virtual_name in recorded_virtual_name:
                Util.debug(virtual_name)
            for target in targets:
                Util.debug(target)

        target_os = self.target_os
        if target_os == 'default':
            target_os = Util.HOST_OS

        os_targets = []
        for target in self.targets:
            if target[self.TARGET_INDEX_OS] == target_os:
                os_targets.append(target)
        self.os_targets = os_targets

        target_indexes = []
        arg_target = self.args.target
        if arg_target == 'all':
            arg_target = '0-%d' % (len(self.os_targets) - 1)
        arg_targets = arg_target.split(',')
        for tmp_target in arg_targets:
            if '-' in tmp_target:
                tmp_targets = tmp_target.split('-')
                target_min = int(tmp_targets[0])
                target_max = int(tmp_targets[1])
                target_indexes.extend(range(target_min, target_max + 1))
            else:
                target_indexes.append(int(tmp_target))
        target_indexes = sorted(target_indexes)
        self.target_indexes = target_indexes

    def _log_exec(self, time, op, cmd=''):
        info = '%s%s%s' % (op, self.SEPARATOR, time)
        if cmd:
            info += '%s%s' % (self.SEPARATOR, cmd)
        Util.info(info)
        Util.append_file(self.exec_log, info)

    def _parse_result(self, result_file, verbose=False):
        file_name = os.path.basename(result_file)
        match = re.search(self.RESULT_FILE_PATTERN, file_name)
        virtual_name = match.group(1)

        real_type = self.VIRTUAL_NAME_INFO[virtual_name][self.VIRTUAL_NAME_INFO_INDEX_REAL_TYPE]

        return TestResult(result_file, real_type)

    def _send_email(self, subject, content=''):
        if self.args.email:
            subject = '[GPUTest] %s %s %s' % (Util.HOST_NAME, self.timestamp, subject)
            Util.send_email(subject, content, to=self.args.email_to, type='html')

if __name__ == '__main__':
    GPUTest()
