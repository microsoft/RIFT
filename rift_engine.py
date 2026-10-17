from typing import Union, List, Optional
from pathlib import Path
from librift.rift_cfg import RiftConfig
from librift.rift_meta import RiftMeta
from librift.rift_os import RiftOs
from librift.storage_handler import StorageHandler
from librift.utils import get_logger
from librift.proj_handler import get_project_handler,RiftProjectHandlerError
from librift.rift_gen import RiftGenerator
import os

class RiftEngineError(Exception):
    """Base exception for RIFT engine errors."""
    pass


class RiftConfigError(RiftEngineError):
    """Configuration-related errors."""
    pass


class RiftMetadataError(RiftEngineError):
    """Metadata extraction errors."""
    pass


class RiftSignatureError(RiftEngineError):
    """Signature generation errors, whatever the output format."""
    pass


class RiftFlirtError(RiftSignatureError):
    """FLIRT generation errors."""
    pass


class RiftFidError(RiftSignatureError):
    """Function ID database generation errors."""
    pass


# Per-format config attribute, error type and hint for a missing toolchain.
FORMAT_AVAILABILITY = {"flirt": "flirt_available", "fid": "fid_available"}
FORMAT_ERRORS = {"flirt": RiftFlirtError, "fid": RiftFidError}
FORMAT_HINTS = {
    "flirt": "Set PcfPath and SigmakePath in the config to generate FLIRT signatures.",
    "fid": "Set AnalyzeHeadlessPath in the config to generate Function ID databases.",
}


