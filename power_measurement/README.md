# Browser Power Measurement

This folder contains the `measure_power.py` script, a standalone utility to measure power consumption while a webpage runs in your browser (specifically Chromium-based browsers like Chrome or Edge). It relies on underlying tracing mechanisms configured strictly to grab internal device power values during webpage execution.

## Requirements

- **Python 3.x**
- Chrome or Edge installed locally.
- For the standard `cdp` logging mode, **`websocket-client`** needs to be installed:
  ```bash
  pip install websocket-client
  ```

## Usage Quick Start

You can operate the script seamlessly through your command-line terminal providing various arguments based on targeted platforms.

```bash
# Basic run with default Chrome stable tracing "https://www.google.com" using Perfetto 
python measure_power.py

# Specify duration (in seconds), browser (chrome/edge), channel, and target URL via CDP method
python measure_power.py \
    --browser chrome \
    --channel canary \
    --url https://webglsamples.org/aquarium/aquarium.html \
    --duration 60 \
    --method cdp
```

## Advanced Command-line Arguments

- `--browser` Types: `chrome`, `edge` (Default is `chrome`)
- `--channel` Releases: `stable`, `beta`, `dev`, `canary` (Default is `stable`)
- `--url`: The target website to run performance sampling on 
- `--duration`: Integer seconds representing test span runtime
- `--method` choices:
    - **`perfetto`** (Default): Uses direct launch parameters (`--trace-startup`) allowing standard process tracking internally through trace-configs. Best for pure, detached start-to-finish log streams.
    - **`cdp`**: Utilizes Chrome DevTools Protocol to instantiate an active websocket connecting directly to the running webpage intercepting category traces programmatically.
- `--browser-path`: Run a custom browser executable location explicitly bypassing typical auto-discovery rules
- `--user-data-dir`: Isolate a separate custom profile directory ensuring test runs are non-interfering. If not supplied, an implicit temporary `out/browser_power_profile/` will be generated and utilized.

## Trace Outputs

Successfully populated trace log reports generally process and filter tracing metrics saving primarily to: `out/log/browser_power_trace_<timestamp>.json`. Upon conclusion, sampling values (such as CPU Power `(mW)`, Package Power `(mW)`, and iGPU Power `(mW)`) are written to standard output. 
Results can be richly visualized and audited by dropping the generated JSON artifact onto standard trace viewing UI's like [Perfetto UI](https://ui.perfetto.dev/) or `chrome://tracing`.