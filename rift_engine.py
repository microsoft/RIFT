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


class RiftFlirtError(RiftEngineError):
    """FLIRT generation errors."""
    pass


class RiftEngine:
    """Core engine for Rust binary analysis and FLIRT signature generation."""

    def __init__(self, logger=None, config_path=None, output_folder="./Output"):
        """
        Initialize RIFT engine with lightweight setup.

        Args:
            logger: Logger instance (creates default if None)
            config_path: Path to config file (default: uses RiftConfig default)
            output_folder: Output folder for FLIRT signatures (default: ./Output)

        Raises:
            RiftConfigError: If configuration loading fails
        """
        try:
            self.logger = get_logger() if logger is None else logger
            self.cfg = RiftConfig(self.logger, config_path)
            self.output_folder = str(Path(output_folder).resolve())
        except Exception as e:
            raise RiftConfigError(f"Failed to initialize RIFT engine: {e}")

        if not os.path.isdir(self.output_folder):
            raise RiftConfigError(f"{self.output_folder} is not a valid folder destination to store results in!")
        # Always-available components (lightweight)
        self._rift_meta = None

        # Lazy-loaded FLIRT components (heavy initialization)
        self._flirt_initialized = False
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

    def _ensure_flirt_initialized(self, meta):
        """
        Initialize FLIRT generation components (called lazily on first use).

        This performs heavy initialization including:
        - Setting up cargo projects
        - Initializing file system structures
        - Configuring FLIRT generator

        Raises:
            RiftFlirtError: If FLIRT initialization fails
        """
        if self._flirt_initialized:
            return

        try:
            self.logger.info("Initializing FLIRT generation environment...")

            # Initialize components needed for FLIRT generation
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
            # Create FLIRT generator
            self._rift_gen = RiftGenerator(
                self.cfg,
                self.logger,
                self.rift_meta,
                self._rift_os,
                self._storage_handler,
                self._proj_handler
            )
            self.logger.debug(f"Generating FLIRT environment")
            # Initialize FLIRT environment
            self._rift_gen.init_env(meta)

            self._flirt_initialized = True
            self.logger.info("FLIRT generation environment initialized successfully")

        except Exception as e:
            raise RiftFlirtError(f"Failed to initialize FLIRT environment: {e}")

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
        # Extract metadata from binary
        meta = self.extract_metadata(binary_path)
        if not meta:
            raise RiftMetadataError(f"Could not extract metadata from binary: {binary_path}")

        # Ensure FLIRT environment is initialized
        self._ensure_flirt_initialized(meta)

        # Generate FLIRT signatures
        try:
            output_path = output_folder or self.output_folder
            self.logger.info(f"Generating FLIRT signatures for {binary_path}")
            self._rift_gen.gen_toolc_flirt(meta, output_path)
            self._rift_gen.generate_crates_flirt(meta, output_path)
            return output_path

        except Exception as e:
            raise RiftFlirtError(f"Failed to generate FLIRT signatures: {e}")

    def generate_compiler_flirt(self, meta, output_folder: Optional[str] = None) -> Optional[Path]:
        """
        Generate FLIRT signature for the Rust compiler itself.

        Args:
            meta: RustMetadata instance with compiler information
            output_folder: Output folder (uses default if None)

        Returns:
            Path to output folder where signature was generated

        Raises:
            RiftFlirtError: If FLIRT generation fails
        """
        self.logger.info(f"generate_compiler_flirt output_folder = {output_folder}")
        # Ensure FLIRT environment is initialized
        self._ensure_flirt_initialized(meta)

        try:
            output_path = output_folder or self.output_folder
            self.logger.info(f"Generating compiler FLIRT signature for {meta.get_target_compiler()}, output_path = {output_path}")
            output_path = self._rift_gen.gen_toolc_flirt(meta, output_path)
            return output_path

        except Exception as e:
            raise RiftFlirtError(f"Failed to generate compiler FLIRT signature: {e}")

    def generate_crate_flirt(self, meta, crate, output_folder: Optional[str] = None, debug_build=False):
        """Generates flirt signature for a specific crate"""
        self._ensure_flirt_initialized(meta)
        try:
            output_path = output_folder or self.output_folder
            self.logger.info(f"Generating FLIRT signature for {crate.get_id()}, output_path = {output_path}")
            output_path = self._rift_gen.generate_crate_flirt(meta, crate, output_path, debug_build=debug_build)
            return output_path
        except Exception as e:
            raise RiftFlirtError(f"Failed to generate crate FLIRT signature for {crate.get_id()}")

    def generate_crates_flirt(self, meta, output_folder: Optional[str] = None):
        """Generates FLIRT signatures for a set of crates"""
        self._ensure_flirt_initialized(meta)
        try:
            output_path = output_folder or self.output_folder
            self._rift_gen.generate_crates_flirt(meta, output_path)
            return output_path
        except Exception as e:
            raise RiftFlirtError(f"Failed to generate crates FLIRT signatures: {e}")
