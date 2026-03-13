"""
Binary metadata extraction - handles LIEF parsing, architecture detection, and string extraction.
"""

from typing import Union, Optional, List, Tuple
from pathlib import Path
import lief


# Architecture mappings for PE binaries
PE_ARCH_MAP = {
    lief.PE.Header.MACHINE_TYPES.I386: "i686",
    lief.PE.Header.MACHINE_TYPES.AMD64: "x86_64",
    lief.PE.Header.MACHINE_TYPES.ARM: "arm",
    lief.PE.Header.MACHINE_TYPES.ARM64: "aarch64",
    lief.PE.Header.MACHINE_TYPES.ARMNT: "arm",
}

# Architecture mappings for ELF binaries
ELF_ARCH_MAP = {
    lief.ELF.ARCH.I386: "i686",
    lief.ELF.ARCH.X86_64: "x86_64",
    lief.ELF.ARCH.ARM: "arm",
    lief.ELF.ARCH.AARCH64: "aarch64",
    lief.ELF.ARCH.RISCV: "riscv",
    lief.ELF.ARCH.PPC: "powerpc",
    lief.ELF.ARCH.PPC64: "powerpc64",
    lief.ELF.ARCH.MIPS: "mips",
}


class MetaExtractor:
    """Handles binary parsing, architecture detection, and string extraction."""

    def __init__(self, logger, rift_os):
        """
        Initialize the MetaExtractor.

        Args:
            logger: Logger instance for logging operations
            rift_os: RiftOs instance for string extraction
        """
        self.logger = logger
        self.rift_os = rift_os

    def extract_from_file(self, file_path: Union[str, Path]) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Extract file type, architecture, and strings from a binary file.

        Args:
            file_path: Path to the binary file

        Returns:
            Tuple of (filetype, architecture, strings)
            filetype: "PE" or "ELF" or None
            architecture: Architecture string (e.g., "x86_64", "aarch64") or None
            strings: List of extracted strings from the binary
        """
        file_path = Path(file_path)

        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return None, None, []

        # Parse binary to get filetype and architecture
        filetype, arch = self._parse_binary(file_path)

        # Extract strings from binary
        strings = self.rift_os.get_strings(file_path)

        return filetype, arch, strings

    def _parse_binary(self, file_path: Union[str, Path]) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse binary file and determine both filetype and architecture.

        Args:
            file_path: Path to the binary file

        Returns:
            Tuple of (filetype, architecture)
            filetype: "PE" or "ELF" or None if parsing failed
            architecture: Architecture string or None if unknown
        """
        try:
            binary = lief.parse(str(file_path))

            if binary is None:
                self.logger.warning(f"Could not parse binary: {file_path}")
                return None, None

            # Determine file type and architecture for PE binaries
            if binary.format == lief.PE.Binary.FORMATS.PE:
                self.logger.debug("Detected file type: PE")
                filetype = "PE"
                machine = binary.header.machine
                arch = PE_ARCH_MAP.get(machine, str(machine))
                self.logger.debug(f"Detected architecture: {arch}")
                return filetype, arch

            # Determine file type and architecture for ELF binaries
            elif binary.format == lief.EXE_FORMATS.ELF:
                self.logger.debug("Detected file type: ELF")
                filetype = "ELF"
                machine = binary.header.identity_class
                arch = ELF_ARCH_MAP.get(machine, str(machine))
                self.logger.debug(f"Detected architecture: {arch}")
                return filetype, arch

            else:
                self.logger.warning(f"Unknown binary format: {binary.format}")
                return None, None

        except Exception as e:
            self.logger.error(f"Error parsing binary {file_path}: {e}")
            return None, None