class RiftEngine:
    """Core engine for Rust binary analysis and FLIRT signature generation."""

    def __init__(self, logger=None, config=None, output_folder="./Output"):
        """
        Initialize RIFT engine with lightweight setup.

        Args:
            logger: Logger instance (creates default if None)
            config: Either a pre-built RiftConfig instance, or a path (str/Path) to a config file
                which will be used to construct a RiftConfig
            output_folder: Output folder for FLIRT signatures (default: ./Output)

        Raises:
            RiftConfigError: If configuration loading fails
        """
        try:
            self.logger = get_logger() if logger is None else logger
            if isinstance(config, RiftConfig):
                self.cfg = config
            else:
                self.cfg = RiftConfig(self.logger, config)
            self.output_folder = Path(output_folder).resolve()
            if not self.output_folder.exists:
                raise RiftEngineError("Invalid output folder!")
            self.output_folder = str(Path(output_folder).resolve())

        except Exception as e:
            raise RiftConfigError(f"Failed to initialize RIFT engine: {e}")

        if not os.path.isdir(self.output_folder):
            raise RiftConfigError(f"{self.output_folder} is not a valid folder destination to store results in!")
        # Always-available components (lightweight)
        self._rift_meta = None

        # Lazy-loaded generation components (heavy initialization)
        self._initialized = False
        self._rift_os = None
        self._rift_gen = None
        self._storage_handler = None
        self._proj_handler = None
        self._cargo_proj_path = None

    @property
    def rift_meta(self):
        """Lazy-load metadata extractor."""
        if self._rift_meta is None:
            self._rift_meta = RiftMeta(logger=self.logger, cfg=self.cfg)
        return self._rift_meta

    def extract_metadata(self, source: Union[List[str], str, Path]) -> Optional[dict]:
        """
        Extract metadata from Rust binaries or strings.

        Args:
            source: Either a list of strings or a file path (str or Path)

        Returns:
            Dictionary containing extracted metadata, or None if extraction failed

        Raises:
            RiftMetadataError: If metadata extraction fails
        """
        try:
            metadata = self.rift_meta.extract_meta(source)
            return metadata
        except FileNotFoundError as e:
            raise RiftMetadataError(f"Binary not found: {e}")
        except Exception as e:
            raise RiftMetadataError(f"Metadata extraction failed: {e}")

    def set_output_folder(self, output_folder):
        """Set new output folder"""
        self.output_folder = str(Path(output_folder).resolve())

    # Backward compatibility alias
    def get_meta(self, source: Union[List[str], str, Path]) -> Optional[dict]:
        """
        Extract metadata from Rust binaries (backward compatibility wrapper).

        Args:
            source: Either a list of strings or a file path (str or Path)

        Returns:
            Dictionary containing extracted metadata (commithash, rust_version, crates, target_triple)
        """
        return self.extract_metadata(source)

    def backend_available(self, fmt):
        """Returns True if the backend for the given signature format is configured."""
        if fmt not in FORMAT_AVAILABILITY:
            raise RiftConfigError(f"Unknown signature format = {fmt}!")
        return getattr(self.cfg, FORMAT_AVAILABILITY[fmt])

    def _ensure_initialized(self, meta, fmt):
        """
        Initialize the generation environment (lazily, on first use).

        Fails only when the backend for the requested format is missing, so a
        Ghidra-only host can generate .fidb files with no IDA installed.
        """
        if not self.backend_available(fmt):
            raise RiftConfigError(
                f"Signature format '{fmt}' is not available. {FORMAT_HINTS[fmt]}"
            )
        if self._initialized:
            return

        try:
            self.logger.info("Initializing signature generation environment...")
            self._rift_os = RiftOs(logger=self.logger, cfg=self.cfg)

            try:
                self._proj_handler = get_project_handler(self._rift_os, self.cfg, self.logger)
            except RiftProjectHandlerError:
                self.logger.error("Could not initialize ProjectHandler!")
                return
            self._storage_handler = StorageHandler(
                self.cfg.work_folder,
                self.cfg.cargo_proj_folder,
                self.output_folder,
                self.logger
            )
            self._rift_gen = RiftGenerator(
                self.cfg,
                self.logger,
                self.rift_meta,
                self._rift_os,
                self._storage_handler,
                self._proj_handler
            )
            self._rift_gen.init_env(meta)

            self._initialized = True
            self.logger.info("Signature generation environment initialized successfully")

        except Exception as e:
            raise FORMAT_ERRORS[fmt](f"Failed to initialize generation environment: {e}")

    def _resolve_output_folder(self, output_folder):
        """
        Returns the absolute output folder, falling back to the default one.

        Must run before _ensure_initialized, which changes the working directory
        to the cargo project and would make a relative path resolve there.
        """
        return str(Path(output_folder).resolve()) if output_folder else self.output_folder

    # ---------------- per-format generation (internal) ----------------

    def _generate_from_binary(self, binary_path, output_folder, fmt):
        """Generates toolchain and crate signatures for a binary in one format."""
        meta = self.extract_metadata(binary_path)
        if not meta:
            raise RiftMetadataError(f"Could not extract metadata from binary: {binary_path}")

        output_path = self._resolve_output_folder(output_folder)
        self._ensure_initialized(meta, fmt)
        try:
            self.logger.info(f"Generating {fmt} signatures for {binary_path}")
            self._rift_gen.gen_toolc_flirt(meta, output_path, formats=(fmt,))
            self._rift_gen.generate_crates_flirt(meta, output_path, formats=(fmt,))
            return output_path
        except Exception as e:
            raise FORMAT_ERRORS[fmt](f"Failed to generate {fmt} signatures: {e}")

    def _generate_compiler_signature(self, meta, output_folder, fmt):
        """Generates the toolchain signature in one format. Returns its path."""
        output_path = self._resolve_output_folder(output_folder)
        self._ensure_initialized(meta, fmt)
        try:
            self.logger.info(
                f"Generating compiler {fmt} signature for {meta.get_target_compiler()}, output_path = {output_path}")
            sig_paths = self._rift_gen.gen_toolc_flirt(meta, output_path, formats=(fmt,))
            return sig_paths[0] if sig_paths else None
        except Exception as e:
            raise FORMAT_ERRORS[fmt](f"Failed to generate compiler {fmt} signature: {e}")

    def _generate_crate_signature(self, meta, crate, output_folder, debug_build, fmt):
        """Generates a single crate's signature in one format. Returns its path."""
        output_path = self._resolve_output_folder(output_folder)
        self._ensure_initialized(meta, fmt)
        try:
            self.logger.info(f"Generating {fmt} signature for {crate.get_id()}, output_path = {output_path}")
            sig_paths = self._rift_gen.generate_crate_flirt(
                meta, crate, output_path, debug_build=debug_build, formats=(fmt,))
            return sig_paths[0] if sig_paths else None
        except Exception as e:
            raise FORMAT_ERRORS[fmt](f"Failed to generate crate {fmt} signature for {crate.get_id()}")

    def _generate_crates_signatures(self, meta, output_folder, fmt):
        """Generates signatures for every crate in the metadata, in one format."""
        output_path = self._resolve_output_folder(output_folder)
        self._ensure_initialized(meta, fmt)
        try:
            self._rift_gen.generate_crates_flirt(meta, output_path, formats=(fmt,))
            return output_path
        except Exception as e:
            raise FORMAT_ERRORS[fmt](f"Failed to generate crates {fmt} signatures: {e}")

    # ---------------- FLIRT (IDA Pro .sig) ----------------

    def generate_flirt_from_binary(self, binary_path: Union[str, Path], output_folder: Optional[str] = None) -> Optional[Path]:
        """
        Generate FLIRT signatures by analyzing a binary file.

        Args:
            binary_path: Path to binary file to analyze
            output_folder: Output folder (uses default if None)

        Returns:
            Path to output folder where signatures were generated

        Raises:
            RiftMetadataError: If metadata extraction fails
            RiftFlirtError: If FLIRT generation fails
        """
        return self._generate_from_binary(binary_path, output_folder, "flirt")

    def generate_compiler_flirt(self, meta, output_folder: Optional[str] = None) -> Optional[Path]:
        """Generate the FLIRT signature for the Rust compiler itself. Returns its path."""
        self.logger.info(f"generate_compiler_flirt output_folder = {output_folder}")
        return self._generate_compiler_signature(meta, output_folder, "flirt")

    def generate_crate_flirt(self, meta, crate, output_folder: Optional[str] = None, debug_build=False):
        """Generates flirt signature for a specific crate"""
        return self._generate_crate_signature(meta, crate, output_folder, debug_build, "flirt")

    def generate_crates_flirt(self, meta, output_folder: Optional[str] = None):
        """Generates FLIRT signatures for a set of crates"""
        return self._generate_crates_signatures(meta, output_folder, "flirt")

    # ---------------- Function ID (Ghidra .fidb) ----------------

    def generate_fid_from_binary(self, binary_path: Union[str, Path], output_folder: Optional[str] = None) -> Optional[Path]:
        """
        Generate Function ID databases by analyzing a binary file.

        Args:
            binary_path: Path to binary file to analyze
            output_folder: Output folder (uses default if None)

        Returns:
            Path to output folder where databases were generated

        Raises:
            RiftMetadataError: If metadata extraction fails
            RiftFidError: If FID generation fails
        """
        return self._generate_from_binary(binary_path, output_folder, "fid")

    def generate_compiler_fid(self, meta, output_folder: Optional[str] = None) -> Optional[Path]:
        """Generate the Function ID database for the Rust compiler itself. Returns its path."""
        self.logger.info(f"generate_compiler_fid output_folder = {output_folder}")
        return self._generate_compiler_signature(meta, output_folder, "fid")

    def generate_crate_fid(self, meta, crate, output_folder: Optional[str] = None, debug_build=False):
        """Generates a Function ID database for a specific crate"""
        return self._generate_crate_signature(meta, crate, output_folder, debug_build, "fid")

    def generate_crates_fid(self, meta, output_folder: Optional[str] = None):
        """Generates Function ID databases for a set of crates"""
        return self._generate_crates_signatures(meta, output_folder, "fid")
