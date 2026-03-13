"""
RustCrate class for representing Rust crates with name and version.
"""


class RustCrate:

    def __init__(self, name, version):
        """Init."""
        self.name = name
        self.version = version

    def get_cfg_crate_version(self):
        """Get crate version for Cargo.toml config. Args: None. Returns: str: Formatted version string."""
        if self.version is None or self.version == "":
            return "\"*\""
        return f"\"={self.version}\""

    def get_id(self):
        """Get crate identifier. Args: None. Returns: str: Crate name with optional version (name@version)."""
        if self.version is None or self.version == "":
            return f"{self.name}"
        return f"{self.name}@{self.version}"

            
