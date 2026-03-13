# RIFT (Rust Interactive Function Tool)

> ⚠️ **Security Warning**
>
> This tool is intended to be used **only within a dedicated virtual machine (VM)** environment. Running it outside of a controlled VM may expose your system to security risks, including potential malware execution or data leakage.
>
> Please ensure all analysis is conducted in an **isolated, sandboxed VM** with no access to production networks or sensitive data.

> 🧪 **Experimental Build**
>
> This branch is under active development. Functionality may be incomplete or subject to change. **Testing has been conducted on Windows only.** Behaviour on Linux or macOS is untested and not guaranteed.

RIFT (Rust Interactive Function Tool) is a toolsuite to assist reverse engineers in identifying library code in rust malware. It is a research project developed by the MIRAGE Team, explores library recognition techniques conducted on rust binaries and was presented at RECON 2025.

This branch is an updated version, supporting only FLIRT signature generation. For the original version presented at RECON 2025 and also supports BinaryDiffing, see the version_1_stable build.



## Features



- **Binary Metadata Extraction**: Extract metadata from Rust binaries including:
  - Rust compiler version and commit hash
  - Target architecture and triple
  - Compiler type (MSVC, GNU, UEFI)
  - Detected Rust crates and their versions
  - File type detection (PE/ELF)

- **FLIRT Signature Generation**: Create FLIRT signatures for:
  - Rust compiler toolchain (rustc)
  - Individual Rust crates
  - Multiple architectures, tested only on x86 and x86_64

- **Multiple Operating Modes**:
  - File analysis mode (run rift_cli.py directly on binaries)
  - JSON configuration mode (feed exported JSON files as input, similar as in version_1_stable)
  - Direct generation mode (specific crate/compiler combinations)

- **Integration in Ida**:
  - Ida Pro Plugin and RIFT_API server to generate FLIRT signature in single RE sessions

## Installation

1. Clone the repository
2. Install dependencies via `py -m pip install -r requirements.txt`
3. Ensure that rustup and cargo are installed, preferably via: https://rustup.rs/
4. Place Ida Pro utilities (`pcf`, `sigmake`) and `strings.exe` from preferably SysInternals Suite in the `bin/` directory
5. Configure `rift_config.cfg` with correct paths

Furthermore, RIFT depends on `data/rustc_hashes.json` to determine the rust version of the corresponding commit hash. This file should be updated regularily.

To update the `rustc_hashes.json` file, one can simply always pull the latest RIFT version or generate it by themselves via running `update_rustc_hashes.ps1` or `update_rustc_hashes.sh`, depending on the environment.


## Usage

RIFT can either run as a command line application to generate FLIRT signatures on demand or as an API server appliance, communicating with an Ida Pro Plugin directly.


### CommandLine Mode

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--file` | `-f` | Path to binary file to analyze | - |
| `--json` | - | Input JSON configuration file | - |
| `--cfg` | `-c` | Path to config file | `./rift_config.cfg` |
| `--log` | `-l` | Log file path | None |
| `--verbose` | `-v` | Enable verbose logging | False |
| `--output` | `-o` | Output folder for signatures | `./Output` |
| `--only-meta` | - | Print metadata only (file mode) | False |

#### File Analysis Mode

Run `rift_cli.py` directly on a binary and extract metadata or generate FLIRT signatures on demand:

```bash
python rift_cli.py -f sample.exe --only-meta
```

Analyze a binary and generate FLIRT signatures:
```bash
python rift_cli.py -f sample.exe -o ./output
```

#### JSON Configuration Mode

Input a JSON configuration and generate FLIRT signatures as configured in JSON:
```bash
python rift_cli.py --json config.json -o ./output
```

#### Direct Generation Mode

Input either a crate and a compiler or simply a compiler toolchain:

Generate FLIRT for a specific crate and compiler:
```bash
python rift_cli.py reqwest@0.11.0 1.75.0-x86_64-pc-windows-msvc -o ./output
```

Generate FLIRT for a compiler toolchain only:
```bash
python rift_cli.py 1.75.0-x86_64-pc-windows-msvc -o ./output
```

### Server Mode

RIFT includes a lightweight HTTP API server (`rift_server.py`) that accepts FLIRT generation jobs from remote clients (e.g. the IDA Pro plugin) and processes them asynchronously in the background.

#### Starting the server

```bash
python rift_server.py -o ./Output --cfg rift_config.cfg
```

| Argument | Description | Default |
|----------|-------------|---------|
| `-o` | Output folder for generated signatures. **When set, overrides any `output_folder` value sent by the client.** | `./Output/` |
| `--cfg` | Path to `rift_config.cfg` | `./rift_config.cfg` |
| `--log` | Log file path | None (stdout only) |
| `--verbose` | Enable DEBUG-level logging | False |

The server binds to the IP and port configured in `rift_config.cfg` under `[RiftServer]` (`Ip` and `Port`). Default is `127.0.0.1:5001`.

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/flirt` | Submit a FLIRT generation job. Returns a `job_id` immediately. |
| `GET` | `/job?id=<job_id>` | Get the status and result of a specific job. |
| `GET` | `/jobs[?status=<status>]` | List all jobs, optionally filtered by status (`pending`, `running`, `completed`, `failed`). |
| `GET` | `/health` | Health check — returns server status and worker state. |

#### POST /flirt — Request body

```json
{
  "commithash": "a55dd71",
  "arch": "x86_64",
  "filetype": "PE",
  "crates": [{"name": "reqwest", "version": "0.11.0"}],
  "target_triple": "x86_64-pc-windows-msvc",
  "output_folder": "/optional/client/path"
}
```

> **Note:** `output_folder` in the request body is ignored when the server is started with `-o`.

#### GET /job — Response example

```json
{
  "job_id": "abc123",
  "status": "completed",
  "result_files": ["/path/to/output/reqwest.sig"]
}
```

### IDA Pro Integration

The RIFT IDA Pro plugin allows FLIRT signatures to be generated and optionally applied directly from within an active reverse engineering session, without leaving IDA Pro.

#### Prerequisites

- RIFT server running and reachable (see [Server Mode](#server-mode))
- IDA Pro with Python support (IDA 7.x+)
- `rift_config.cfg` configured with the correct server IP and port

#### Installation

Run the installer script, passing the path to your IDA Pro plugins folder:

```bat
installUpdateIdaPlugin.bat "%APPDATA%\Hex-Rays\IDA Pro\plugins"
```

This copies the following layout into your plugins folder:

```
plugins/
├── rift_plugin.py          ← IDA plugin entry point
├── librift_ida/
│   ├── rift_form.py        ← Plugin UI (PySide6)
│   ├── rift_ida_core.py    ← Core logic (arch detection, server comms)
│   └── rift_controller.py  ← Background thread controller
├── librift/                ← Shared RIFT core library
└── rift_essentials/
    └── rift_config.cfg     ← Server connection config
```

#### Configuration

Edit `rift_essentials/rift_config.cfg` in the plugins folder and set the server address:

```ini
[RiftServer]
Ip = 127.0.0.1
Port = 5001
```

#### Usage

1. Open a Rust binary in IDA Pro.
2. Go to **Edit → Plugins → RIFT** (or use the hotkey if configured).
3. The plugin automatically extracts metadata from the binary (compiler version, crates, architecture, target triple).
4. Click **Configure** to verify server connectivity.
5. Click **Apply** to submit a job to the RIFT server and select a local folder where signatures will be stored.
6. Generated `.sig` files can be applied to the database via IDA's signature manager or the `ida_apply_flirt_from_folder.py` script in the `scripts/` folder.