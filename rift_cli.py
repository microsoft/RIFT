import argparse
import sys
import os
from pathlib import Path
from librift.utils import get_logger, parse_crate_string
from librift.rift_meta import build_rustmeta_from_string, build_rustmeta_from_json
from librift.sig_backend import DEFAULT_FORMAT
from rift_engine import RiftEngine

logger = None

def get_requested_formats(args):
    """
    Maps the --flirt / --fidb flags onto signature formats.

    Each flag selects one format and they combine, so passing both generates
    both artifacts from a single build. With neither flag set, RIFT keeps its
    historical behaviour and generates FLIRT signatures.
    """
    formats = []
    if args.flirt:
        formats.append("flirt")
    if args.fidb:
        formats.append("fid")
    if not formats:
        logger.debug(f"No output format requested, defaulting to {DEFAULT_FORMAT}")
        formats.append(DEFAULT_FORMAT)
    return tuple(formats)

def handle_file_mode(input_file, cfg_path, output_path, only_meta=False, formats=(DEFAULT_FORMAT,)):
    """Handle file analysis mode - analyze binary and optionally generate signatures."""
    if not os.path.isfile(input_file):
        logger.error(f"File {input_file} does not exist!")
        return 0

    logger.info(f"Running in file analysis mode: {input_file}")
    api = RiftEngine(logger, cfg_path, output_folder=output_path)

    if only_meta:
        meta = api.get_meta(input_file)
        if meta is None:
            logger.error("Could not extract metadata from binary")
            return 0
        meta.print()
        return 1

    # Generate signatures (default behavior when --only-meta is not set)
    for fmt in formats:
        logger.info(f"Generating {fmt} signatures for analyzed binary")
        if fmt == "flirt":
            api.generate_flirt_from_binary(input_file, output_path)
        else:
            api.generate_fid_from_binary(input_file, output_path)

    return 1

def handle_json_mode(json_file, cfg_path, output_path, formats=(DEFAULT_FORMAT,)):
    """Handle JSON mode - generate signatures from JSON configuration."""
    if not os.path.isfile(json_file):
        logger.error(f"File {json_file} does not exist!")
        return 0

    api = RiftEngine(logger, cfg_path, output_folder=output_path)
    meta = build_rustmeta_from_json(logger, api.cfg, json_file)
    for fmt in formats:
        logger.info(f"Generating {fmt} signature for crates and compiler passed through {json_file}")
        if fmt == "flirt":
            api.generate_compiler_flirt(meta, output_path)
            api.generate_crates_flirt(meta, output_path)
        else:
            api.generate_compiler_fid(meta, output_path)
            api.generate_crates_fid(meta, output_path)
    return 1

def handle_gen_mode(cfg_path, output_path, compiler="", crate="", formats=(DEFAULT_FORMAT,)):
    """Handle generation mode - generate FLIRT signatures for crate/compiler combinations."""
    logger.info(f"Running in signature generation mode, formats = {', '.join(formats)}")

    # Case 1: Both crate and compiler provided
    if crate and compiler:
        logger.info(f"Crate: {crate}, Compiler: {compiler}")
        api = RiftEngine(logger, cfg_path, output_folder=output_path)
        meta = build_rustmeta_from_string(compiler)

        # Generate signatures for specific crate with compiler
        crate_obj = parse_crate_string(crate)
        logger.debug(f"Compiling crate = {crate_obj.get_id()}")
        for fmt in formats:
            logger.info(f"Generating {fmt} signature for {crate} with compiler {compiler}")
            if fmt == "flirt":
                api.generate_crate_flirt(meta, crate_obj, output_path)
            else:
                api.generate_crate_fid(meta, crate_obj, output_path)
        return 1

    # Case 2: Only compiler provided (no crate)
    elif compiler and not crate:
        logger.info(f"Compiler: {compiler}")
        api = RiftEngine(logger, cfg_path, output_folder=output_path)
        meta = build_rustmeta_from_string(compiler)

        # Generate signatures for compiler only
        for fmt in formats:
            logger.info(f"Generating {fmt} signature for compiler {compiler}")
            try:
                if fmt == "flirt":
                    api.generate_compiler_flirt(meta, output_path)
                else:
                    api.generate_compiler_fid(meta, output_path)
                logger.info(f"Compiler {fmt} signature generated successfully")
            except Exception as e:
                logger.error(f"Failed to generate compiler {fmt} signature: {e}")
                return 0
        return 1
    else:
        logger.error(f"Providing only the crate and not the compiler is not supported yet!")
        return 0

