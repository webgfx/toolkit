#!/usr/bin/env python3
# pylint: disable=line-too-long, missing-function-docstring, missing-module-docstring, missing-class-docstring

import argparse
import os
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
            SCRIPT_DIR = os.path.dirname(match.group(1)).replace('\\', '/')
            break
    else:
        SCRIPT_DIR = sys.path[0]
else:
    lines = subprocess.Popen('ls -l %s' % __file__, shell=True, stdout=subprocess.PIPE).stdout.readlines()
    for line in lines:
        match = re.search(r'.* -> (.*)', line.decode('utf-8'))
        if match:
            SCRIPT_DIR = os.path.dirname(match.group(1))
            break
    else:
        SCRIPT_DIR = sys.path[0]

sys.path.append(SCRIPT_DIR)
sys.path.append(SCRIPT_DIR + '/..')

from util.base import Util


class WarpRegression:
    def __init__(self):
        parser = argparse.ArgumentParser(description='WARP Regression Test')
        parser.add_argument('--target', dest='target', help='target name (angle)', choices=['angle'], required=True)
        parser.add_argument('--run-filter', dest='run_filter', help='test filter', default='*')
        parser.add_argument('--email', dest='email', help='send email with results', action='store_true')

        parser.epilog = """
examples:
{0} {1} --target angle --run-filter "BufferDataTestES3.BufferResizing/*D3D11"
""".format(
            Util.PYTHON, parser.prog
        )

        args = parser.parse_args()
        self.target = args.target
        self.filter = args.run_filter
        self.send_email = args.email

        self.results = {
            'old': {'passed': 0, 'failed': 0, 'skipped': 0, 'failures': []},
            'new': {'passed': 0, 'failed': 0, 'skipped': 0, 'failures': []},
        }

    def _run_angle_test(self, warp_type):
        """Run angle_end2end_tests with specified WARP using webgfx.py --warp"""
        Util.info(f'Running angle_end2end_tests with {warp_type} WARP...')

        # Run webgfx.py with --warp option from d:\r
        run_dir = 'd:/r'
        cmd = f'python3.exe webgfx.py --target {self.target} --run --warp {warp_type}'
        if self.filter and self.filter != '*':
            cmd += f' --run-filter {self.filter}'

        Util.info(f'Running: {cmd} (in {run_dir})')

        # Run from d:\r directory
        original_dir = os.getcwd()
        os.chdir(run_dir)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
            output = result.stdout + result.stderr
            print(output)  # Display output

            # Parse the report output for PASS_FAIL failures
            self._parse_report_output(output, warp_type)
            self._display_run_report(output, warp_type)
        except subprocess.TimeoutExpired:
            Util.warning(f'Test timed out for {warp_type} WARP')
        except Exception as e:
            Util.warning(f'Error running test: {e}')
        finally:
            os.chdir(original_dir)

    def _parse_report_output(self, output, warp_type):
        """Parse the report output from webgfx.py to extract PASS_FAIL failures"""
        failures = []

        # Find [PASS_FAIL] section and extract test names
        in_pass_fail_section = False
        for line in output.split('\n'):
            line = line.strip()
            if line == '[PASS_FAIL]':
                in_pass_fail_section = True
                continue
            elif line.startswith('[') and line.endswith(']'):
                # Another section started, stop parsing PASS_FAIL
                in_pass_fail_section = False
                continue

            if in_pass_fail_section and line:
                # Each non-empty line in PASS_FAIL section is a test name
                failures.append(line)

        # Also parse summary line for counts: "PASS_FAIL X, FAIL_PASS Y, ..."
        summary_match = re.search(r'PASS_FAIL\s+(\d+)', output)
        if summary_match:
            self.results[warp_type]['failed'] = int(summary_match.group(1))
        else:
            self.results[warp_type]['failed'] = len(failures)

        # Parse PASS_PASS count
        pass_match = re.search(r'PASS_PASS\s+(\d+)', output)
        if pass_match:
            self.results[warp_type]['passed'] = int(pass_match.group(1))

        self.results[warp_type]['failures'] = failures

    def _display_run_report(self, output, warp_type):
        """Display report after each test run"""
        print('')
        print('=' * 60)
        print(f'{warp_type.upper()} WARP Test Results')
        print('=' * 60)
        print(f"Passed:  {self.results[warp_type]['passed']}")
        print(f"Failed:  {self.results[warp_type]['failed']}")
        print(f"Skipped: {self.results[warp_type]['skipped']}")

        if self.results[warp_type]['failures']:
            print('')
            print(f"Failed tests ({len(self.results[warp_type]['failures'])}):")
            for test in self.results[warp_type]['failures']:
                print(f'  {test}')
        print('=' * 60)
        print('')

    def _generate_report(self):
        """Generate comparison report"""
        report = []
        report.append('=' * 60)
        report.append('WARP Regression Test Report')
        report.append('=' * 60)
        report.append('')
        report.append(f'Target: {self.target}')
        report.append(f'Filter: {self.filter}')
        report.append('')
        report.append('-' * 60)
        report.append('Summary')
        report.append('-' * 60)
        report.append(f"{'':20} {'Old WARP':>15} {'New WARP':>15}")
        report.append(f"{'Passed':20} {self.results['old']['passed']:>15} {self.results['new']['passed']:>15}")
        report.append(f"{'Failed':20} {self.results['old']['failed']:>15} {self.results['new']['failed']:>15}")
        report.append(f"{'Skipped':20} {self.results['old']['skipped']:>15} {self.results['new']['skipped']:>15}")
        report.append('')

        # Find regressions (failures in new but not in old)
        old_failures = set(self.results['old']['failures'])
        new_failures = set(self.results['new']['failures'])

        regressions = new_failures - old_failures
        fixes = old_failures - new_failures

        if regressions:
            report.append('-' * 60)
            report.append(f'Regressions ({len(regressions)} tests failed in new WARP but passed in old):')
            report.append('-' * 60)
            for test in sorted(regressions):
                report.append(f'  {test}')
            report.append('')

        if fixes:
            report.append('-' * 60)
            report.append(f'Fixes ({len(fixes)} tests passed in new WARP but failed in old):')
            report.append('-' * 60)
            for test in sorted(fixes):
                report.append(f'  {test}')
            report.append('')

        report.append('=' * 60)

        return '\n'.join(report)

    def _send_email_report(self, report):
        """Send email with the report"""
        subject = f'WARP Regression Test Report - {self.target}'

        old_failures = set(self.results['old']['failures'])
        new_failures = set(self.results['new']['failures'])
        regressions = new_failures - old_failures

        if regressions:
            subject += f' - {len(regressions)} REGRESSIONS'
        else:
            subject += ' - No Regressions'

        Util.send_email(subject=subject, content=report)

    def run(self):
        """Run the regression test"""
        Util.info(f'Starting WARP regression test for: {self.target}')

        if self.target == 'angle':
            # Run with old WARP
            self._run_angle_test('old')

            # Run with new WARP
            self._run_angle_test('new')

        # Generate report
        report = self._generate_report()
        print(report)

        # Send email if requested
        if self.send_email:
            self._send_email_report(report)


if __name__ == '__main__':
    WarpRegression().run()
