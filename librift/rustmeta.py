"""
RustMetadata class for encapsulating metadata extracted from Rust binaries.
"""

import re
from librift.crate import RustCrate

SUPPORTED_FILETYPES = ["ELF", "PE"]
SUPPORTED_COMPILERS = ["msvc", "gnu", "uefi"]


class RustMetadata:
    """Encapsulates all metadata extracted from a Rust binary."""

    def __init__(self,
                 commithash=None,
                 hash_short=None,
                 crates=None,
                 arch=None,
                 target_triple=None,
                 rust_version=None,
                 version_short=None,
                 compiler=None,
                 filetype=None,
                 ts=None):

        self.commithash = commithash
        self.hash_short = hash_short
        # Initialize crates as a set, handling both list and set inputs
        if crates is None:
            self.crates = set()
        elif isinstance(crates, set):
            self.crates = crates
        elif isinstance(crates, list):
            self.crates = self._validate_and_convert_crates(crates)
        else:
            self.crates = set()

        self.arch = arch
        self.target_triple = target_triple
        self.rust_version = rust_version
        self.version_short = version_short
        self.compiler = compiler
        self.filetype = filetype
        self.ts = ts  # timestamp for nightly builds

    def get_target_triple(self):
        """
        Build the target triple from the metadata.

        Returns:
            Target triple string

        Raises:
            ValueError: If filetype or compiler is invalid/missing
        """
        if self.filetype not in SUPPORTED_FILETYPES:
            raise ValueError(f"Invalid filetype: {self.filetype}")
        if self.compiler not in SUPPORTED_COMPILERS:
            raise ValueError(f"Invalid compiler: {self.compiler}")

        target_triple = f"{self.arch}"
        if self.filetype == "PE":
            target_triple += f"-pc-windows"
        else:
            target_triple += f"-unknown-linux"
        target_triple += f"-{self.compiler}"
        return target_triple


    def get_triple_suffix(self):
        """Get target triple suffix. Args: None. Returns: str: Triple suffix like 'pc-windows-msvc'."""
        triple_suffix = ""
        if self.filetype == "PE":
            triple_suffix += "pc-windows"
        else:
            triple_suffix += "unknown-linux"
        triple_suffix += f"-{self.compiler}"
        return triple_suffix

    def get_channel(self):
        """Returns channel"""
        if "nightly" in self.rust_version:
            return f"nightly-{self.ts}"
        else:
            return self.version_short

    def get_rustc_flirt_name(self):
        """Returns flirt signature name for rust compiler"""
        return f"rustc-{self.get_rust_version()}-{self.get_target_triple()}.sig"

    def get_flirt_name(self, crate):
        if crate.version != "":
            return f"{crate.name}-{crate.version}-{self.get_rust_version()}-{self.get_target_triple()}.sig"
        else:
            return f"{crate.name}-{self.get_rust_version()}-{self.get_target_triple()}.sig"

    def get_rust_version(self):
        """Returns the rust version."""
        if "nightly" in self.rust_version:
            return f"nightly-{self.ts}"
        else:
            return self.version_short

    def get_target_edition(self):
        """Returns the target edition for the current rust project based on timestamp"""
        available_editions = ["2015", "2018", "2021"]
        if self.ts is None:
            return available_editions[0]

        # Extract year from timestamp (format: YYYY-MM-DD)
        year = int(self.ts.split("-")[0])

        if year < 2018:
            return "2015"
        elif year < 2021:
            return "2018"
        else:
            return "2021" 

    def get_target_compiler(self):
        """
        Generate the target compiler string.

        Returns:
            Target compiler string combining rust version and target triple
        """
        if self.target_triple is None:
            self.target_triple = self.get_target_triple()
        return f"{self.get_rust_version()}-{self.target_triple}"

    def to_dict(self):
        """
        Convert metadata to dictionary format for backward compatibility.

        Returns:
            Dictionary containing all metadata fields
        """
        return {
            "commithash": self.commithash,
            "rust_version": self.rust_version,
            "version_short": self.version_short,
            "crates": list(self.crates),  # Always convert set to list for JSON serialization
            "target_triple": self.target_triple,
            "compiler": self.compiler,
            "arch": self.arch,
            "filetype": self.filetype
        }

    def _validate_and_convert_crates(self, crates):
        """
        Validate and convert crates list/set to a set, filtering invalid formats.

        Args:
            crates: List or set of crate strings

        Returns:
            set: Validated set of crates with proper format (name-version)
        """
        validated_crates = set()
        for crate in crates:
            # Validate format: name-version (e.g., "serde-1.0.185")
            # Also allow special crates without version: "std", "core", "alloc", "backtrace", "panic_unwind"
            if re.match(r"(.*)-(\d+\..*)", crate):
                validated_crates.add(crate)
        return validated_crates

    def add_crate(self, crate):
        """
        Add a single crate to the set.

        Args:
            crate (str): Crate string in format "name-version"
        """
        if re.match(r"(.*)-(\d+\..*)", crate):
            self.crates.add(crate)

    def get_crates(self):
        """
        Build list of RustCrate objects from the crate strings.

        Returns:
            list: List of RustCrate objects
        """
        crates = []
        for crate in self.crates:
            # Parse crate string: name-version (e.g., "color-spantrace-0.2.0")
            m = re.match(r"(.*)-(\d+\..*)", crate)
            if m:
                # Create RustCrate object with name and version
                crates.append(RustCrate(m.group(1), m.group(2)))
        return crates

    def get_crates_list(self):
        """
        Returns crates as a list of strings.

        Returns:
            list: Sorted list of crate strings for consistent ordering
        """
        return sorted(list(self.crates))

    def get_compiler_from_target_triple(self, target_triple):
        """
        Parse the target triple and extract the compiler.

        Args:
            target_triple (str): Target triple string (e.g., "x86_64-pc-windows-msvc")

        Returns:
            str: Compiler name ("msvc", "gnu", or "uefi"), or None if not found
        """
        for compiler in SUPPORTED_COMPILERS:
            if compiler in target_triple:
                return compiler
        return None

    def print(self):
        """
        Print metadata information in a formatted way.
        """
        print("=" * 50)
        print("RIFT Metadata")
        print("=" * 50)
        print(f"Rust Version:    {self.rust_version or 'Unknown'}")
        print(f"Version Short:   {self.version_short or 'Unknown'}")
        print(f"Timestamp:       {self.ts or 'Unknown'}")
        print(f"Commit Hash:     {self.commithash or 'Unknown'}")
        print(f"Architecture:    {self.arch or 'Unknown'}")
        print(f"File Type:       {self.filetype or 'Unknown'}")
        print(f"Compiler:        {self.compiler or 'Unknown'}")
        print(f"Target Triple:   {self.target_triple or 'Unknown'}")

        if self.crates:
            print(f"Crates ({len(self.crates)}):")
            for crate in sorted(self.crates):
                print(f"  - {crate}")
        else:
            print("Crates:          None detected")
        print("=" * 50)