def main(args):
    """Main entry point - routes to appropriate handler based on arguments."""
    global logger
    logger = get_logger(args.log, args.verbose)

    # Pre-check: Verify config file exists
    if not os.path.isfile(args.cfg):
        logger.error(f"Config file {args.cfg} does not exist!")
        return 0

    formats = get_requested_formats(args)

    # Mode 1: File analysis mode (when -f/--file is provided)
    if args.file:
        return handle_file_mode(args.file, args.cfg, args.output, args.only_meta, formats)

    # Mode 2: Legacy mode, JSON file is provided
    elif args.json:
        return handle_json_mode(args.json, args.cfg, args.output, formats)

    # Mode 3: Direct signature generation mode (crate/compiler based)
    elif args.crate or args.compiler:
        return handle_gen_mode(args.cfg, args.output, args.compiler or "", args.crate or "", formats)

    else:
        logger.error("No valid arguments provided. Use --help for usage information.")
        return 0


RIFT_ASCII = """
 ____  ___ _____ _____
|  _ \|_ _|  ___|_   _|
| |_) || || |_    | |
|  _ < | ||  _|   | |
|_| \_\___|_|     |_|

 Rust FLIRT Signature Generator
"""

class RiftArgumentParser(argparse.ArgumentParser):
    def format_help(self):
        return RIFT_ASCII + "\n" + super().format_help()


if __name__ == "__main__":
    parser = RiftArgumentParser(
        description="RIFT - Rust binary analysis and FLIRT signature generation tool",
        epilog="""
Examples:
  # Analyze a binary file and print only metadata
  %(prog)s -f sample.exe --only-meta

  # Analyze a binary and generate FLIRT signatures (default)
  %(prog)s -f sample.exe -o ./output

  # Generate FLIRT for a specific crate and compiler
  %(prog)s reqwest@0.123 1.89-i686-pc-windows-msvc -o ./output

  # Generate FLIRT for a compiler only
  %(prog)s 1.89-i686-pc-windows-msvc -o ./output

  # Generate a Ghidra Function ID database instead of FLIRT signatures
  %(prog)s --fidb 1.89-i686-pc-windows-msvc -o ./output

  # Generate both artifacts from one build
  %(prog)s --flirt --fidb -f sample.exe -o ./output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Positional arguments for crate/compiler FLIRT generation mode
    parser.add_argument("crate", nargs='?', help="Crate specification (e.g., reqwest@0.123) or compiler specification (e.g., 1.89-i686-pc-windows-msvc)")
    parser.add_argument("compiler", nargs='?', help="Compiler specification (e.g., 1.89-i686-pc-windows-msvc) when crate is also provided")

    # Create mutually exclusive group for file input modes
    file_mode_group = parser.add_mutually_exclusive_group()
    file_mode_group.add_argument("-f", "--file", help="Path to binary file to analyze (File analysis mode)")
    file_mode_group.add_argument("--json", help="Input JSON configuration to generate corresponding FLIRT signatures")

    # Optional arguments
    parser.add_argument("-c", "--cfg", help="Config file path (default: ./rift_config.cfg)", default="./rift_config.cfg")
    parser.add_argument("-l", "--log", help="Log file path (default: None)", default=None)
    parser.add_argument("-v", "--verbose", help="Enable verbose logging", action="store_true", default=False)
    parser.add_argument("-o", "--output", help="Output folder (default: ./Output)", default="./Output")
    parser.add_argument("--only-meta", help="Print only metadata, skip FLIRT generation (File analysis mode only)", action="store_true")

    # Determine what kind of signature files should be created
    parser.add_argument("--flirt", help="Generate FLIRT signatures", action="store_true", default=False)
    parser.add_argument("--fidb", help="Generate Function ID database files", action="store_true", default=False)

    args = parser.parse_args()
    sys.exit(main(args))