import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class BrowserPower:
    """Run Chrome tracing with system_power category to measure power consumption."""

    # Browser paths for different OS and channels
    BROWSER_PATHS = {
        'win32': {
            'chrome': {
                'stable': '{programfiles}/Google/Chrome/Application/chrome.exe',
                'beta': '{programfiles}/Google/Chrome Beta/Application/chrome.exe',
                'dev': '{programfiles}/Google/Chrome Dev/Application/chrome.exe',
                'canary': '{localappdata}/Google/Chrome SxS/Application/chrome.exe',
            },
            'edge': {
                'stable': '{programfiles}/Microsoft/Edge/Application/msedge.exe',
                'beta': '{programfiles}/Microsoft/Edge Beta/Application/msedge.exe',
                'dev': '{programfiles}/Microsoft/Edge Dev/Application/msedge.exe',
                'canary': '{localappdata}/Microsoft/Edge SxS/Application/msedge.exe',
            },
        },
        'darwin': {
            'chrome': {
                'stable': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                'beta': '/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta',
                'dev': '/Applications/Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev',
                'canary': '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
            },
            'edge': {
                'stable': '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                'beta': '/Applications/Microsoft Edge Beta.app/Contents/MacOS/Microsoft Edge Beta',
                'dev': '/Applications/Microsoft Edge Dev.app/Contents/MacOS/Microsoft Edge Dev',
                'canary': '/Applications/Microsoft Edge Canary.app/Contents/MacOS/Microsoft Edge Canary',
            },
        },
        'linux': {
            'chrome': {
                'stable': '/usr/bin/google-chrome-stable',
                'beta': '/usr/bin/google-chrome-beta',
                'dev': '/usr/bin/google-chrome-unstable',
                'canary': '/usr/bin/google-chrome-unstable',  # Linux doesn't have canary, use dev
            },
            'edge': {
                'stable': '/usr/bin/microsoft-edge-stable',
                'beta': '/usr/bin/microsoft-edge-beta',
                'dev': '/usr/bin/microsoft-edge-dev',
                'canary': '/usr/bin/microsoft-edge-dev',  # Linux doesn't have canary, use dev
            },
        },
    }

    DEBUG_PORT = 9222

    def __init__(self, parser):
        parser.add_argument('--browser', dest='browser', choices=['chrome', 'edge'], default='chrome',
                            help='browser type (default: chrome)')
        parser.add_argument('--channel', dest='channel', choices=['stable', 'beta', 'dev', 'canary'], default='stable',
                            help='browser channel (default: stable)')
        parser.add_argument('--url', dest='url', default='https://www.google.com',
                            help='website URL to load (default: https://www.google.com)')
        parser.add_argument('--duration', dest='duration', type=int, default=30,
                            help='run duration in seconds (default: 30)')
        parser.add_argument('--output', dest='output', default='',
                            help='output trace file path (default: browser_power_trace.json in out/log)')
        parser.add_argument('--repeat', dest='repeat', type=int, default=1,
                            help='number of times to repeat the test (default: 1)')
        parser.add_argument('--cooldown', dest='cooldown', type=int, default=30,
                            help='cooldown time in seconds between repeated runs (default: 30)')
        parser.add_argument('--browser-path', dest='browser_path', default='',
                            help='custom browser executable path (overrides --browser and --channel)')
        parser.add_argument('--user-data-dir', dest='user_data_dir', default='',
                            help='custom user data directory')
        parser.add_argument('--extra-browser-args', dest='extra_browser_args', default='',
                            help='extra browser arguments (comma-separated)')
        parser.add_argument('--method', dest='method', choices=['cdp', 'perfetto'], default='cdp',
                            help='tracing method: cdp (DevTools Protocol, default and recommended) or perfetto (command-line, experimental - may not produce output on all platforms)')

        parser.epilog = f'''
examples:
{sys.executable} {parser.prog} --browser chrome --channel canary --url https://example.com --duration 60
{sys.executable} {parser.prog} --browser edge --channel stable --url https://www.youtube.com --duration 120
{sys.executable} {parser.prog} --browser-path "C:/path/to/chrome.exe" --url https://example.com
{sys.executable} {parser.prog} --method cdp --repeat 3 --cooldown 60 --browser chrome --channel canary --url https://example.com
'''

        args = parser.parse_args()
        self.browser = args.browser
        self.channel = args.channel
        self.url = args.url
        self.duration = args.duration
        self.repeat = args.repeat
        self.cooldown = args.cooldown
        self.output = args.output
        self.browser_path = args.browser_path
        self.user_data_dir = args.user_data_dir
        self.extra_browser_args = args.extra_browser_args
        self.method = args.method

        self._run()

    def _get_browser_path(self):
        """Get the browser executable path based on OS, browser type and channel."""
        if self.browser_path:
            return self.browser_path

        host_os = sys.platform
        if host_os.startswith('linux'):
            host_os = 'linux'

        if host_os not in self.BROWSER_PATHS:
            logger.error(f'Unsupported OS: {host_os}')
            return None

        if self.browser not in self.BROWSER_PATHS[host_os]:
            logger.error(f'Unsupported browser: {self.browser} on {host_os}')
            return None

        if self.channel not in self.BROWSER_PATHS[host_os][self.browser]:
            logger.error(f'Unsupported channel: {self.channel} for {self.browser} on {host_os}')
            return None

        path = self.BROWSER_PATHS[host_os][self.browser][self.channel]

        # Replace placeholders for Windows paths
        if host_os == 'win32':
            programfiles = os.getenv('PROGRAMFILES', 'C:\\Program Files')
            localappdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~') + '\\AppData\\Local')
            path = path.replace('{programfiles}', programfiles.replace('\\', '/'))
            path = path.replace('{localappdata}', localappdata.replace('\\', '/'))

        return path

    def _get_user_data_dir(self):
        """Get or create a user data directory for the browser session."""
        if self.user_data_dir:
            return os.path.normpath(self.user_data_dir)

        # Use a temporary directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        toolkit_dir = os.path.dirname(script_dir)
        user_data_dir = os.path.normpath(os.path.join(toolkit_dir, 'gitignore', 'browser_power_profile'))
        os.makedirs(user_data_dir, exist_ok=True)
        return user_data_dir

    def _get_output_path(self, iteration=1):
        """Get the output trace file path."""
        if self.output and self.repeat == 1:
            # Normalize to OS-native path separators for Chrome compatibility
            return os.path.normpath(self.output)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        toolkit_dir = os.path.dirname(script_dir)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        log_dir = os.path.join(toolkit_dir, 'gitignore', 'log')
        os.makedirs(log_dir, exist_ok=True)
        
        prefix = "browser_power_trace"
        if self.output:
            prefix = os.path.splitext(os.path.basename(self.output))[0]
            if os.path.dirname(self.output):
                log_dir = os.path.dirname(self.output)
                
        iter_suffix = f"_iter{iteration}" if self.repeat > 1 else ""
        output_path = os.path.normpath(os.path.join(log_dir, f'{prefix}_{timestamp}{iter_suffix}.json'))
        return output_path

    def _create_trace_config(self, trace_file):
        """Create a trace config file for system_power tracing."""
        # Chrome trace config format
        config = {
            "record_mode": "record-continuously",
            "included_categories": ["disabled-by-default-system_power"],
            "excluded_categories": ["*"],
            "memory_dump_config": {}
        }

        config_file = trace_file.replace('.json', '_config.json')
        with open(config_file, 'w') as f:
            json.dump(config, f)
        return config_file

    def _build_browser_command(self, browser_path, user_data_dir, trace_file=None):
        """Build the browser command with tracing arguments."""
        cmd = [browser_path]

        # Basic arguments
        cmd.extend([
            f'--user-data-dir={user_data_dir}',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-background-networking',
            '--disable-client-side-phishing-detection',
            '--disable-default-apps',
            '--disable-hang-monitor',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--disable-translate',
            '--metrics-recording-only',
            '--safebrowsing-disable-auto-update',
            # Enable remote debugging for DevTools Protocol access
            f'--remote-debugging-port={self.DEBUG_PORT}',
            '--remote-allow-origins=*',
            # Enable internal debugging pages (chrome://tracing, etc.)
            '--enable-logging',
            '--enable-gpu-benchmarking',
        ])

        # Add perfetto tracing arguments if using perfetto method
        if self.method == 'perfetto' and trace_file:
            config_file = self._create_trace_config(trace_file)
            
            # Use forward slashes for the path as Chrome may prefer this
            trace_file_fwd = trace_file.replace('\\', '/')
            config_file_fwd = config_file.replace('\\', '/')
            cmd.extend([
                '--enable-tracing',
                f'--trace-config-file={config_file_fwd}',
                f'--trace-startup-file={trace_file_fwd}',
                f'--trace-startup-duration={self.duration}',
                '--trace-startup-format=json',
            ])

        # Extra browser arguments
        if self.extra_browser_args:
            extra_args = self.extra_browser_args.split(',')
            for arg in extra_args:
                arg = arg.strip()
                if arg:
                    if not arg.startswith('--'):
                        arg = '--' + arg
                    cmd.append(arg)

        # URL to load
        cmd.append(self.url)

        return cmd

    def _wait_for_devtools(self, timeout=30):
        """Wait for DevTools to become available."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                url = f'http://127.0.0.1:{self.DEBUG_PORT}/json/version'
                with urllib.request.urlopen(url, timeout=2) as response:
                    return json.loads(response.read().decode('utf-8'))
            except Exception:
                time.sleep(0.5)
        return None

    def _get_browser_ws_url(self):
        """Get the browser WebSocket URL from DevTools."""
        try:
            url = f'http://127.0.0.1:{self.DEBUG_PORT}/json/version'
            with urllib.request.urlopen(url, timeout=5) as response:
                version_info = json.loads(response.read().decode('utf-8'))
                return version_info.get('webSocketDebuggerUrl')
        except Exception as e:
            logger.warning(f'Failed to get browser WebSocket URL: {e}')
        return None

    def _get_page_target(self):
        """Get the first page target from DevTools."""
        try:
            url = f'http://127.0.0.1:{self.DEBUG_PORT}/json'
            with urllib.request.urlopen(url, timeout=5) as response:
                targets = json.loads(response.read().decode('utf-8'))
                for target in targets:
                    if target.get('type') == 'page':
                        return target
        except Exception as e:
            logger.warning(f'Failed to get page target: {e}')
        return None

    def _run_tracing_cdp_internal(self, ws_url, duration, trace_file):
        """Run tracing using Chrome DevTools Protocol with a persistent connection."""
        try:
            import websocket
        except ImportError:
            logger.error('websocket-client package is required. Install with: pip install websocket-client')
            return False

        try:
            ws = websocket.create_connection(ws_url, timeout=duration + 30, suppress_origin=True)
            msg_id = 0

            def send_command(method, params=None):
                nonlocal msg_id
                msg_id += 1
                request = {'id': msg_id, 'method': method}
                if params:
                    request['params'] = params
                ws.send(json.dumps(request))
                return msg_id

            def wait_for_response(expected_id):
                while True:
                    response = json.loads(ws.recv())
                    if response.get('id') == expected_id:
                        return response
                    # Handle async events
                    if 'method' in response:
                        continue

            # Start tracing with power categories
            # Use system_power category which provides CPU Power, iGPU Power, Package Power (mW)
            trace_config = {
                'traceConfig': {
                    'includedCategories': [
                        'disabled-by-default-system_power',
                    ],
                    'recordMode': 'recordContinuously',
                }
            }

            logger.info('Sending Tracing.start command...')
            start_id = send_command('Tracing.start', trace_config)
            response = wait_for_response(start_id)

            if 'error' in response:
                logger.error(f'Failed to start tracing: {response["error"]}')
                ws.close()
                return False

            logger.info('Tracing started successfully')

            # Wait for the specified duration
            logger.info(f'Running for {duration} seconds...')
            time.sleep(duration)

            # Stop tracing
            logger.info('Stopping tracing...')
            end_id = send_command('Tracing.end')

            # Collect trace data chunks
            trace_data = []
            while True:
                response = json.loads(ws.recv())
                if response.get('method') == 'Tracing.dataCollected':
                    trace_data.extend(response.get('params', {}).get('value', []))
                elif response.get('method') == 'Tracing.tracingComplete':
                    logger.info('Tracing complete')
                    break
                elif response.get('id') == end_id:
                    if 'error' in response:
                        logger.error(f'Failed to stop tracing: {response["error"]}')
                        ws.close()
                        return False

            ws.close()

            if trace_data:
                # Save trace data to file
                trace_output = {'traceEvents': trace_data}
                with open(trace_file, 'w', encoding='utf-8') as f:
                    json.dump(trace_output, f)

                file_size = os.path.getsize(trace_file)
                logger.info(f'Trace file created: {trace_file} ({file_size} bytes)')
                return True
            else:
                logger.error('No trace data collected')
                return False

        except Exception as e:
            logger.error(f'Tracing failed: {e}')
            return False

    def _run(self):
        """Run the power measurement."""
        browser_path = self._get_browser_path()
        if not browser_path:
            return

        # Verify browser exists
        if not os.path.exists(browser_path):
            logger.error(f'Browser not found at: {browser_path}')
            return

        user_data_dir = self._get_user_data_dir()

        logger.info(f'Browser: {self.browser} ({self.channel})')
        logger.info(f'Browser path: {browser_path}')
        logger.info(f'URL: {self.url}')
        logger.info(f'Duration: {self.duration} seconds per iteration')
        logger.info(f'Iterations: {self.repeat}')
        logger.info(f'Tracing method: {self.method}')

        if self.method == 'perfetto':
            logger.warning('Perfetto method is experimental and may not produce trace output on all platforms. '
                           'Consider using --method cdp (default) for reliable results.')

        all_power_events = []
        trace_files = []

        for i in range(1, self.repeat + 1):
            if self.repeat > 1:
                logger.info(f'--- Starting iteration {i}/{self.repeat} ---')
                
            trace_file = self._get_output_path(iteration=i)
            trace_files.append(trace_file)
            
            logger.info(f'Trace output: {trace_file}')

            if self.method == 'perfetto':
                events = self._run_perfetto_tracing(browser_path, user_data_dir, trace_file)
            else:
                events = self._run_cdp_tracing(browser_path, user_data_dir, trace_file)
                
            if events:
                # Add iteration info to each event
                for event in events:
                    event['_iteration'] = i
                all_power_events.extend(events)
                
            if i < self.repeat:
                logger.info(f'Cooling down for {self.cooldown} seconds before next iteration...')
                time.sleep(self.cooldown)
                
        if all_power_events:
            try:
                # Generate final combined HTML report if multiple runs, otherwise just standard report
                if self.repeat > 1:
                    report_path = trace_files[0].replace(f'_iter1.json', '_combined_report.html')
                else:
                    report_path = trace_files[0].replace('.json', '_report.html')
                    
                self._generate_html_report(all_power_events, report_path, trace_files)
            except Exception as e:
                logger.error(f'Failed to generate final HTML report: {e}')

    def _run_perfetto_tracing(self, browser_path, user_data_dir, trace_file):
        """Run tracing using command-line flags (perfetto/trace-startup)."""
        # Build command with trace-startup flags
        cmd = self._build_browser_command(browser_path, user_data_dir, trace_file)
        logger.info('Starting browser with trace-startup...')
        logger.info(f'Command: {" ".join(cmd)}')

        process = None
        try:
            # Start the browser process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Wait for trace-startup-duration to complete
            # The trace file should be written after this duration
            logger.info(f'Waiting for trace-startup-duration ({self.duration} seconds)...')
            time.sleep(self.duration)

            # Give Chrome a bit more time to finalize the trace
            logger.info('Waiting for trace to finalize...')
            time.sleep(3)

            # Check if trace file was created before terminating
            if os.path.exists(trace_file):
                logger.info('Trace file detected, terminating browser...')
            else:
                logger.info('Trace file not yet created, waiting longer...')
                time.sleep(5)

            # Terminate the browser gracefully to flush trace
            logger.info('Terminating browser...')
            process.terminate()

            try:
                _, stderr = process.communicate(timeout=30)
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='ignore')
                    if stderr_text.strip() and 'ERROR' in stderr_text:
                        logger.warning(f'Browser stderr: {stderr_text[:500]}')
            except subprocess.TimeoutExpired:
                logger.warning('Browser did not terminate gracefully, killing...')
                process.kill()
                process.communicate()

            # Wait for trace file to be flushed
            time.sleep(3)

            # Check if trace file was created
            if os.path.exists(trace_file):
                file_size = os.path.getsize(trace_file)
                logger.info(f'Trace file created: {trace_file} ({file_size} bytes)')
                return self._analyze_trace(trace_file)
            else:
                logger.error(f'Trace file was not created: {trace_file}')
                # Check for trace files in other locations
                self._search_trace_files(user_data_dir)
                return []

        except Exception as e:
            logger.error(f'Error running browser: {e}')
            return []
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait()

    def _search_trace_files(self, user_data_dir):
        """Search for trace files in common locations."""
        search_paths = [
            user_data_dir,
            os.path.join(user_data_dir, 'Default'),
            os.environ.get('TEMP', ''),
            os.environ.get('LOCALAPPDATA', ''),
        ]
        logger.info('Searching for trace files...')
        for path in search_paths:
            if path and os.path.exists(path):
                for f in os.listdir(path):
                    if 'trace' in f.lower() and f.endswith('.json'):
                        logger.info(f'Found trace file: {os.path.join(path, f)}')

    def _run_cdp_tracing(self, browser_path, user_data_dir, trace_file):
        """Run tracing using Chrome DevTools Protocol."""
        # Build command without trace-startup flags
        cmd = self._build_browser_command(browser_path, user_data_dir, trace_file=None)
        logger.info('Starting browser...')
        logger.info(f'Command: {" ".join(cmd)}')

        process = None
        try:
            # Start the browser process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Wait for DevTools to be ready
            logger.info('Waiting for DevTools to be ready...')
            version_info = self._wait_for_devtools()
            if not version_info:
                logger.error('DevTools did not become available')
                return

            logger.info(f'Browser version: {version_info.get("Browser", "unknown")}')

            # Get the browser WebSocket URL for tracing
            ws_url = self._get_browser_ws_url()
            if not ws_url:
                logger.error('Could not get browser WebSocket URL')
                return

            # Run tracing with a persistent connection
            logger.info('Starting power tracing via DevTools Protocol...')
            if self._run_tracing_cdp_internal(ws_url, self.duration, trace_file):
                return self._analyze_trace(trace_file)
            else:
                logger.error('Tracing failed')
                return []

        except Exception as e:
            logger.error(f'Error running browser: {e}')
            return []
        finally:
            # Terminate the browser
            if process:
                logger.info('Terminating browser...')
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    def _analyze_trace(self, trace_file):
        """Analyze the trace file and print power-related information."""
        try:
            with open(trace_file, 'r', encoding='utf-8') as f:
                trace_data = json.load(f)

            # Get trace events
            if 'traceEvents' in trace_data:
                events = trace_data['traceEvents']
            elif isinstance(trace_data, list):
                events = trace_data
            else:
                events = []

            logger.info(f'Total trace events: {len(events)}')

            # Collect categories and look for power-related events
            categories = set()
            power_events = []
            event_names = set()

            for event in events:
                if isinstance(event, dict):
                    cat = event.get('cat', '')
                    name = event.get('name', '')
                    categories.add(cat)
                    event_names.add(name)
                    if 'power' in cat.lower() or 'power' in name.lower() or 'energy' in name.lower():
                        power_events.append(event)

            logger.info(f'Trace categories: {sorted(categories)}')
            logger.info(f'Unique event names: {len(event_names)}')
            logger.info(f'Power-related trace events: {len(power_events)}')

            if power_events:
                logger.info('Sample power events:')
                for event in power_events[:10]:  # Show first 10 events
                    logger.info(f'  - {event.get("name", "unknown")}: {event.get("args", {})}')
            else:
                logger.warning('No power events found. The system_power category may not be available on this platform.')
                logger.info('The trace file can still be viewed in chrome://tracing or https://ui.perfetto.dev/')
                
            return power_events

        except json.JSONDecodeError as e:
            logger.warning(f'Could not parse trace file as JSON: {e}')
            return []
        except Exception as e:
            logger.warning(f'Error analyzing trace: {e}')
            return []

    def _generate_html_report(self, power_events, html_path, trace_files):
        """Generate an HTML report summarizing power consumption across iterations."""
        import collections
        import math

        # Structure: metric_name -> iteration -> [values]
        iter_stats = collections.defaultdict(lambda: collections.defaultdict(list))
        global_stats = collections.defaultdict(list)

        has_iterations = self.repeat > 1

        for event in power_events:
            name = event.get('name')
            value = event.get('args', {}).get('value')
            iteration = event.get('_iteration', 1)

            if name and value is not None:
                iter_stats[name][iteration].append(value)
                global_stats[name].append(value)

        def _std_dev(values):
            if len(values) < 2:
                return 0.0
            mean = sum(values) / len(values)
            return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))

        def _median(values):
            s = sorted(values)
            n = len(s)
            if n % 2 == 1:
                return s[n // 2]
            return (s[n // 2 - 1] + s[n // 2]) / 2

        summary = []
        for name, values in global_stats.items():
            avg_val = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            std_val = _std_dev(values)
            med_val = _median(values)

            iter_data = {}
            if has_iterations:
                for it in range(1, self.repeat + 1):
                    it_values = iter_stats[name].get(it, [])
                    if it_values:
                        iter_data[it] = {
                            'avg': sum(it_values) / len(it_values),
                            'min': min(it_values),
                            'max': max(it_values),
                            'std': _std_dev(it_values),
                            'med': _median(it_values),
                            'count': len(it_values),
                        }
                    else:
                        iter_data[it] = {'avg': 0, 'min': 0, 'max': 0, 'std': 0, 'med': 0, 'count': 0}

            summary.append({
                'name': name,
                'avg': avg_val,
                'min': min_val,
                'max': max_val,
                'std': std_val,
                'med': med_val,
                'count': len(values),
                'iters': iter_data,
            })

        # Build per-iteration averages for chart data
        metric_names = [s['name'] for s in summary]
        chart_iter_data = {}
        if has_iterations:
            for it in range(1, self.repeat + 1):
                chart_iter_data[it] = [s['iters'].get(it, {}).get('avg', 0) for s in summary]

        # Color assignments per metric (up to 6)
        metric_colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']

        # Generate timestamp
        report_time = time.strftime('%Y-%m-%d %H:%M:%S')

        # ---- Build HTML ----
        html = []
        html.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Power Consumption Report</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --border: #475569;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --accent: #38bdf8;
    --accent2: #818cf8;
    --green: #34d399;
    --red: #f87171;
    --orange: #fb923c;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 0;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 0;
  }}
  header .container {{ padding-top: 0; padding-bottom: 0; }}
  h1 {{
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 4px;
  }}
  .subtitle {{ color: var(--text-dim); font-size: 14px; }}

  /* Info cards row */
  .info-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 24px 0;
  }}
  .info-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
  }}
  .info-card .info-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
    margin-bottom: 4px;
  }}
  .info-card .info-value {{
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    word-break: break-all;
  }}
  .info-card .info-value a {{
    color: var(--accent);
    text-decoration: none;
  }}
  .info-card .info-value a:hover {{ text-decoration: underline; }}

  /* Metric highlight cards */
  .metric-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin: 24px 0;
  }}
  .metric-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
  }}
  .metric-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
  }}
  .metric-card .mc-name {{
    font-size: 14px;
    color: var(--text-dim);
    margin-bottom: 12px;
    font-weight: 500;
  }}
  .metric-card .mc-avg {{
    font-size: 36px;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .metric-card .mc-unit {{
    font-size: 14px;
    color: var(--text-dim);
    font-weight: 400;
  }}
  .metric-card .mc-stats {{
    display: flex;
    gap: 16px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }}
  .mc-stat {{ flex: 1; }}
  .mc-stat-label {{ font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}
  .mc-stat-value {{ font-size: 15px; font-weight: 600; margin-top: 2px; }}
  .mc-stat-value.min {{ color: var(--green); }}
  .mc-stat-value.max {{ color: var(--red); }}
  .mc-stat-value.med {{ color: var(--orange); }}
  .mc-stat-value.std {{ color: var(--accent2); }}

  /* Section headers */
  .section-title {{
    font-size: 20px;
    font-weight: 600;
    margin: 36px 0 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}

  /* Bar chart */
  .chart-container {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin: 16px 0;
  }}
  .chart-row {{
    display: flex;
    align-items: center;
    margin-bottom: 8px;
  }}
  .chart-label {{
    width: 140px;
    font-size: 13px;
    color: var(--text-dim);
    flex-shrink: 0;
    text-align: right;
    padding-right: 16px;
  }}
  .chart-bar-group {{
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .chart-bar-wrap {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .chart-bar {{
    height: 22px;
    border-radius: 4px;
    transition: width 0.6s ease;
    min-width: 2px;
  }}
  .chart-bar-val {{
    font-size: 12px;
    color: var(--text-dim);
    white-space: nowrap;
  }}
  .chart-legend {{
    display: flex;
    gap: 16px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    flex-wrap: wrap;
  }}
  .chart-legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-dim);
  }}
  .chart-legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }}

  /* Detailed table */
  .table-wrap {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    margin: 16px 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th {{
    background: var(--surface2);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-dim);
    padding: 12px 16px;
    text-align: right;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
  }}
  th:first-child {{ text-align: left; }}
  td {{
    padding: 12px 16px;
    font-size: 14px;
    text-align: right;
    border-bottom: 1px solid rgba(71,85,105,0.4);
    font-variant-numeric: tabular-nums;
  }}
  td:first-child {{
    text-align: left;
    font-weight: 600;
    color: var(--text);
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(56,189,248,0.04); }}
  .iter-header {{ color: var(--accent) !important; }}

  /* Trace files */
  .trace-files {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 20px;
  }}
  .trace-files summary {{
    cursor: pointer;
    font-size: 14px;
    color: var(--text-dim);
    font-weight: 500;
  }}
  .trace-files ul {{
    margin-top: 8px;
    padding-left: 20px;
  }}
  .trace-files li {{
    font-size: 13px;
    color: var(--text-dim);
    padding: 2px 0;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
  }}

  footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-dim);
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>

<header>
<div class="container">
  <h1>Power Consumption Report</h1>
  <div class="subtitle">Browser power measurement via Chromium tracing</div>
</div>
</header>

<div class="container">

  <!-- Test Configuration -->
  <div class="info-grid">
    <div class="info-card">
      <div class="info-label">Browser</div>
      <div class="info-value">{self.browser.title()} ({self.channel})</div>
    </div>
    <div class="info-card">
      <div class="info-label">URL</div>
      <div class="info-value"><a href="{self.url}" target="_blank">{self.url}</a></div>
    </div>
    <div class="info-card">
      <div class="info-label">Duration</div>
      <div class="info-value">{self.duration}s &times; {self.repeat} run{"s" if self.repeat > 1 else ""}</div>
    </div>
    <div class="info-card">
      <div class="info-label">Cooldown</div>
      <div class="info-value">{self.cooldown}s between runs</div>
    </div>
    <div class="info-card">
      <div class="info-label">Total Samples</div>
      <div class="info-value">{len(power_events):,}</div>
    </div>
    <div class="info-card">
      <div class="info-label">Generated</div>
      <div class="info-value">{report_time}</div>
    </div>
  </div>

  <!-- Metric highlight cards -->
  <div class="section-title">Overview</div>
  <div class="metric-cards">
""")
        for idx, stat in enumerate(summary):
            color = metric_colors[idx % len(metric_colors)]
            html.append(f"""    <div class="metric-card" style="--mc-color: {color}">
      <style>.metric-card:nth-child({idx + 1})::before {{ background: {color}; }}</style>
      <div class="mc-name">{stat['name']}</div>
      <div class="mc-avg" style="color: {color}">{stat['avg']:,.1f} <span class="mc-unit">mW avg</span></div>
      <div class="mc-stats">
        <div class="mc-stat"><div class="mc-stat-label">Min</div><div class="mc-stat-value min">{stat['min']:,}</div></div>
        <div class="mc-stat"><div class="mc-stat-label">Max</div><div class="mc-stat-value max">{stat['max']:,}</div></div>
        <div class="mc-stat"><div class="mc-stat-label">Median</div><div class="mc-stat-value med">{stat['med']:,.1f}</div></div>
        <div class="mc-stat"><div class="mc-stat-label">Std Dev</div><div class="mc-stat-value std">{stat['std']:,.1f}</div></div>
      </div>
    </div>
""")

        html.append("  </div>\n")

        # ---- Bar Chart (per-iteration comparison) ----
        if has_iterations:
            # Find global max for scaling bars
            all_avgs = []
            for it_data in chart_iter_data.values():
                all_avgs.extend(it_data)
            chart_max = max(all_avgs) if all_avgs else 1

            iter_colors = []
            base_hues = [207, 167, 142, 262, 30, 174]  # blue, teal, green, purple, orange, cyan
            for i in range(self.repeat):
                h = base_hues[i % len(base_hues)]
                iter_colors.append(f'hsl({h}, 70%, 60%)')

            html.append("""  <div class="section-title">Per-Iteration Comparison</div>
  <div class="chart-container">
""")
            for m_idx, m_name in enumerate(metric_names):
                html.append(f'    <div class="chart-row">\n')
                html.append(f'      <div class="chart-label">{m_name}</div>\n')
                html.append(f'      <div class="chart-bar-group">\n')
                for it in range(1, self.repeat + 1):
                    val = chart_iter_data[it][m_idx]
                    pct = (val / chart_max * 100) if chart_max > 0 else 0
                    html.append(f'        <div class="chart-bar-wrap"><div class="chart-bar" style="width:{pct:.1f}%;background:{iter_colors[it-1]}"></div><div class="chart-bar-val">{val:,.1f} mW</div></div>\n')
                html.append(f'      </div>\n')
                html.append(f'    </div>\n')

            html.append('    <div class="chart-legend">\n')
            for it in range(1, self.repeat + 1):
                html.append(f'      <div class="chart-legend-item"><div class="chart-legend-dot" style="background:{iter_colors[it-1]}"></div>Run {it}</div>\n')
            html.append('    </div>\n')
            html.append('  </div>\n')

        # ---- Detailed data table ----
        html.append('  <div class="section-title">Detailed Statistics</div>\n')
        html.append('  <div class="table-wrap">\n  <table>\n    <thead>\n      <tr>\n')
        html.append('        <th>Metric</th><th>Average</th><th>Median</th><th>Min</th><th>Max</th><th>Std Dev</th><th>Samples</th>\n')
        if has_iterations:
            for it in range(1, self.repeat + 1):
                html.append(f'        <th class="iter-header">Run {it} Avg</th>\n')
        html.append('      </tr>\n    </thead>\n    <tbody>\n')

        for stat in summary:
            html.append(f'      <tr>\n')
            html.append(f'        <td>{stat["name"]}</td>\n')
            html.append(f'        <td>{stat["avg"]:,.2f}</td>\n')
            html.append(f'        <td>{stat["med"]:,.1f}</td>\n')
            html.append(f'        <td>{stat["min"]:,}</td>\n')
            html.append(f'        <td>{stat["max"]:,}</td>\n')
            html.append(f'        <td>{stat["std"]:,.1f}</td>\n')
            html.append(f'        <td>{stat["count"]:,}</td>\n')
            if has_iterations:
                for it in range(1, self.repeat + 1):
                    val = stat['iters'].get(it, {}).get('avg', 0)
                    html.append(f'        <td>{val:,.2f}</td>\n')
            html.append(f'      </tr>\n')

        html.append('    </tbody>\n  </table>\n  </div>\n')

        # ---- Per-iteration detail tables ----
        if has_iterations:
            html.append('  <div class="section-title">Per-Run Breakdown</div>\n')
            for it in range(1, self.repeat + 1):
                html.append(f'  <h3 style="font-size:15px;color:var(--accent);margin:16px 0 8px;">Run {it}</h3>\n')
                html.append('  <div class="table-wrap">\n  <table>\n    <thead>\n      <tr>\n')
                html.append('        <th>Metric</th><th>Average</th><th>Median</th><th>Min</th><th>Max</th><th>Std Dev</th><th>Samples</th>\n')
                html.append('      </tr>\n    </thead>\n    <tbody>\n')
                for stat in summary:
                    d = stat['iters'].get(it, {})
                    html.append(f'      <tr>\n')
                    html.append(f'        <td>{stat["name"]}</td>\n')
                    html.append(f'        <td>{d.get("avg",0):,.2f}</td>\n')
                    html.append(f'        <td>{d.get("med",0):,.1f}</td>\n')
                    html.append(f'        <td>{d.get("min",0):,}</td>\n')
                    html.append(f'        <td>{d.get("max",0):,}</td>\n')
                    html.append(f'        <td>{d.get("std",0):,.1f}</td>\n')
                    html.append(f'        <td>{d.get("count",0):,}</td>\n')
                    html.append(f'      </tr>\n')
                html.append('    </tbody>\n  </table>\n  </div>\n')

        # ---- Trace files ----
        html.append("""
  <details class="trace-files">
    <summary>Trace Files ({count})</summary>
    <ul>
      {items}
    </ul>
  </details>
""".format(count=len(trace_files),
           items="\n      ".join(f"<li>{os.path.basename(f)}</li>" for f in trace_files)))

        # ---- Footer ----
        html.append(f"""
  <footer>
    <span>Data source: Chromium <code>disabled-by-default-system_power</code> trace category</span>
    <span>{report_time}</span>
  </footer>

</div>
</body>
</html>
""")

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(''.join(html))

        logger.info(f'HTML Report created: {html_path}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Browser Power Measurement using Chrome Tracing',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    BrowserPower(parser)
