"""
RIFT Metadata handler, extracts metadata from rust binaries
"""

from typing import Union, List
from pathlib import Path
import re
from librift.rift_cfg import RiftConfig
from librift.rift_os import RiftOs
from librift.meta_extractor import MetaExtractor
from librift.rustmeta import RustMetadata
from librift.utils import read_json


class RiftInvalidCompiler(Exception):
    """Exception raised when an invalid compiler pattern is provided."""
    pass

# https://www.codeproject.com/Articles/175482/Compiler-Internals-How-Try-Catch-Throw-are-Interpr
ENV_STRINGS = {
        "Mingw-w64 runtime failure:": "gnu",
        "_CxxThrowException": "msvc",
        "std/src/sys/alloc/uefi.rs": "uefi",
}

RE_RUSTLIB_PATTERN = r".{1,250}[\\|\/](.{1,50}-\d+\.\d+.\d+(-.{1,20})?)[\\|\/].{1,100}\.rs"
RE_COMMITHASH_PATTERN = r".{1,250}rustc[\\|\/]([0-9a-zA-Z]{40})[\\|\/]"

# NOTE: Hardcoded check in compiler pattern if ends with -gnu or -msvc
RE_COMPILER_PATTERN = r"(.{1,70})\-(aarch64|arm64ec|armv5te|armv7a?|armv8r|i[56]86|loongarch64|nvptx64|powerpc64le|powerpc64|powerpc|riscv32i|riscv32im|riscv32imafc|riscv32imac|riscv32imc|riscv64a23|riscv64gc|riscv64imac|s390x|sparc64|sparcv9|thumbv6m|thumbv7em|thumbv7m|thumbv7neon|thumbv8m\.base|thumbv8m\.main|wasm32v1|wasm32|x86_64|arm)\-(.{1,70}(-msvc|-gnu|-uefi))"
re_compiler = re.compile(RE_COMPILER_PATTERN)

def build_rustmeta_from_string(compiler):
    m = re_compiler.match(compiler)
    if m is None:
        raise RiftInvalidCompiler(f"Invalid compiler pattern")
    rust_version = m.group(1)
    arch = m.group(2)
    compiler = None
    compiler_part = m.group(3)

    # Determine filetype based on compiler string
    if "windows" in compiler_part:
        filetype = "PE"
    else:
        filetype = "ELF"

    if compiler_part.endswith("-msvc"):
        compiler = "msvc"
    elif compiler_part.endswith("-uefi"):
        compiler = "uefi"
    elif compiler_part.endswith("-gnu"):
        compiler = "gnu"

    # Extract timestamp from nightly version (e.g., "nightly-2024-01-01" -> "2024-01-01")
    ts = None
    if "nightly" in rust_version:
        nightly_match = re.match(r"nightly-(\d{4}-\d{2}-\d{2})", rust_version)
        if nightly_match:
            ts = nightly_match.group(1)

    return RustMetadata(rust_version=rust_version,
                        version_short=rust_version,
                        arch=arch, compiler=compiler, filetype=filetype, ts=ts)


def build_rustmeta_from_json(logger, rift_cfg, json_file: str):
    """"Build RustMeta object from JSON Input file"""
    json_data = read_json(json_file)
    rift_meta = RiftMeta(logger, rift_cfg)
    # We need to get the rust compiler based on the target triple
    rust_version, ts, version_short = rift_meta.get_rust_version_for_hash(json_data["commithash"])
    rust_meta = RustMetadata(commithash=json_data["commithash"],
                             rust_version=rust_version,
                             version_short=version_short,
                             arch=json_data["arch"],
                             filetype=json_data["filetype"],
                             crates=json_data["crates"],
                             ts=ts)
    rust_meta.compiler = rust_meta.get_compiler_from_target_triple(json_data["target_triple"])
    return rust_meta


def build_rustmeta_from_strings(logger, rift_cfg, strings):
    """Build RustMeta object from input strings"""
    rift_meta = RiftMeta(logger, rift_cfg)
    return rift_meta.extract_meta(strings)


def build_rustmeta_from_binary(logger, rift_cfg, binary_path):
    """Generates RustMeta object from input binary"""
    rift_meta = RiftMeta(logger, rift_cfg, binary_path=binary_path)
    meta = rift_meta.extract_meta(binary_path)
    return meta

