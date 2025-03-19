import os
import re
import subprocess
import sys
lines = subprocess.Popen('dir %s' % __file__, shell=True, stdout=subprocess.PIPE).stdout.readlines()
for line in lines:
    match = re.search('\[(.*)\]', line.decode('utf-8'))
    if match:
        script_dir = os.path.dirname(match.group(1)).replace('\\', '/')
        break
else:
    script_dir = sys.path[0]

sys.path.append(script_dir)
sys.path.append(script_dir + '/..')

from util.base import * # pylint: disable=unused-wildcard-import

class Aquarium(Program):
    def __init__(self):
        parser = argparse.ArgumentParser(description='aquarium')
        parser.epilog='''
examples:
{0} {1} --roll
{0} {1} --sync --build --run
'''.format(Util.PYTHON, parser.prog)

        parser.add_argument('--sync', dest='sync', help='sync', action='store_true')
        parser.add_argument('--makefile', dest='makefile', help='makefile', action='store_true')
        parser.add_argument('--build', dest='build', help='build', action='store_true')
        parser.add_argument('--run', dest='run', help='run')
        parser.add_argument('--roll', dest='roll', help='roll', action='store_true')
        parser.add_argument('--roll-update', dest='roll_update', help='update related repos before roll', action='store_true')

        python_ver = Util.get_python_ver()
        if python_ver[0] == 3:
            super().__init__(parser)
        else:
            super(Aquarium, self).__init__(parser)

        self._handle_ops()

    def roll(self):
        repo_rev = {}

        # https://chromium.googlesource.com/chromium/src/build.git
        # https://chromium.googlesource.com/chromium/src/buildtools.git
        # https://chromium.googlesource.com/chromium/src/tools/clang.git
        # https://chromium.googlesource.com/chromium/src/third_party/googletest.git
        # https://chromium.googlesource.com/chromium/src/third_party/jinja2.git
        # https://chromium.googlesource.com/chromium/src/third_party/jsoncpp.git
        # https://android.googlesource.com/platform/external/libpng.git
        # https://chromium.googlesource.com/chromium/src/third_party/markupsafe.git
        # https://chromium.googlesource.com/chromium/src/testing.git
        # https://chromium.googlesource.com/chromium/src/third_party/zlib.git
        standalone_repos = ['build', 'buildtools', 'clang', 'googletest', 'jinja2', 'jsoncpp', 'libpng', 'markupsafe', 'testing', 'zlib']
        for repo in standalone_repos:
            repo_dir = '%s/%s' % (Util.PROJECT_DIR, repo)
            if not os.path.exists(repo_dir):
                Util.error('%s does not exist' % repo_dir)

            if self.args.roll_update:
                Util.chdir(repo_dir)
                Util.execute('git pull')

            Util.chdir(repo_dir)
            if repo in ['googletest', 'jsoncpp']:
                key = '%s_gn_revision' % repo
            else:
                key = '%s_revision' % repo
            repo_rev[key] = Util.get_working_dir_hash()

        chromium_repos = ['angle_revision', 'catapult_revision', 'dawn_revision', 'googletest_revision', 'gn_version', 'jsoncpp_revision', 'libcxx_revision', 'libcxxabi_revision', 'libunwind_revision', 'swiftshader_revision']
        chromium_dir = Util.PROJECT_CHROMIUM_DIR
        if self.args.roll_update:
            Util.chdir(chromium_dir)
            Util.execute('git pull')
        lines = open('%s/DEPS' % chromium_dir).readlines()
        for index, line in enumerate(lines):
            for repo in chromium_repos:
                match = re.search('\'%s\':\s+\'(.*)\'' % repo, line)
                if match:
                    repo_rev[repo] = match.group(1)
                    break

            if re.search('src/tools/clang/dsymutil', line):
                match = re.search('\'version\': \'(.*)\'', lines[index + 4])
                if match:
                    repo_rev['dsymutil_revision'] = match.group(1)

            match = re.search('glfw.git@\' \+\s+\'(.*)\'', line)
            if match:
                repo_rev['glfw_revision'] = match.group(1)

            if re.search('src/third_party/jsoncpp/source', line):
                match = re.search('\'@\' \+ \'(.*)\'', lines[index + 2])
                if match:
                    repo_rev['jsoncpp_revision'] = match.group(1)

            if re.search('src/third_party/libjpeg_turbo', line):
                match = re.search('\'@\' \+ \'(.*)\'', lines[index + 1])
                if match:
                    repo_rev['libjpeg_turbo_revision'] = match.group(1)

            if re.search('src/third_party/nasm', line):
                match = re.search('\'(.*)\'', lines[index + 2])
                if match:
                    repo_rev['nasm_revision'] = match.group(1)

            match = re.search('vulkan-deps@(.*)\'', line)
            if match:
                repo_rev['vulkan_deps_revision'] = match.group(1)

            if re.search('src/third_party/vulkan_memory_allocator', line):
                match = re.search('\'@\' \+ \'(.*)\'', lines[index + 1])
                if match:
                    repo_rev['vulkan_memory_allocator_revision'] = match.group(1)

        #print(repo_rev)

        repos = repo_rev.keys()
        for line in fileinput.input('%s/DEPS' % self.root_dir, inplace=1):
            for repo in repos:
                match = re.search('\'%s\': \'.*\',' % repo, line)
                if match:
                    line = '  \'%s\': \'%s\',\n' % (repo, repo_rev[repo])
                    break
            sys.stdout.write(line)
        fileinput.close()

        Util.execute('dos2unix %s/DEPS' % self.root_dir)

    def sync(self):
        cmd = '%s %s --root-dir %s --sync --runhooks' % (Util.PYTHON, self.GNP_SCRIPT, self.root_dir)
        Util.execute(cmd)

    def makefile(self):
        cmd = 'gn gen out/release --args="is_debug=false"'
        Util.execute(cmd)
        if Util.HOST_OS == Util.WINDOWS:
            cmd = 'gn gen out/anglerelease --args="is_debug=false enable_angle=true"'
            Util.execute(cmd)

    def build(self):
        cmd = 'ninja -C out/release aquarium'
        Util.execute(cmd)
        if Util.HOST_OS == Util.WINDOWS:
            cmd = 'ninja -C out/anglerelease aquarium'
            Util.execute(cmd)

    def run(self):
        cmd = 'out/release/aquarium --backend d3d12 --test-time 10'
        Util.execute(cmd)

        cmd = 'out/release/aquarium --backend dawn_d3d12 --test-time 10'
        Util.execute(cmd)

        if Util.HOST_OS == Util.WINDOWS:
            cmd = 'out/release/aquarium --backend angle_d3d11 --test-time 10'
            Util.execute(cmd)

    def _handle_ops(self):
        args = self.args
        if args.roll:
            self.roll()
        if args.sync:
            self.sync()
        if args.makefile:
            self.makefile()
        if args.build:
            self.build()
        if args.run:
            self.run()

if __name__ == '__main__':
    Aquarium()

