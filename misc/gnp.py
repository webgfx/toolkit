import os
import platform
import re
import subprocess
import sys

HOST_OS = sys.platform
if HOST_OS == 'win32':
    lines = subprocess.Popen(
        'dir %s' % __file__.replace('/', '\\'), shell=True, stdout=subprocess.PIPE
    ).stdout.readlines()
    for line in lines:
        match = re.search(r'\[(.*)\]', line.decode('utf-8'))
        if match:
            script_dir = os.path.dirname(match.group(1)).replace('\\', '/')
            break
    else:
        script_dir = sys.path[0]
else:
    lines = subprocess.Popen('ls -l %s' % __file__, shell=True, stdout=subprocess.PIPE).stdout.readlines()
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


class Gnp(Program):
    BUILD_TARGET_DICT = {
        'angle_e2e': 'angle_end2end_tests',
        'angle_perf': 'angle_perftests',
        'angle_unit': 'angle_unittests',
        'dawn_e2e': 'dawn_end2end_tests',
        # For chrome drop
        'webgl_cts_tests': 'chrome/test:telemetry_gpu_integration_test',
        'webgpu_cts_tests': 'chrome/test:telemetry_gpu_integration_test',
    }
    BACKUP_TARGET_DICT = {
        'angle_e2e': 'angle_end2end_tests',
        'angle_perf': 'angle_perftests',
        'angle_unit': 'angle_unittests',
        'dawn_e2e': 'dawn_end2end_tests',
        'chrome': '//chrome:chrome',
        'chromedriver': '//chrome/test/chromedriver:chromedriver',
        'gl_tests': '//gpu:gl_tests',
        'vulkan_tests': '//gpu/vulkan:vulkan_tests',
        'telemetry_gpu_integration_test': '//chrome/test:telemetry_gpu_integration_test',
        'webgpu_blink_web_tests': '//:webgpu_blink_web_tests',
        # For chrome drop
        'webgl_cts_tests': '//chrome/test:telemetry_gpu_integration_test',
        'webgpu_cts_tests': '//chrome/test:telemetry_gpu_integration_test',
    }

    def __init__(self, parser):
        parser.add_argument('--project', dest='project', help='project')
        parser.add_argument('--dcheck', dest='dcheck', help='dcheck', action='store_true')
        parser.add_argument('--is-debug', dest='is_debug', help='is debug', action='store_true')

        parser.add_argument(
            '--is-official-build', dest='is_official_build', help='is official build', action='store_true'
        )
        parser.add_argument('--vulkan-only', dest='vulkan_only', help='gn args with vulkan only', action='store_true')

        parser.add_argument('--special-out-dir', dest='special_out_dir', help='special out dir', action='store_true')
        parser.add_argument('--rev', dest='rev', help='revision')
        parser.add_argument('--rev-stride', dest='rev_stride', help='rev stride', type=int, default=1)
        parser.add_argument('--symbol-level', dest='symbol_level', help='symbol level', type=int, default=-1)
        parser.add_argument('--batch', dest='batch', help='batch', action='store_true')
        parser.add_argument('--download', dest='download', help='download', action='store_true')

        parser.add_argument(
            '--disable-component-build',
            dest='disable_component_build',
            help='disable component build',
            action='store_true',
        )
        parser.add_argument(
            '--disable-warning-as-error',
            dest='disable_warning_as_error',
            help='disable warning as error',
            action='store_true',
        )
        parser.add_argument(
            '--disable-exit-on-error', dest='disable_exit_on_error', help='disable exit on error', action='store_true'
        )

        parser.add_argument('--sync', dest='sync', help='sync', action='store_true')
        parser.add_argument('--sync-reset', dest='sync_reset', help='do a reset before syncing', action='store_true')
        parser.add_argument('--sync-src-only', dest='sync_src_only', help='sync src only', action='store_true')
        parser.add_argument('--runhooks', dest='runhooks', help='runhooks', action='store_true')
        parser.add_argument('--makefile', dest='makefile', help='generate makefile', action='store_true')
        parser.add_argument('--remote', dest='remote', help='use distributed build system', action='store_true')
        parser.add_argument('--makefile-vs', dest='makefile_vs', help='generate visual studio sln', action='store_true')
        parser.add_argument('--build', dest='build', help='build', action='store_true')
        parser.add_argument(
            '--build-max-fail', dest='build_max_fail', help='build keeps going until N jobs fail', type=int, default=1
        )
        parser.add_argument('--build-target', dest='build_target', help='build target')
        parser.add_argument(
            '--build-verbose',
            dest='build_verbose',
            help='output verbose info. Find log at out/Release/.ninja_log',
            action='store_true',
        )
        parser.add_argument('--backup', dest='backup', help='backup', action='store_true')
        parser.add_argument('--backup-inplace', dest='backup_inplace', help='backup inplace', action='store_true')
        parser.add_argument('--backup-symbol', dest='backup_symbol', help='backup symbol', action='store_true')
        parser.add_argument('--backup-target', dest='backup_target', help='backup target')
        parser.add_argument('--upload', dest='upload', help='upload', action='store_true')
        parser.add_argument('--run', dest='run', help='run', action='store_true')
        parser.add_argument('--run-target', dest='run_target', help='run target')
        parser.add_argument('--run-output', dest='run_output', help='run output file')
        parser.add_argument('--run-args', dest='run_args', help='run args')
        parser.add_argument('--run-disabled', dest='run_disabled', help='run disabled cases', action='store_true')
        parser.add_argument('--run-filter', dest='run_filter', help='run filter', default='all')
        parser.add_argument('--run-rev', dest='run_rev', help='run rev', default='out')
        parser.add_argument('--run-mesa-rev', dest='run_mesa_rev', help='mesa revision', default='system')

        parser.epilog = '''
examples:
{0} {1} --sync --runhooks --makefile --build --backup --build --run --download
{0} {1} --backup --root-dir d:/workspace/chrome
{0} {1} --disable-component-build --symbol-level 2 --build --build-target chrome,chromedriver --backup --backup-target chrome,chromedriver --backup-symbol # debug
{0} {1} --target-os android --disable-component-build --sync --runhooks --build # android
'''.format(
            Util.PYTHON, parser.prog
        )

        python_ver = Util.get_python_ver()
        if python_ver[0] == 3:
            super().__init__(parser)
        else:
            super(Gnp, self).__init__(parser)
        args = self.args

        Util.prepend_path(Util.PROJECT_DEPOT_TOOLS_DIR)
        Util.prepend_path('%s:%s/python-bin' % (Util.PROJECT_DEPOT_TOOLS_DIR, Util.PROJECT_DEPOT_TOOLS_DIR))

        if args.project:
            project = args.project
        else:
            project = os.path.basename(self.root_dir)
            # handle repo chromium
            if project == 'src':
                project = os.path.basename(os.path.dirname(self.root_dir))
        if 'chromium' in project:
            project = 'chromium'
        elif 'chrome' in project:
            project = 'chromium'
        elif 'cr' in project:
            project = 'chromium'

        self.project = project

        if project == 'chromium':
            self.repo = ChromiumRepo(self.root_dir)
            self.backup_dir = '%s/backup' % os.path.dirname(self.root_dir)
        else:
            self.backup_dir = '%s/backup' % self.root_dir

        if args.is_debug:
            build_type = 'debug'
        else:
            build_type = 'release'
        self.build_type = build_type
        self.build_type_cap = build_type.capitalize()

        if args.symbol_level == -1:
            if args.is_debug:
                args.symbol_level = 2
            else:
                args.symbol_level = 0

        if self.args.special_out_dir:
            out_dir = Util.cal_relative_out_dir(
                self.target_arch, self.target_os, args.symbol_level, args.disable_component_build, args.dcheck
            )
        else:
            out_dir = 'out'
        # capitalize() is required by WebGPU CTS
        self.out_dir = '%s/%s' % (out_dir, self.build_type_cap)

        if self.project == 'angle':
            default_target = 'angle_e2e'
        elif self.project == 'chromium':
            if self.args.target_os == 'android':
                default_target = 'chrome_public_apk'
            else:
                default_target = 'chrome'
        elif self.project == 'dawn':
            default_target = 'dawn_e2e'
        else:
            default_target = ''
        self.default_target = default_target

        if args.disable_exit_on_error:
            self.exit_on_error = False
        else:
            self.exit_on_error = True

        if args.rev:
            if re.search('-', args.rev):
                tmp_revs = args.rev.split('-')
                min_rev = tmp_revs[0]
                max_rev = tmp_revs[1]
                if args.run:
                    Util.error('Cannot run with multiple revisions')
            else:
                min_rev = args.rev
                max_rev = args.rev

            if '.' in min_rev and '.' not in max_rev or '.' not in min_rev and '.' in max_rev:
                Util.error('min_rev and max_rev should be in same format')

            if '.' in min_rev:
                integer_rev = int(float(min_rev)) + 1
                self.integer_rev = integer_rev
                self.repo.get_info(integer_rev, integer_rev, 'main')
                roll_count = self.repo.info[ChromiumRepo.INFO_INDEX_REV_INFO][integer_rev][
                    ChromiumRepo.REV_INFO_INDEX_ROLL_COUNT
                ]
                if roll_count <= 1:
                    Util.error('Rev %s cannot be built as a roll')

                tmp_min = int(min_rev.split('.')[1])
                tmp_max = int(max_rev.split('.')[1])
                for i in range(tmp_min, min(tmp_max + 1, roll_count)):
                    self.rev = '%s.%s' % (min_rev.split('.')[0], i)
                    self.decimal_rev = i
                    self._handle_ops()
            else:
                min_rev = int(min_rev)
                max_rev = int(max_rev)
                tmp_rev = min_rev
                while tmp_rev <= max_rev:
                    if tmp_rev % args.rev_stride == 0:
                        self.rev = str(tmp_rev)
                        self.integer_rev = int(self.rev)
                        self.decimal_rev = 0
                        self._handle_ops()
                        tmp_rev += args.rev_stride
                    else:
                        tmp_rev += 1
        else:
            self.rev = ''
            self.integer_rev = 0
            self.decimal_rev = 0
            self._handle_ops()

    def sync(self):
        if self.project == 'chromium':
            if self.rev:
                Util.info('Begin to sync rev %s' % self.rev)

            if self.args.sync_reset:
                self._execute('git reset --hard HEAD && git clean -fd', exit_on_error=self.exit_on_error)

            if self.integer_rev:
                self.repo.get_info(self.integer_rev, self.integer_rev, 'main')
            self._chromium_sync_integer_rev()
            if not self.integer_rev:
                self.integer_rev = self.repo.get_working_dir_rev()
                self.repo.get_info(self.integer_rev, self.integer_rev, 'main')
            if self.decimal_rev:
                self._chromium_sync_decimal_rev()
        else:
            self._execute('git pull --no-recurse-submodules', exit_on_error=self.exit_on_error)
            self._execute_gclient(cmd_type='sync')

    def runhooks(self):
        self._execute_gclient(cmd_type='runhooks')

    def makefile(self):
        args = self.args

        if self.args.remote:
            cmd = f'autogn x64 {self.build_type} --use-remoteexec -o {self.build_type_cap}'
            self._execute(cmd, exit_on_error=self.exit_on_error)
            return

        # non remote
        if args.is_debug:
            gn_args = 'is_debug=true'
        else:
            gn_args = 'is_debug=false'

        if self.project != 'aquarium':
            if args.dcheck:
                gn_args += ' dcheck_always_on=true'
            else:
                gn_args += ' dcheck_always_on=false'

            if self.args.disable_component_build:
                gn_args += ' is_component_build=false'
            else:
                gn_args += ' is_component_build=true'

            if args.disable_warning_as_error:
                gn_args += ' treat_warnings_as_errors=false'
            else:
                gn_args += ' treat_warnings_as_errors=true'

            gn_args += ' symbol_level=%s' % self.args.symbol_level
            gn_args += ' is_clang=true'

        if self.project == 'chromium':
            if self.args.symbol_level == 0:
                gn_args += ' blink_symbol_level=0'

            # for windows, it has to use "" instead of ''
            if Util.HOST_OS == Util.WINDOWS:
                gn_args += ' ffmpeg_branding=\\\"Chrome\\\"'
            else:
                gn_args += ' ffmpeg_branding="Chrome"'

            gn_args += ' enable_nacl=false proprietary_codecs=true'
            if self.args.is_official_build:
                gn_args += ' is_official_build=true use_cfi_icall=false chrome_pgo_phase=0'

        if self.args.vulkan_only:
            if self.project == 'angle':
                # angle_enable_glsl=false angle_enable_essl=false angle_enable_hlsl=false
                gn_args += ' angle_enable_gl=false angle_enable_metal=false angle_enable_d3d9=false angle_enable_d3d11=false angle_enable_null=false'
            elif self.project == 'dawn':
                gn_args += (
                    ' dawn_enable_d3d12=false dawn_enable_metal=false dawn_enable_null=false dawn_enable_opengles=false'
                )

        if self.args.target_os == Util.ANDROID:
            if Util.HOST_OS == Util.WINDOWS:
                gn_args += ' target_os=\\\"android\\\" target_cpu=\\\"x64\\\"'
            else:
                gn_args += ' target_os="android" target_cpu="x64"'

        if self.project == 'dawn' and self.args.target_os == Util.WINDOWS:
            gn_args += ' dawn_dxc_enable_asserts_in_ndebug=false dawn_enable_desktop_gl=false dawn_enable_opengles=false dawn_use_x11=false dawn_enable_vulkan=false dawn_use_swiftshader=false'
            gn_args += ' tint_build_glsl_writer=false tint_build_glsl_validator=false tint_build_ir_binary=false tint_build_spv_reader=false'
            # Below gn args couldn't be set
            # gn_args += ' dawn_supports_glfw_for_windowing=false dawn_use_glfw=false dawn_use_windows_ui=false tint_build_cmd_tools=false tint_build_tests=false'

        quotation = Util.get_quotation()
        cmd = 'gn --args=%s%s%s' % (quotation, gn_args, quotation)
        if args.makefile_vs:
            cmd += ' --ide=vs'
        cmd += ' gen %s' % self.out_dir
        Util.ensure_dir(self.out_dir)
        Util.info('GN ARGS: {}'.format(gn_args))
        self._execute(cmd, exit_on_error=self.exit_on_error)

    def build(self):
        build_target = self.args.build_target
        if build_target:
            targets = build_target.split(',')
        else:
            targets = [self.default_target]

        for key, value in self.BUILD_TARGET_DICT.items():
            if key in targets:
                targets[targets.index(key)] = value

        if self.project == 'chromium':
            if self.rev:
                rev = self.rev
            else:
                rev = self.repo.get_working_dir_rev()
            Util.info('Begin to build rev %s' % rev)
            Util.chdir(self.root_dir + '/build/util')
            self._execute('%s lastchange.py -o LASTCHANGE' % Util.PYTHON, exit_on_error=self.exit_on_error)
            Util.chdir(self.root_dir)

        if self.args.remote:
            cmd = f'autoninja -C out/{self.build_type_cap} chrome'
        else:
            cmd = f'ninja -j{Util.CPU_COUNT} -k{self.args.build_max_fail} -C {self.out_dir} {" ".join(targets)}'
        if self.args.build_verbose:
            cmd += ' -v'
        self._execute(cmd, show_duration=True)

    def backup(self):
        if self.project == 'chromium':
            if self.rev:
                rev = self.rev
            else:
                rev = self.repo.get_working_dir_rev()
            rev_dir = Util.cal_backup_dir(rev)
        else:
            rev_dir = Util.cal_backup_dir()
        backup_path = '%s/%s' % (self.backup_dir, rev_dir)
        Util.ensure_dir(self.backup_dir)

        Util.info('Begin to backup %s' % rev_dir)
        if os.path.exists(backup_path) and not self.args.backup_inplace:
            Util.info('Backup folder "%s" alreadys exists' % backup_path)
            os.rename(backup_path, '%s-%s' % (backup_path, Util.get_datetime()))

        if self.args.backup_target:
            targets = self.args.backup_target.split(',')
        else:
            targets = [self.default_target]

        for key, value in self.BACKUP_TARGET_DICT.items():
            if key in targets:
                targets[targets.index(key)] = value

        for index, target in enumerate(targets):
            if target.startswith('angle'):
                targets[index] = '//src/tests:%s' % target
            elif target.startswith('dawn'):
                if self.project == 'chromium':
                    targets[index] = '//third_party/dawn/src/dawn/tests:%s' % target
                else:
                    targets[index] = '//src/dawn/tests:%s' % target

        tmp_files = []
        if self.project == 'aquarium':
            for tmp_file in os.listdir(self.out_dir):
                if os.path.isdir('%s/%s' % (self.out_dir, tmp_file)):
                    tmp_file += '/'
                tmp_files.append(tmp_file)
        else:
            for target in targets:
                target_files = (
                    self._execute(
                        'gn desc %s %s runtime_deps' % (self.out_dir, target),
                        exit_on_error=self.exit_on_error,
                        return_out=True,
                    )[1]
                    .rstrip('\n')
                    .split('\n')
                )
                tmp_files = Util.union_list(tmp_files, target_files)

        # 'gen/', 'obj/', '../../testing/test_env.py', '../../testing/location_tags.json', '../../.vpython'
        exclude_files = []
        if self.args.backup_target == 'dawn_e2e':
            # Even if we don't build them, they still show up from gn desc. So we need to remove them manually.
            exclude_files.extend(['../..', 'bin/', 'vk', 'vulkan', 'Vk', 'dbg', 'libEGL', 'libGLESv2', 'd3dcompiler_47'])

        src_files = []
        for tmp_file in tmp_files:
            tmp_file = tmp_file.rstrip('\r')
            if not self.args.backup_symbol and tmp_file.endswith('.pdb'):
                continue

            if tmp_file.startswith('./'):
                tmp_file = tmp_file[2:]

            if self.target_os == Util.CHROMEOS and not tmp_file.startswith('../../'):
                continue

            for exclude_file in exclude_files:
                if re.match(exclude_file, tmp_file):
                    break
            else:
                src_files.append('%s/%s' % (self.out_dir, tmp_file))

        if self.project == 'angle':
            src_files += [
                'out/%s/args.gn' % self.build_type_cap,
                'out/%s/../../infra/specs/angle.json' % self.build_type_cap,
            ]
        elif self.project == 'aquarium':
            src_files += ['assets/', 'shaders/']
        elif self.project == 'chromium':
            src_files += ['out/%s/args.gn' % self.build_type_cap]
            if Util.HOST_OS == Util.WINDOWS:
                src_files += [
                    'infra/config/generated/builders/try/dawn-win10-x64-deps-rel/targets/chromium.dawn.json',
                    'infra/config/generated/builders/try/gpu-fyi-try-win10-intel-rel-64/targets/chromium.gpu.fyi.json',
                ]
            elif Util.HOST_OS == Util.LINUX:
                src_files += [
                    'infra/config/generated/builders/try/dawn-linux-x64-deps-rel/targets/chromium.dawn.json',
                    'infra/config/generated/builders/try/gpu-fyi-try-linux-intel-rel/targets/chromium.gpu.fyi.json',
                ]

        src_file_count = len(src_files)
        for index, src_file in enumerate(src_files):
            dst_file = '%s/%s' % (backup_path, src_file)
            # dst_file can be subfolder of another dst_file, so only file can be skipped
            if self.args.backup_inplace and os.path.isfile(dst_file):
                Util.info(f'[{index + 1}/{src_file_count}] skip {dst_file}')
                continue
            Util.ensure_dir(os.path.dirname(dst_file))
            if os.path.isdir(src_file):
                dst_file = os.path.dirname(dst_file.rstrip('/'))
            cmd = 'cp -rf %s %s' % (src_file, dst_file)
            Util.info('[%s/%s] %s' % (index + 1, src_file_count, cmd))
            self._execute(cmd, exit_on_error=False, show_cmd=False)

            # permission denied
            # shutil.copyfile(file, dst_dir)

    def upload(self):
        if self.rev:
            rev = self.rev
        else:
            rev = 'latest'
        rev_name, _ = Util.get_backup_dir(self.backup_dir, rev)
        rev_dir = '%s/%s' % (self.backup_dir, rev_name)
        if Util.HOST_OS == Util.LINUX:
            rev_backup_file = '%s.tar.gz' % rev_dir
            if not os.path.exists(rev_backup_file):
                Util.chdir(self.backup_dir)
                Util.execute('tar zcf %s.tar.gz %s' % (rev_name, rev_name))
        elif Util.HOST_OS == Util.WINDOWS:
            rev_backup_file = '%s.zip' % rev_dir
            if not os.path.exists(rev_backup_file):
                shutil.make_archive(rev_dir, 'zip', rev_dir)

        relative_path = (
            self.root_dir[self.root_dir.index('project') + len('project') + 1 :].replace('\\', '/').replace('/src', '')
        )
        if Util.check_server_backup(relative_path, os.path.basename(rev_backup_file)):
            Util.info('Server already has rev %s' % rev_backup_file)
        else:
            Util.execute(
                'scp %s wp@%s:/workspace/backup/%s/%s/'
                % (rev_backup_file, Util.BACKUP_SERVER, Util.HOST_OS, relative_path)
            )

    def run(self):
        if Util.HOST_OS == Util.LINUX and self.args.run_mesa_rev == 'latest':
            Util.set_mesa(Util.PROJECT_MESA_BACKUP_DIR, self.args.run_mesa_rev)

        if self.args.run_rev == 'out':
            run_dir = self.out_dir
        else:
            rev_name, _ = Util.get_backup_dir('backup', self.args.run_rev)
            run_dir = 'backup/%s/out/%s' % (rev_name, self.build_type_cap)

        Util.chdir(run_dir, verbose=True)
        run_target = self.args.run_target
        if run_target:
            targets = run_target.split(',')
        else:
            targets = [self.default_target]

        for key, value in self.BUILD_TARGET_DICT.items():
            if key in targets:
                targets[targets.index(key)] = value

        for target in targets:
            self._run(target)

    def download(self):
        if not self.project == 'chromium':
            return

        rev = self.rev
        if not rev:
            Util.error('Please designate revision')

        download_dir = '%s/%s-%s/tmp' % (ScriptRepo.IGNORE_CHROMIUM_DOWNLOAD_DIR, self.target_arch, self.target_os)
        Util.ensure_dir(download_dir)
        Util.chdir(download_dir)

        if self.target_os == Util.DARWIN:
            target_arch_tmp = ''
        elif self.target_arch == 'x86_64':
            target_arch_tmp = '_x64'
        else:
            target_arch_tmp = ''

        if self.target_os == Util.WINDOWS:
            target_os_tmp = 'Win'
            target_os_tmp2 = 'win'
        elif self.target_os == Util.DARWIN:
            target_os_tmp = 'Mac'
            target_os_tmp2 = 'mac'
        else:
            target_os_tmp = self.target_os.capitalize()
            target_os_tmp2 = self.target_os

        rev_zip = '%s.zip' % rev
        if os.path.exists(rev_zip) and os.stat(rev_zip).st_size == 0:
            Util.ensure_nofile(rev_zip)
        if os.path.exists('../%s' % rev_zip):
            Util.info('%s has been downloaded' % rev_zip)
        else:
            # linux64: Linux_x64/<rev>/chrome-linux.zip
            # win64: Win_x64/<rev>/chrome-win32.zip
            # mac64: Mac/<rev>/chrome-mac.zip
            if self.target_os == Util.ANDROID:
                # https://commondatastorage.googleapis.com/chromium-browser-snapshots/index.html?prefix=Android/
                # https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Android%2F607944%2Fchrome-android.zip?generation=1542192867201693&alt=media
                archive_url = (
                    '"https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Android%2F'
                    + rev
                    + '%2Fchrome-android.zip?generation=1542192867201693&alt=media"'
                )
            else:
                archive_url = (
                    'http://commondatastorage.googleapis.com/chromium-browser-snapshots/%s%s/%s/chrome-%s.zip'
                    % (target_os_tmp, target_arch_tmp, rev, target_os_tmp2)
                )
            self._execute(
                '%s %s --show-progress -O %s' % (ScriptRepo.WGET_FILE, archive_url, rev_zip),
                exit_on_error=self.exit_on_error,
            )
            if os.path.getsize(rev_zip) == 0:
                Util.warning('Could not find revision %s' % rev)
                self._execute('rm %s' % rev_zip, exit_on_error=self.exit_on_error)
            else:
                self._execute('mv %s ../' % rev_zip, exit_on_error=self.exit_on_error)

    def batch(self):
        self.sync()
        self.runhooks()
        self.makefile()
        self.build()
        self.backup()
        self.run()

    def _execute_gclient(self, cmd_type, job_count=0, extra_cmd='', verbose=False):
        self._set_boto()
        cmd = 'gclient ' + cmd_type
        if extra_cmd:
            cmd += ' ' + extra_cmd
        if cmd_type == 'sync':
            cmd += ' -n -D --force -R'

        if not job_count:
            job_count = Util.CPU_COUNT
        cmd += ' -j%s' % job_count

        if verbose:
            cmd += ' -v'

        if self.args.proxy:
            Util.set_proxy(self.proxy_address, self.proxy_port)

        self._execute(cmd=cmd, exit_on_error=self.exit_on_error)

        if not Util.has_depot_tools_in_path() and os.path.exists(Util.PROJECT_DEPOT_TOOLS_DIR):
            Util.remove_path(Util.PROJECT_DEPOT_TOOLS_DIR)

    def _chromium_sync_integer_rev(self):
        if self.integer_rev:
            roll_repo = self.repo.info[ChromiumRepo.INFO_INDEX_REV_INFO][self.integer_rev][
                ChromiumRepo.REV_INFO_INDEX_ROLL_REPO
            ]
            if self.decimal_rev and not roll_repo:
                Util.error('Rev %s is not a roll' % self.integer_rev)

        tmp_hash = ''
        if self.integer_rev:
            working_dir_rev = self.repo.get_working_dir_rev()
            if working_dir_rev == self.integer_rev:
                return
            tmp_hash = self.repo.get_hash_from_rev(self.integer_rev, 'main')

        if tmp_hash:
            extra_cmd = '--revision src@' + tmp_hash
        else:
            self._execute('git pull --no-recurse-submodules', exit_on_error=self.exit_on_error)
            extra_cmd = ''

        if not self.args.sync_src_only:
            self._execute_gclient(cmd_type='sync', extra_cmd=extra_cmd)

    def _chromium_sync_decimal_rev(self):
        roll_repo = self.repo.info[ChromiumRepo.INFO_INDEX_REV_INFO][self.integer_rev][
            ChromiumRepo.REV_INFO_INDEX_ROLL_REPO
        ]
        roll_count = self.repo.info[ChromiumRepo.INFO_INDEX_REV_INFO][self.integer_rev][
            ChromiumRepo.REV_INFO_INDEX_ROLL_COUNT
        ]
        if roll_repo:
            if self.decimal_rev:
                if self.decimal_rev >= roll_count:
                    Util.error('The decimal part of rev cannot be greater or equal to %s' % roll_count)
            else:
                self.decimal_rev = roll_count
        else:
            if self.decimal_rev:
                Util.error('Rev %s is not a roll' % self.integer_rev)
            else:
                return

        roll_hash = self.repo.info[ChromiumRepo.INFO_INDEX_REV_INFO][self.integer_rev][
            ChromiumRepo.REV_INFO_INDEX_ROLL_HASH
        ]
        roll_count_diff = roll_count - self.decimal_rev
        if roll_count_diff < 0:
            Util.error('The decimal part of rev should be less than %s' % roll_count)
        Util.chdir('%s/%s' % (self.root_dir, roll_repo))
        cmd = 'git reset --hard %s~%s' % (roll_hash, roll_count_diff)
        self._execute(cmd, exit_on_error=self.exit_on_error)
        cmd = 'git rev-parse --abbrev-ref HEAD'
        branch = self._execute(cmd, show_cmd=False, exit_on_error=self.exit_on_error, return_out=True)[1].strip()
        if not branch == 'master':
            Util.error('Repo %s is not on master' % roll_repo)

    def _run(self, target):
        if target == 'telemetry_gpu_integration_test':
            cmd = 'vpython3 ../../content/test/gpu/run_gpu_integration_test.py'
        elif target == 'webgpu_blink_web_tests':
            cmd = 'bin/run_webgpu_blink_web_tests'
            if Util.HOST_OS == Util.WINDOWS:
                cmd += '.bat'
                # Workaround for content shell crash on Windows when building webgpu_blink_web_tests with is_official_build which is configured in makefile().
                # cmd += ' --additional-driver-flag=--disable-gpu-sandbox'
        else:
            cmd = '%s/%s%s' % (os.getcwd(), target, Util.EXEC_SUFFIX)
        if Util.HOST_OS == Util.WINDOWS:
            cmd = Util.format_slash(cmd)
        if self.args.run_disabled:
            cmd += ' --gtest_also_run_disabled_tests'
        if not self.args.run_filter == 'all':
            cmd += ' --gtest_filter=*%s*' % self.args.run_filter

        if self.args.run_args:
            cmd += ' %s' % self.args.run_args

        if Util.HOST_OS == Util.LINUX:
            if target == 'telemetry_gpu_integration_test':
                cmd += ' --browser=exact --browser-executable=./chrome'
            if target not in ['telemetry_gpu_integration_test', 'webgpu_blink_web_tests']:
                cmd = './' + cmd

        if target in ['angle_end2end_tests', 'angle_white_box_tests']:
            if 'test-launcher-bot-mode' not in cmd:
                cmd += ' --test-launcher-bot-mode'

        if target == 'dawn_end2end_tests':
            if 'exclusive-device-type-preference' not in cmd:
                cmd += ' --exclusive-device-type-preference=discrete,integrated'
            if Util.HOST_OS == Util.LINUX:
                cmd += ' --backend=vulkan'
            # for output, Chrome build uses --gtest_output=json:%s, standalone build uses --test-launcher-summary-output=%s

        self._execute(cmd, exit_on_error=self.exit_on_error)

    def _handle_ops(self):
        args = self.args
        if args.sync:
            self.sync()
        if args.runhooks:
            self.runhooks()
        if args.makefile:
            self.makefile()
        if args.build:
            self.build()
        if args.backup:
            self.backup()
        if args.upload:
            self.upload()
        if args.run:
            self.run()
        if args.batch:
            self.batch()
        if args.download:
            self.download()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GN Script')
    Gnp(parser)
