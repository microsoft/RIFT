# RIFT on macOS with IDA Pro 9.3+

This guide describes the supported macOS layout for the current RIFT branch. It was validated with IDA Pro 9.3 and applies to later IDA 9.x versions when their bundled Python and Qt APIs remain compatible.

RIFT has two runtimes:

1. The RIFT server and command-line tools use the full `requirements.txt` environment.
2. The IDA plugin runs inside IDA's Python process and must use IDA's bundled PySide6/Qt libraries.

Do not install RIFT's full requirements into a virtual environment activated by IDA. In particular, PySide6 from that environment can override IDA's bundled Qt libraries and cause `Symbol not found` errors in other plugins.

## Prerequisites

- macOS with IDA Pro 9.3 or later.
- `rustup` and `cargo` on `PATH`.
- IDA FLIRT tools `pcf` and `sigmake`. IDA Pro bundles them under `<IDA app>/Contents/MacOS/tools/flair/`.
- A dedicated analysis VM with no access to production networks or sensitive data. RIFT is intended for malware analysis.

The macOS system `strings` utility is sufficient for standalone file analysis. No Windows `strings.exe` is required.

The repository-level `rift_config.cfg` retains Windows-compatible defaults. The IDA plugin configuration below supplies the macOS-specific paths.

## Install the RIFT runtime

From the RIFT checkout, create a dedicated virtual environment and install the complete requirements there:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Keep this environment separate from any virtual environment configured through IDA's `idapythonrc.py`.

## Install the IDA plugin

Set `IDAUSR` to the IDA user directory used by the target IDA installation. The default on macOS is usually `$HOME/.idapro`:

```bash
export RIFT_ROOT="$(pwd)"
export IDAUSR="${IDAUSR:-$HOME/.idapro}"

mkdir -p "$IDAUSR/plugins/librift_ida" \
         "$IDAUSR/plugins/librift" \
         "$IDAUSR/plugins/rift_essentials" \
         "$RIFT_ROOT/work" \
         "$RIFT_ROOT/tmp" \
         "$RIFT_ROOT/Output"

cp plugins/ida/rift_plugin.py "$IDAUSR/plugins/rift_plugin.py"
cp plugins/ida/librift_ida/*.py "$IDAUSR/plugins/librift_ida/"
cp librift/*.py "$IDAUSR/plugins/librift/"
cp data/rustc_hashes.json "$IDAUSR/plugins/rift_essentials/rustc_hashes.json"
```

If IDA activates a user virtual environment, make only RIFT's non-Qt dependencies available to that environment:

```bash
"$IDAUSR/venv/bin/python" -m pip install \
  "ar==1.0.1" "lief==0.17.5" "requests==2.33.0"
```

Do not install `PySide6`, `PySide6_Addons`, `PySide6_Essentials`, or `shiboken6` into `$IDAUSR/venv`. IDA 9.3 supplies its compatible Qt 6.8 runtime.

## Configure the plugin

First identify the installed IDA application bundle. Its name includes the IDA version, so update this value when using a different release:

```bash
IDA_APP="/Applications/IDA Professional 9.3.app"
test -x "$IDA_APP/Contents/MacOS/tools/flair/pcf"
test -x "$IDA_APP/Contents/MacOS/tools/flair/sigmake"
```

Create `$IDAUSR/plugins/rift_essentials/rift_config.cfg` and replace `/path/to/RIFT` with the checkout location. The configuration file does not expand the `IDA_APP` shell variable, so enter the full application-bundle paths. For IDA 9.3, use:

```ini
[Default]
PcfPath = /Applications/IDA Professional 9.3.app/Contents/MacOS/tools/flair/pcf
SigmakePath = /Applications/IDA Professional 9.3.app/Contents/MacOS/tools/flair/sigmake
WorkFolder = /path/to/RIFT/work
CargoProjFolder = /path/to/RIFT/tmp
RustcHashes = /path/to/RIFT/data/rustc_hashes.json
StringsTool = /usr/bin/strings

[RiftServer]
server_mode = local
Ip = 127.0.0.1
Port = 5001
flirt_dir = /path/to/RIFT/ServerStorage
ApiKey =
TlsCert =
TlsKey =
TlsCaCert =
```

For another IDA release, replace `IDA Professional 9.3.app` in both FLIRT paths with the exact installed application-bundle name. The `WorkFolder` and `CargoProjFolder` directories must exist and be writable; the server creates `flirt_dir` when it starts. Keep the server in `local` mode and bound to localhost unless a specific isolated lab design requires remote access with API-key and TLS configuration.

## Start RIFT and use it from IDA

Start the server from the dedicated RIFT environment:

```bash
source .venv/bin/activate
python rift_server.py -o ./Output --cfg "$IDAUSR/plugins/rift_essentials/rift_config.cfg"
```

Verify it before opening the plugin:

```bash
curl http://127.0.0.1:5001/health
```

The response should report `status` as `healthy` and `worker_alive` as `true`.

Open the target Rust binary in the graphical IDA application, then select **Edit → Plugins → RIFT**. The plugin extracts the Rust compiler metadata from IDA's string list and submits generation jobs to the local server.

Use the graphical IDA executable for the plugin. `idat` is useful for non-UI checks but cannot load PySide6-based plugin forms.

## Troubleshooting

### `Symbol not found` references an external PySide6 library

The IDA-activated environment contains an incompatible Qt package. Remove only the external PySide6 packages from that environment and keep the full RIFT requirements in the dedicated RIFT environment. Restart IDA after changing the environment.

### `PySide6 can only be used from the GUI version of IDA`

This is expected when a GUI plugin is imported by `idat`. Run RIFT from the graphical IDA application.

### Rust version cannot be determined

RIFT maps the Rust compiler commit embedded in the binary through `data/rustc_hashes.json`. Update that file from the current RIFT checkout or regenerate it with the platform-appropriate hash update script.

### Server mode is unavailable

Confirm that the plugin config contains `[RiftServer]`, `Ip = 127.0.0.1`, and `Port = 5001`, then check `/health` before restarting IDA.
