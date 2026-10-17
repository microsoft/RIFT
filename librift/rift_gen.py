"""
RIFT generation module for generating content and responses.
"""
from librift.rift_os import RiftOs
from librift.proj_handler import ProjectHandler
from librift.flirt import FlirtGenerator
from librift.fid import FunctionIdDb_Engine
from librift.sig_backend import SUPPORTED_FORMATS, DEFAULT_FORMAT
from librift.utils import exec_cmd, get_files_from_dir, cleanup_folder
from librift.crate import RustCrate
from librift.rift_meta import RiftMeta
from librift.rustmeta import RustMetadata
from librift.rift_cfg import RiftConfig
from librift.storage_handler import StorageHandler
from logging import Logger
import os


class RiftFlirtGenException(Exception):
    """Custom exception for RIFT FLIRT generation errors."""
    pass

class RiftGenerator:
    def __init__(self, cfg: RiftConfig, logger: Logger, rift_meta: RiftMeta, rift_os: RiftOs, storage_handler: StorageHandler, proj_handler: ProjectHandler):
        """
        Initialize the RIFT generator.
        """
        self.cfg = cfg
        self.logger = logger
        self.rift_meta = rift_meta
        self.storage_handler = storage_handler
        self.rift_os = rift_os
        self.proj_handler = proj_handler
        self.backends = {}
        if cfg.flirt_available:
            self.backends["flirt"] = FlirtGenerator(logger, cfg.sigmake, cfg.pcf, storage_handler.pat_path)
        if cfg.fid_available:
            self.backends["fid"] = FunctionIdDb_Engine(logger, cfg.analyze_headless, storage_handler.ghidra_path)
        self.logger.debug(f"Available signature backends = {sorted(self.backends)}")

    def init_target_compiler(self, meta: RustMetadata):
        """Install and configure target compiler. Args: meta (RustMetadata). Returns: bool: True if successful."""
        target_compiler = meta.get_target_compiler()
        if target_compiler not in self.rift_os.get_installed_toolchains():
            self.logger.info(f"Installing target_compiler = {target_compiler}")
            if not self.rift_os.install_target_compiler(target_compiler):
                self.logger.error(f"Could not install target_compiler = {target_compiler}")
                return False
        
        target = meta.get_target_triple()
        if target not in self.rift_os.get_added_targets():
            self.logger.info(f"Adding target = {target}")
            if not self.rift_os.add_target(target):
                self.logger.error(f"Could not add target = {target}")
                return False
        return True
    
    def init_env(self, meta: RustMetadata):
        """Initialize environment and configs. Args: meta (RustMetadata). Returns: bool: True if successful."""
        if not self.init_target_compiler(meta):
            self.logger.error(f"Failed initializing target compiler!")
            return False
        self.logger.debug("Initialized target compiler")
        if not self.proj_handler.init_toml_config():
            self.logger.error("Could not initialize Cargo.toml config!")
            return False
        if not self.proj_handler.init_toolchain_config(meta):
            self.logger.error("Could not initialize rust-toolchain.config!")
            return False
        if not self.proj_handler.init_cargo_config(meta):
            return False
        
        # Configure the target edition
        target_edition = meta.get_target_edition()
        self.logger.debug(f"Setting edition in Cargo.toml to {target_edition}")
        self.proj_handler.cargo_toml.set_edition(target_edition)
        self.proj_handler.cargo_toml.remove_crates()
        self.storage_handler.cleanup_files()
        self.rift_os.set_dir(self.proj_handler.cargo_proj_path)
        return True

    def _get_cargo_check(self, crate: RustCrate, debug_build=False):
        """Build cargo check command. Args: crate (RustCrate), debug_build (bool). Returns: list: Command list."""
        build_type = "--debug" if debug_build else "--release"
        return ["cargo", "check", build_type, "--package", crate.name]

    def _get_cargo_build(self, crate: RustCrate, debug_build=False):
        """Build cargo build command. Args: crate (RustCrate), debug_build (bool). Returns: list: Command list."""
        build_type = "--debug" if debug_build else "--release"
        return ["cargo", "build", build_type, "--package", crate.name]
    
    def compile_crate(self, crate: RustCrate, debug_build=False):
        """Compile crate"""

        check_cmd = self._get_cargo_check(crate, debug_build=debug_build)
        compile_cmd = self._get_cargo_build(crate, debug_build=debug_build)

        resultcode, stdout, stderr = exec_cmd(check_cmd, capture_output=True, check=True)
        if resultcode != 0:
            self.logger.warning(f"Failed running check on {crate.get_id()}")
            self.logger.debug(stdout)
            self.logger.debug(stderr)
            return False
        resultcode, _, _ = exec_cmd(compile_cmd, capture_output=False, check=True)
        if resultcode != 0:
            self.logger.warning(f"Failed compiling {crate.get_id()}")
            return False
        return True
    
    def gen_toolc_flirt(self, meta: RustMetadata, output_folder: str, formats=(DEFAULT_FORMAT,)):
        """Generate the toolchain signatures. Returns list of generated artifact paths."""
        rustup_path = self.storage_handler.search_rustup_location()
        if rustup_path is None:
            raise RiftFlirtGenException("Could not find rustup folder!")
        tc_rlib_folder = self.storage_handler.get_tc_rlib_folder(rustup_path, meta)
        self.logger.debug(f"Toolchain folder = {tc_rlib_folder}")
        if tc_rlib_folder is None:
            raise RiftFlirtGenException("Collection phase failed! Could not find rlib files of toolchain!")
        coff_files = self.__unpack_rlibs(tc_rlib_folder, self.storage_handler.coff_toolchain_path, self.storage_handler.tmp_toolchain_path)
        sig_paths = self.__handle_gen_signatures(coff_files, output_folder, meta, formats=formats)

        try:
            self.storage_handler.cleanup_files()
        except Exception:
            self.logger.error(f"Could not cleanup folder = {self.storage_handler.pat_path}")
        return sig_paths
    
    def generate_crates_flirt(self, meta: RustMetadata, output_folder: str, formats=(DEFAULT_FORMAT,)):
        """Batch generate crates for file"""
        crates = meta.get_crates()
        self.logger.debug(f"Inserting {len(crates)} crates into cargo project")
        for crate in crates:
            if not self.generate_crate_flirt(meta, crate, output_folder, formats=formats):
                self.logger.warning(f"Failed generating crate = {crate.get_id()}")
        return output_folder

    def __resolve_formats(self, formats):
        """Validates the requested formats and returns them deduplicated, in declared order."""
        if isinstance(formats, str):
            formats = (formats,)
        requested = set()
        for fmt in formats:
            name = str(fmt).strip().lower()
            if name not in SUPPORTED_FORMATS:
                raise RiftFlirtGenException(f"Unknown signature format = {fmt}!")
            requested.add(name)
        if not requested:
            raise RiftFlirtGenException("No signature format requested!")
        return tuple(fmt for fmt in SUPPORTED_FORMATS if fmt in requested)

    def __handle_gen_signatures(self, coff_files, output_folder, meta, crate=None, formats=(DEFAULT_FORMAT,)):
        """
        Emits one artifact per requested format from the same object files.

        A backend that fails or is unavailable is logged and skipped, so one
        missing toolchain never takes the other format down with it. Raises only
        when no requested format produced anything.
        """
        sig_paths = []
        for fmt in self.__resolve_formats(formats):
            backend = self.backends.get(fmt)
            if backend is None:
                self.logger.error(f"Signature format = {fmt} was requested but its backend is unavailable!")
                continue
            sig_path = os.path.join(output_folder, meta.get_sig_name(crate, backend.extension))
            self.logger.info(f"Storing {fmt} signature in {sig_path}")
            try:
                sig_paths.append(backend.generate(coff_files, sig_path, meta, crate))
            except Exception:
                self.logger.exception(f"Could not generate {fmt} signature!")
        if not sig_paths:
            raise RiftFlirtGenException(f"Could not generate any signature for formats = {formats}!")
        return sig_paths

    def __unpack_rlibs(self, rlib_folder, crates_path, tmp_crates_path):
        """Unpacks rlib files from folder. Returns list of file paths"""
        self.storage_handler.unpack_rlibs_to(get_files_from_dir(rlib_folder, ".rlib"), crates_path, tmp_crates_path)
        self.logger.debug(f"RlibFolder = {rlib_folder}")
        coff_files = get_files_from_dir(crates_path, ".o")
        self.logger.debug(f"Total of {len(coff_files)}")
        return coff_files

    def generate_crate_flirt(self, meta: RustMetadata, crate: RustCrate, output_folder: str, debug_build=False, formats=(DEFAULT_FORMAT,)):
        """Generates signatures for a single crate. Stores them in output_folder"""
        
        self.proj_handler.insert_crate(crate)
        self.logger.debug(f"Compiling FLIRT signature for crate {crate.get_id()}")
        res = self.compile_crate(crate, debug_build=debug_build)
        sig_paths = None
        # If you couldn't compile still clean up
        if not res:
            self.logger.error(f"Could not compile {crate.get_id()}")
        else:
            crates_rlib_folder = self.storage_handler.get_crates_rlib_folder(self.proj_handler.cargo_proj_path, meta)
            coff_files = self.__unpack_rlibs(crates_rlib_folder, self.storage_handler.coff_crates_path, self.storage_handler.tmp_crates_path)
            sig_paths = self.__handle_gen_signatures(coff_files, output_folder, meta, crate=crate, formats=formats)

        try:
            self.storage_handler.cleanup_files()
        except Exception:
            self.logger.exception(f"Could not cleanup folder = {self.storage_handler.pat_path}")
        self.proj_handler.remove_crate(crate)
        self.proj_handler.reset_project()
        return sig_paths