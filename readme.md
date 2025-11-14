# RIFT (Rust Interactive Function Tool)

> ⚠️ **Security Warning**
>
> This tool is intended to be used **only within a dedicated virtual machine (VM)** environment. Running it outside of a controlled VM may expose your system to security risks, including potential malware execution or data leakage.
>
> Please ensure all analysis is conducted in an **isolated, sandboxed VM** with no access to production networks or sensitive data.


RIFT (Rust Interactive Function Tool) is a toolsuite to assist reverse engineers in identifying library code in rust malware. It is a research project developed by the MSTIC-MIRAGE Team, explores library recognition techniques conducted on rust binaries and was presented at RECON 2025.

It consists of three core components:

1) RIFT Static Analyzer - IDA Plugin to extract static information from rust binaries
2) RIFT Generator - A set of scripts serving as wrappers around the rust toolchain.
3) RIFT Diff Applier - IDA Plugin to apply generated binary diffing results on the binary

Currently, the plugins are only developed for Ida Pro and tested on Ida Pro >=9.0.
RIFT Generator was tested on Windows 10, 64 bit. We have also recently added support for Linux. RIFT FLIRT Signature generation was tested on Debian 12.

RIFT was mainly tested on Windows malware so far, expanding its capabilities is ongoing.
We are very much looking forward for contributions by the community.

## Setup Guide

Copy the following files to your Ida plugins directory:

* rift_static_analyzer.py
* rift_diff_applier.py
* Copy the ida_rift_lib folder to Ida plugins

In order to use the whole toolsuite, the following dependencies need to be installed:

* rustup and cargo, preferably via: https://rustup.rs/
* Python requirements via: `py -m pip install -r requirements.txt`
* You will have to install Ida, download Diaphora(https://github.com/joxeankoret/diaphora) and FLAIR tools (https://docs.hex-rays.com/user-guide/helper-tools)
* Furthermore, you will also need to adjust the rift_config.cfg. You need to set the paths to the corresponding tools

## Updating Commithash JSON File

RIFT depends on `data/rustc_hashes.json` to determine the rust version of the corresponding commit hash. This file should be updated regularily.
To update, simply `cd` into the `RIFT` folder and run `update_rustc_hashes.ps1` or `update_rustc_hashes.sh` and the `data/rustc_hashes.json` file will be updated.
It's worthwhile noting that this process will take a few minutes. The script requires `awscli` and `python3` to be installed.

## Usage Guide

For a hands-on guide, check the `docs` folder for a step-by-step guide on how to use RIFT on real-world malware. The procedure can be summarized as follows:

1) Run RIFT Static Analyzer Plugin to extract information
2) Generate FLIRT signatures and/or diffing information
3) Apply FLIRT singatures and/or run RIFT Diff Applier

### 1) Static information Extraction

RIFT Static Analyzer is an IDA plugin that extracts various information from a rust binary. The output needs to be fed into the RIFT Generator in stage 2 to generate the corresponding signatures and COFF files.

In IDA, go to Edit->Plugins and click RIFT Static Analyzer, this will spawn the RIFT Static Analyzer GUI. 

![RIFT Static Analyzer](screenshots/ida_static_analyzer_1.png)

Overall, the static analyzer attempts to extract and store the following information in output json file:

* Commit Hash of used rustc compiler
* The target triple used for compilation (consists of architecture and compiler)
* The architecture the binary was compiled for
* The crates and their corresponding versions found in the binary 

### 2) Generating FLIRT signatures and Binary Diffing Information

RIFT Generator is a wrapper around rustup, cargo, Diaphora, Ida and Hexray's FLAIR tools, automating the process of generating the diffing information and flirt signature generation.

![RIFT Generator Procedure](screenshots/RIFT_Client_Procedure.png)

To run, you simply need to run `rift.py` and specify via command line arguments.

```
C:\RIFT\RIFT_V5>py rift.py -h
usage: rift.py [-h] [--cfg RIFT_CONFIG] --input INPUT --output OUTPUT [--binary-diff] [--target TARGET]
               [--diff-output DIFF_OUTPUT_NAME] [--flirt]

options:
  -h, --help            show this help message and exit
  --cfg RIFT_CONFIG     Path to config file
  --input INPUT         JSON input file
  --output OUTPUT       Location where the results should be copied to
  --binary-diff         Enable binary diffing
  --target TARGET       Target SQLITE file to batch diff against
  --diff-output DIFF_OUTPUT_NAME
                        Name of JSON file containing diffing information
  --flirt               Enable flirt signature generation
```

## RIFT Diff Applier

RIFT Diff Applier is an experimental IDA plugin that displays the results from the RIFT Generator diffing procedure. Essentially, it installs hotkeys and displays the top matching functions with the highest similarity from all diffed functions.

The approach can be useful if the rust compiler was not properly determined.

In IDA, go to Edit->Plugins and click RIFT Diff Applier, this will spawn the RIFT Diff Applier GUI.

![Rift Diff Applier GUI](screenshots/RiftDiffApplier1.png)

From here, you are able to configure a number of different options:

```
Import JSON file -> Load the JSON file containing diffing information
Enable auto renaming -> Based on auto rename ratio, rename functions automatically
Enable name demangling -> Attempt to fix symbols from COFF files (experimental)
Select ratio -> Minimum similarity ratio 
Select auto rename ratio -> Minimum similarity ratio for auto renaming 
```

Once configured and the JSON file is read, a window will pop up. Place the window as you like. If you click on a function and use hotkey CTRL+X or the context menu, `RIFT Diff Applier` will list you the top 3 matching functions.

![Rift Diff Applier in use](screenshots/RIFTDiffApplier_Graphic1.png)
