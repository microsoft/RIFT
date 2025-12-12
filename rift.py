import argparse
from lib.rift_config import RIFTConfig
from lib.rift_fs import RIFTFileSystem
from lib.rift_compiler import RIFTCompiler
from lib.rift_gen import RIFTGenerator
from lib import utils
import os
import json
import pandas as pd
import subprocess

logger = utils.get_logger()

def handle_compile(compile_info, cargo_proj_path):
    rift_compiler = RIFTCompiler(logger, compile_info, cargo_proj_path)
    if not rift_compiler.determine_rust_version():
        logger.error(f"Failed determining rust version for commit_hash = {rift_compiler.commithash}")
        return False, None
    if not rift_compiler.init_target_compiler():
        logger.error(f"Failed initializing target compiler")
        return False, None
    if not rift_compiler.set_crates():
        logger.error(f"Failed setting crates!")
        return False, None
    if not rift_compiler.set_toolchain_config():
        logger.error(f"Failed setting toolchain config!")
        return False, None
    if not rift_compiler.set_cargo_config():
        logger.error(f"Failed setting cargo config file!")
        return False, None
    logger.debug("Building crates now ..")
    result = rift_compiler.build_crates()
    result["proj_config"] = rift_compiler.get_proj_config()
    return True, result
  

def handle_collection(rift_fs, compile_info):
    rustup_path = rift_fs.search_rustup_location()
    if rustup_path is None:
        logger.error("Collection phase failed! Could not find .rustup location!")
        return False
    tc_rlib_folder = rift_fs.get_tc_rlib_folder(rustup_path, compile_info["target_compiler"], compile_info["target"])
    if tc_rlib_folder is None:
        logger.error("Collection phase failed! Could not find rlib files of toolchain!")
        return False
    logger.info(f"Collecting toolchain .RLIB files from {tc_rlib_folder}")
    rift_fs.unpack_rlibs_to(utils.get_files_from_dir(tc_rlib_folder, ".rlib"), rift_fs.coff_toolchain_path, rift_fs.tmp_toolchain_path)

    # collect crates
    crates_rlib_folder = rift_fs.get_crates_rlib_folder(compile_info["proj_path"], compile_info["target"], compile_info["compile_type"])
    if crates_rlib_folder is None:
        logger.error("Could not find crates rlib files!")
    rift_fs.unpack_rlibs_to(utils.get_files_from_dir(crates_rlib_folder, ".rlib"), rift_fs.coff_crates_path, rift_fs.tmp_crates_path)

    return True

def handle_flirt(rift_fs, rift_gen):
    
    # Generate rustc flirt signature
    coff_files = utils.get_files_from_dir(rift_fs.coff_toolchain_path, ".o")
    rift_gen.gen_pat(coff_files, rift_fs.pat_path)
    flirt_sig_path = os.path.join(rift_fs.flirt_path, rift_gen.get_rustc_flirt_name())
    rift_gen.gen_flirt(rift_fs.pat_path, flirt_sig_path, ignore_collisions=True)
    logger.info(f"Generated rustc flirt = {flirt_sig_path}")
    utils.cleanup_folder(rift_fs.pat_path)

    # Generate crate flirt signatures
    coff_files = utils.get_files_from_dir(rift_fs.coff_crates_path, ".o")
    ordered_coff_files = utils.order_by_libname(coff_files)
    for key in ordered_coff_files.keys():
        flirt_sig_name = os.path.join(rift_fs.flirt_path, rift_gen.get_flirt_name(key))
        logger.debug(f"Generating {flirt_sig_name} for {key}")
        coff_files = ordered_coff_files[key]
        try:
            rift_gen.gen_pat(coff_files, rift_fs.pat_path)
            rift_gen.gen_flirt(rift_fs.pat_path, flirt_sig_name, ignore_collisions=True)
        except subprocess.CalledProcessError:
            logger.exception(f"Failed generating flirt signature for {key}, skipping ..")
            utils.cleanup_folder(rift_fs.pat_path)
            continue
        logger.info(f"Generated {flirt_sig_name}")
        utils.cleanup_folder(rift_fs.pat_path)
    return True

def handle_diff(rift_fs, rift_gen, target):
    coff_files = {"toolchain": [], "crates": []}
    coff_files["toolchain"] = utils.get_files_from_dir(rift_fs.coff_toolchain_path, ".o")
    coff_files["crates"] = utils.get_files_from_dir(rift_fs.coff_crates_path, ".o")
    logger.info(f"Coff files collected, total crate coff files = {len(coff_files['crates'])}, total toolchain coff files = {len(coff_files['toolchain'])}")
    # NOTE: Keep use_decompiler disabled for now 
    rift_gen.set_dph_env(False)
    rift_gen.gen_sqlite(coff_files["toolchain"], rift_fs.sql_toolchain_path, rift_fs.idb_toolchain_path)
    logger.info("Finished generating sqlite files for toolchain coff files")
    rift_gen.gen_sqlite(coff_files["crates"], rift_fs.sql_crates_path, rift_fs.idb_crates_path)
    logger.info("Finished generating sqlite files for crates coff files")
    rift_gen.dph_env_cleanup()
    logger.info(f"Running diffing process now!")
    sqlite_files = {"toolchain": [], "crates": []}
    sqlite_files["toolchain"] = utils.get_files_from_dir(rift_fs.sql_toolchain_path, ".sqlite")
    sqlite_files["crates"] = utils.get_files_from_dir(rift_fs.sql_crates_path, ".sqlite")
    logger.info(f"SQL files collected, number of coff files, toolchain = {len(sqlite_files['toolchain'])} , crates = {len(sqlite_files['crates'])}")
    rift_gen.dph_diff(target, sqlite_files["toolchain"], rift_fs.sql_diff_toolchain_path)
    rift_gen.dph_diff(target, sqlite_files["crates"], rift_fs.sql_diff_crates_path)
    return True


