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


class Cros(Program):
    def __init__(self):
        parser = argparse.ArgumentParser(description='ChromeOS Script')

        parser.add_argument(
            '--board',
            dest='board',
            help='board, which can be amd64-generic, peppy for C720, link for pixel2013, samus for pixel2015, auron_yuna for C910',
            default='amd64-generic',
        )
        parser.add_argument('--image-type', dest='image_type', help='image type, can be dev or test', default='test')
        parser.add_argument('--init', dest='init', help='init', action='store_true')
        parser.add_argument('--delete', dest='delete', help='delete sdk', action='store_true')
        parser.add_argument('--sync', dest='sync', help='sync', action='store_true')
        parser.add_argument('--build', dest='build', help='build', action='store_true')
        parser.add_argument('--flash', dest='flash', help='flash', action='store_true')
        parser.add_argument('--chrome-dir', dest='chrome_dir', help='chrome dir', default='')
        parser.add_argument('--pkg', dest='pkg', help='pkg', default='')

        parser.epilog = '''
examples:
{0} {1} --board samus --sync --build
{0} {1} --board auron_yuna --chrome-dir /workspace/project/chromium --pkg chrome
'''.format(
            Util.PYTHON, parser.prog
        )

        python_ver = Util.get_python_ver()
        if python_ver[0] == 3:
            super().__init__(parser)
        else:
            super(Cros, self).__init__(parser)
        args = self.args

        self.board = args.board

        if args.init:
            self.init()
        if args.delete:
            self.delete()
        if args.sync:
            self.sync()
        if args.build:
            self.build()
        if args.flash:
            self.flash()

    def init(self):
        self._execute(
            'repo init -u https://chromium.googlesource.com/chromiumos/manifest.git --repo-url https://chromium.googlesource.com/external/repo.git'
        )
        Util.ensure_pkg('thin-provisioning-tools lvm2')

    def delete(self):
        self._execute('cros_sdk --delete')

    def sync(self):
        self._execute('repo sync --force-sync -j%s' % Util.CPU_COUNT)

    def workon(self):
        result = self._execute('cros_sdk -- cros_workon --board %s list' % board, return_out=True)
        if result[1]:
            cur_pkgs = result[1].strip('\n').split('\n')
        else:
            cur_pkgs = []

        if cur_pkgs and re.search('Generating locale-archive', cur_pkgs[0]):
            del cur_pkgs[0]
        stop_pkgs = Util.diff_list(cur_pkgs, pkgs)
        start_pkgs = Util.diff_list(pkgs, cur_pkgs)
        if stop_pkgs:
            cmd = 'cros_sdk -- cros_workon --board=%s stop %s' % (board, (' ').join(stop_pkgs))
            self._execute(cmd)
        if start_pkgs:
            cmd = 'cros_sdk'
            if CHROME_PKG in start_pkgs:
                if not chrome_dir:
                    error('chrome_dir should be designated')
                cmd += ' --chrome_root=' + chrome_dir
            cmd += ' -- cros_workon --board=%s start %s' % (board, (' ').join(start_pkgs))
            self._execute(cmd)

    def build(self):
        CHROME_PKG = 'chromeos-base/chromeos-chrome'
        MESA_PKG = 'media-libs/mesa'

        args = self.program.args
        board = self.board
        chrome_dir = args.chrome_dir

        pkgs = []
        if args.pkg:
            pkgs = args.pkg.split(',')
            for index, pkg in enumerate(pkgs):
                if pkg in ['chrome', 'chromeos-chrome']:
                    pkgs[index] = CHROME_PKG
                elif pkg in ['mesa']:
                    pkgs[index] = MESA_PKG
                else:
                    error('Package %s is not supported' % pkg)

        Util.info('== Environment ==')
        Util.info('BOARD: %s' % board)
        Util.info('Packages: %s' % (',').join(pkgs))
        Util.info('=================')

        if not os.path.exists('chroot/build/%s' % board):
            self._setup_board()

        # self._execute('cros_sdk -- ./enable_localaccount.sh wp')
        # self.workon()

        self._execute('cros_sdk -- ./build_packages --nowithautotest --board=%s --jobs=%s' % (board, Util.CPU_COUNT))
        # interactive=True will cause problem with build_image. Use interactive=False or replace tune2fs with older version
        if True:
            self._execute(
                'cros_sdk -- ./build_image --board=%s --jobs=%s --noenable_rootfs_verification %s'
                % (board, Util.CPU_COUNT, args.image_type)
            )
        else:
            copy_file(
                dir_share_linux_tool, 'tune2fs-1.42.13', dir_project_chromeos + '/chroot/sbin', 'tune2fs', is_sylk=True
            )
            self._execute(
                'cros_sdk -- ./build_image --board=%s --jobs=%s --noenable_rootfs_verification %s'
                % (board, Util.CPU_COUNT, args.image_type)
            )

    def flash(self):
        self._execute('cros_sdk -- cros flash usb:// --board=%s' % self.board)

    def _setup_board(self):
        self._execute('cros_sdk -- setup_board --force --board=%s' % self.board)


if __name__ == '__main__':
    Cros()
