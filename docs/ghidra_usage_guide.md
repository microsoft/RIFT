# Using RIFT with Ghidra

This guide covers generating Ghidra Function ID databases (`.fidb`) for Rust crates and toolchains
with RIFT, and applying them to a binary in Ghidra. IDA Pro is not required for this workflow.

## How it works

RIFT compiles the requested crate (or uses the requested rustc toolchain), extracts the object files
from the resulting `.rlib` files, and hands them to Ghidra's `analyzeHeadless` launcher. Each database
is built in two headless runs against one throwaway Ghidra project:

1. **Import and analyze.** All object files are imported into the project and analyzed, using
   Ghidra's own `FunctionIDHeadlessPrescript.java` / `FunctionIDHeadlessPostscript.java`.
2. **Populate.** `scripts/RiftPopulateFid.java` builds one Function ID library from all analyzed
   programs and writes it to the `.fidb` file.

The throwaway project lives in `<WorkFolder>/ghidra` and is removed after every run.

## Prerequisites

- **Ghidra** installation. Validated with Ghidra 12.1.2.
- **JDK** matching your Ghidra version. Validated with OpenJDK 21.
- **Rust** via `rustup`, with `cargo` on the `PATH`. RIFT installs the required toolchains itself.
- The Python dependencies of RIFT (see `readme.md`).

## Configuration

All settings live in `rift_config.cfg`, section `[Default]`:

```ini
[Default]
# Ghidra's headless launcher. On Windows use analyzeHeadless.bat
AnalyzeHeadlessPath = /path/to/ghidra_12.1.2_PUBLIC/support/analyzeHeadless
# Work folder for intermediate files. Must exist.
WorkFolder = /path/to/RIFT/work
# Folder where RIFT creates its cargo projects
CargoProjFolder = /path/to/RIFT/tmp
# Path to rustc_hashes.json, shipped in data/
RustcHashes = /path/to/RIFT/data/rustc_hashes.json
# strings binary, used for metadata extraction from binaries
StringsTool = /usr/bin/strings

# IDA tools, only needed for FLIRT output
PcfPath = NOT_SET
SigmakePath = NOT_SET
```

Notes:

- `AnalyzeHeadlessPath` must point at the launcher file itself, not the Ghidra folder. If it is
  missing or wrong, RIFT disables Function ID output and `--fidb` fails with a configuration error.
- `WorkFolder` must already exist. RIFT creates its subfolders, including `ghidra/`, on startup.
- `PcfPath` and `SigmakePath` can stay unset when you only want `.fidb` files. RIFT logs a warning
  that FLIRT generation is disabled, which is expected and harmless.

## Generating databases

Use the `--fidb` flag. Add `--flirt` as well to produce FLIRT signatures from the same build.
The output folder (`-o`) may be relative or absolute, and must exist.

A single crate for a given toolchain:

```bash
python rift_cli.py --fidb serde@1.0.185 1.75.0-x86_64-unknown-linux-gnu -o ./Output
```

The toolchain (std, core, alloc, ...) only:

```bash
python rift_cli.py --fidb 1.75.0-x86_64-unknown-linux-gnu -o ./Output
```

Everything a binary was built with (toolchain plus all detected crates):

```bash
python rift_cli.py --fidb -f sample.exe -o ./Output
```

Both FLIRT and Function ID output in one run (requires IDA tools as well):

```bash
python rift_cli.py --flirt --fidb -f sample.exe -o ./Output
```

Add `-v` for verbose logging, which also prints the exact `analyzeHeadless` commands.

### Output

Each crate and each toolchain produces one `.fidb` holding a single Function ID library:

```
rustc-1.75.0-x86_64-unknown-linux-gnu.fidb
serde-1.0.185-1.75.0-x86_64-unknown-linux-gnu.fidb
```

A successful run logs a result line from the populate script, for example:

```
RIFT_FID_RESULT added=100 excluded=4 attempted=104
```

`added` is the number of functions stored in the database. A database with zero functions is
treated as an error and is not kept.

### Server mode

When running `rift_server.py`, request Function ID output by setting `"fidb": true` in the job
request body. `"flirt"` and `"fidb"` combine the same way as the CLI flags. See `readme.md` for
the full request format.

## Applying databases in Ghidra

1. Copy `scripts/RiftApplyFidFromFolder.java` into your Ghidra scripts directory (by default
   `~/ghidra_scripts`), or add RIFT's `scripts/` folder as a script path in the Script Manager.
2. Open the Rust binary in Ghidra and run **RiftApplyFidFromFolder** from the Script Manager
   (category *FunctionID*).
3. Select the folder containing the generated `.fidb` files. The script attaches every database in
   it and re-applies Function ID matching to the open program, including functions that were
   already named.

Attached databases persist in your Ghidra configuration, so later programs are matched by the
Function ID analyzer automatically. Manage them under
**Tools → Function ID → Choose active FidDbs**.

### Re-running Function ID matching

Function ID matching only happens when the Function ID analyzer runs. Depending on how the
databases were attached and when the program was analyzed, you may need to trigger it again:

- **One-shot Function ID analysis.** Use **Analysis → One Shot → Function ID** to re-run only the
  Function ID analyzer on the open program. This is the quickest option for a program that is
  already analyzed, for example after attaching databases manually via
  **Tools → Function ID → Choose active FidDbs** instead of using the script.
- **Auto analysis.** Use **Analysis → Auto Analyze '<program>'** (shortcut `A`) and make sure
  *Function ID* is enabled in the analyzer list. Use this if the program has not been analyzed yet,
  or if new functions were created after the last Function ID pass.

Function ID only labels functions it can match against an attached database. Functions that were
inlined or compiled differently from the generated databases stay unnamed.

## Troubleshooting

**Where are the details of a failed Ghidra run?**
Ghidra writes its full log, including script errors and stack traces, to
`~/.config/ghidra/ghidra_<version>/application.log` (Linux). Search it for `ERROR` or
`RiftPopulateFid` around the time of the failed run. RIFT also logs Ghidra's output at error level
when the populate run exits with a non-zero code.

**`Populate script did not report a result! Missing RIFT_FID_RESULT`**
Ghidra exits with code 0 even when a script throws, so RIFT relies on the result line instead.
This error means the populate script failed. Check `application.log` for the script's stack trace.

**Rerunning for the same crate reports success but nothing changes**
If the target `.fidb` already exists and already contains the library, the populate script skips it
(`RIFT_FID_SKIP`) and RIFT reports success without rebuilding. Delete the existing `.fidb` before
regenerating it.

**`Ghidra project location ... does not exist!`**
The `<WorkFolder>/ghidra` folder is missing. Check that `WorkFolder` in the config points at an
existing folder. RIFT recreates `ghidra/` on the next start.

## Current limitations

- The workflow has been validated end to end for a single crate on Linux
  (`serde@1.0.185`, rustc `1.75.0-x86_64-unknown-linux-gnu`, Ghidra 12.1.2).
- Full toolchain builds import thousands of object files and have not been validated yet. Expect
  long run times for the import and populate phases.
- Supported architectures: `x86_64`, `i686`, `aarch64`, `arm`. Other architectures are rejected
  rather than producing a database that matches nothing.