def gen_diff_json(rift_fs, diff_output_name):
    sql_diff_files = {"toolchain": [], "crates": []}
    sql_diff_files["toolchain"] = utils.get_files_from_dir(rift_fs.sql_diff_toolchain_path, ".sqlite")
    sql_diff_files["crates"] = utils.get_files_from_dir(rift_fs.sql_diff_crates_path, ".sqlite")
    files = sql_diff_files["toolchain"]
    files.extend(sql_diff_files["crates"])

    df = pd.DataFrame()
    for file in files:
        logger.info(f"Reading {file}")
        # tables: config results unmatched
        dbpath = f"sqlite:///{file}"
        df_results = pd.read_sql_table("results", dbpath)
        df = pd.concat([df, df_results])
    df.to_json(diff_output_name, orient="records", lines=True)
    return True

def main(args):
    """Main."""
    cfg_path = ""
    input = os.path.abspath(os.path.expanduser(args.input))
    output_folder = os.path.abspath(os.path.expanduser(args.output))
    logger = utils.get_logger(args.log, args.verbose)

    if args.rift_config == "rift_config.cfg":
        cfg_path = os.path.join(os.getcwd(), args.rift_config)
    else:
        cfg_path = args.rift_config

    logger.info(f"Starting RIFT, cfg_path = {cfg_path}, input_file = {input}, output_folder = {output_folder}, enable_diff = {args.enable_diffing}, enable_flirt = {args.enable_flirt}")
    try:
        rift_config = RIFTConfig(cfg_path, logger)
    except FileNotFoundError:
        logger.error(f"Invalid configuration! Please set a valid path for WorkFolder and TmpFolder. The folders have to exist")
        return 0
    if args.enable_diffing and not rift_config.diff_available:
        logger.error(f"You have enabled binary diffing, but provided invalid paths to Diaphora and Idat.exe. Aborting execution.")
        return 0
    if args.enable_flirt and not rift_config.flirt_available:
        logger.error(f"You have enabled flirt generation, but provided invalid paths to pcf.exe and sigmake.exe. Aborting execution.")
        return 0
    
    try:
        compile_info = utils.read_json(args.input)
    except FileNotFoundError:
        logger.exception(f"Could not find file = {args.input}")
        return 0
    except json.JSONDecodeError:
        logger.exception(f"Invalid json file = {args.input}")
        return 0
    
    logger.info(f"Read config & compile information, initializing RIFTFileSystem..")
    try:
        rift_fs = RIFTFileSystem(rift_config.work_folder, rift_config.cargo_proj_folder, output_folder, logger)
    except Exception:
        logger.exception(f"Failed initializing RIFTFileSystem with work_folder = {rift_config.work_folder}, cargo_proj_folder = {rift_config.cargo_proj_folder}")
        return 0
    if rift_fs.has_old_files(rift_config.work_folder):
        if not args.cleanup:
            logger.error(f"{rift_config.work_folder} contains old files from previous runs, clean up manually or enable the --cleanup flag to auto clean up the work env")
            return 0
        elif args.cleanup and not rift_fs.cleanup_work_folder():
            logger.error(f"Failed cleaning up work environment {rift_fs.work_folder}!")
            return 0

    if not rift_fs.init_cargo_project():
        return 0
    
    success, compile_info = handle_compile(compile_info, rift_fs.cargo_proj_path)
    if not success:
        logger.error(f"Failed compilation phase! Aborting ..")
        return 0
    
    compiled_crates = "\n".join(compile_info["compiled_crates"])
    logger.info(f"Compiled Crates:\n %s", compiled_crates)
    if len(compile_info["failed_crates"]) > 0:
        failed_crates = "\n".join(compile_info["failed_crates"])
        logger.info(f"Failed crates: \n %s", failed_crates)

    compile_info_path = os.path.join(rift_fs.info_path, "rift_compile_info.json")
    utils.write_json(compile_info_path, compile_info["proj_config"])   

    if not handle_collection(rift_fs, compile_info["proj_config"]):
        logger.error(f"Failed collection phase! Aborting ..")
        return 0
    logger.info(f"Collection phase finished! Enable_flirt = {args.enable_flirt}, Enable_Diffing = {args.enable_diffing}")
    rift_gen = RIFTGenerator(logger, rift_config, compile_info["proj_config"])
    if args.enable_flirt and not handle_flirt(rift_fs, rift_gen):
        logger.error(f"Failed generating flirt signatures!")
    else:
        utils.copy_files_by_ext(rift_fs.flirt_path, ".sig", output_folder)
    if args.enable_diffing and not handle_diff(rift_fs, rift_gen, args.target):
        logger.error(f"Failed generating diffing information!")
    else:
        gen_diff_json(rift_fs, args.diff_output_name)

    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", dest="rift_config", help="Path to config file", default="rift_config.cfg")
    parser.add_argument("--input", help="JSON input file", required=True)
    parser.add_argument("--output", help="Location where the results should be copied to", required=True)
    parser.add_argument("--binary-diff", dest="enable_diffing", action="store_true", help="Enable binary diffing")
    parser.add_argument("--target", dest="target", help="Target SQLITE file to batch diff against")
    parser.add_argument("--diff-output", dest="diff_output_name", help="Name of JSON file containing diffing information")
    parser.add_argument("--flirt", dest="enable_flirt", action="store_true",help="Enable flirt signature generation")
    parser.add_argument("--verbose", help="Enable verbose logging", action="store_true")
    parser.add_argument("--log", help="Enable logging into a file")
    parser.add_argument("--cleanup", action="store_true", help="Cleans up work environment before running")
    args = parser.parse_args()
    main(args)