class RiftMeta:
    """Factory class for extracting Rust metadata from binaries and strings."""

    def __init__(self, logger, cfg: RiftConfig, binary_path=None):
        """
        Initialize the RiftMeta factory.

        Args:
            logger: Logger instance
            cfg: RiftConfig instance
            binary_path: Optional binary path (for backward compatibility, not recommended)
        """
        self.logger = logger
        self.cfg = cfg

        self.__rustlib_re = re.compile(RE_RUSTLIB_PATTERN)
        self.__commithash_re = re.compile(RE_COMMITHASH_PATTERN)
        self.rift_os = RiftOs(logger=logger, cfg=cfg)
        self.meta_extractor = MetaExtractor(logger=logger, rift_os=self.rift_os)

        # For backward compatibility - store binary path if provided
        self.binary_path = binary_path

    def extract_meta(self, source: Union[List[str], str, Path]) -> RustMetadata:
        """
        Extract metadata from either a list of strings or a file path.

        Args:
            source: Either a list of strings or a file path (str or Path)

        Returns:
            RustMetadata instance containing extracted metadata

        Raises:
            TypeError: If source is neither a list nor a file path
        """
        if isinstance(source, list):
            # Handle list of strings - need to provide filetype and arch separately
            return self._extract_from_strings(source, filetype=None, arch=None)
        elif isinstance(source, (str, Path)):
            return self._extract_from_file(source)
        else:
            raise TypeError(f"extract_meta expects a list of strings or a file path, got {type(source)}")
        
    def _extract_from_strings(self, strings: List[str], filetype=None, arch=None) -> RustMetadata:
        """
        Extract metadata from a list of strings.

        Args:
            strings: List of strings to extract metadata from
            filetype: File type (PE or ELF), if known
            arch: Architecture, if known

        Returns:
            RustMetadata instance containing extracted metadata, or None if extraction failed
        """
        # Local variables only - no instance variable mutation
        commithash = None
        hash_short = None
        crates = set()
        compiler = None
        rust_ver = None
        version_short = None
        ts = None
        env_strings_keys = list(ENV_STRINGS.keys())

        # Apply patterns to extract metadata from strings
        for s in strings:

            # Extract rust commithash and determine rust version
            if commithash is None and (match := self.__commithash_re.match(s)):
                commithash = match.group(1)
                hash_short = commithash[0:9]
                self.logger.debug(f"Determined rustc commit hash = {commithash}")

                # Use helper function to find corresponding version
                rust_ver, ts, version_short = self.get_rust_version_for_hash(commithash)
                if rust_ver is not None:
                    self.logger.info(f"Determined rust version = {rust_ver}")
                continue

            # Extract crate information
            if re.search(r"(github|\.cargo|\.rustup|rustc|library|crates\.io|rust[\\|\/]deps)", s) is not None and (match := self.__rustlib_re.match(s)):
                crate = match.group(1)
                self.logger.debug(f"Extracted crate = {crate}")
                crates.add(crate)

            # Determine compiler environment from strings
            if compiler is None:
                s_stripped = s.strip("\n")
                if s_stripped in env_strings_keys:
                    compiler = ENV_STRINGS[s_stripped]
                    self.logger.debug(f"Determined compiler = {compiler}")

        # Validate that we extracted required metadata
        if compiler is None:
            self.logger.warning(f"Could not determine compiler, setting default compiler to msvc")
            compiler = "msvc"
        if rust_ver is None:
            self.logger.error("Could not determine rust version or compiler!")
            return None

        # Build target triple
        metadata = RustMetadata(
            commithash=commithash,
            hash_short=hash_short,
            crates=list(crates),
            rust_version=rust_ver,
            version_short=version_short,
            compiler=compiler,
            filetype=filetype,
            arch=arch,
            ts=ts
        )

        # Build and set target triple
        try:
            metadata.target_triple = metadata.get_target_triple()
        except ValueError as e:
            self.logger.warning(f"Could not build target triple: {e}")
            metadata.target_triple = None

        return metadata


    def _extract_from_file(self, file_path: Union[str, Path]) -> RustMetadata:
        """
        Extract metadata from a file.

        Args:
            file_path: Path to the file

        Returns:
            RustMetadata instance containing extracted metadata

        Raises:
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Use MetaExtractor to get filetype, arch, and strings
        filetype, arch, strings = self.meta_extractor.extract_from_file(file_path)

        # Extract metadata from strings, passing along filetype and arch
        return self._extract_from_strings(strings, filetype=filetype, arch=arch)

    def get_rust_version_for_hash(self, commithash: str):
        """
        Get Rust version information for a given commit hash.

        Args:
            commithash: Full commit hash or short hash (first 9 characters)

        Returns:
            Tuple of (rust_version, timestamp, version_short) if found, or (None, None, None) if not found
        """
        hash_data = self.cfg.rustc_hashes
        hash_short = commithash[0:9] if len(commithash) >= 9 else commithash

        # Find corresponding version from hash data
        for hash_entry in hash_data:
            entry_hash = hash_entry["git_commit_hash"]
            entry_hash_short = hash_entry["hash_short"]

            if commithash == entry_hash or hash_short == entry_hash_short:
                rust_ver = hash_entry["version"]
                version_short = hash_entry["version_short"]
                ts = hash_entry["ts"]
                return (rust_ver, ts, version_short)

        return (None, None, None)
