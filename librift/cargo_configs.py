import os
import configparser
from abc import ABC, abstractmethod


class CargoConfigBase(ABC):
    """
    Abstract base class for Cargo configuration file handlers.

    This class provides common functionality for managing various Cargo-related
    configuration files (Cargo.toml, rust-toolchain, config.toml, etc.).
    """

    def __init__(self, cargo_proj_path, config_file_path, logger):
        """
        Initialize the configuration base handler.

        Args:
            cargo_proj_path: Path to the Cargo project root directory
            config_file_path: Full path to the specific configuration file
        """
        self.cargo_proj_path = cargo_proj_path
        self.config_file_path = config_file_path
        self.logger = logger

    def _init_file(self):
        """
        Create an empty configuration file if it doesn't exist.

        This is a helper method to initialize a new config file.
        """
        open(self.config_file_path, "w+").close()

    @abstractmethod
    def _update_config(self):
        """
        Abstract method to persist configuration changes to disk.

        Subclasses must implement this method to define how their
        specific configuration should be written to the file.
        """
        pass

# TODO: Needs function, which removes existing crates .. all of them in case a cargo project is reused
class CargoToml(CargoConfigBase):
    """
    Manages the Cargo.toml configuration file.

    This class handles operations on the Cargo.toml file, including adding/removing
    dependencies, reading crate information, and setting project metadata like edition.
    """

    def __init__(self, cargo_proj_path, logger):
        """
        Initialize the CargoToml handler.

        Args:
            cargo_proj_path: Path to the Cargo project root directory

        Raises:
            Exception: If Cargo.toml file cannot be initialized or doesn't exist
        """
        self.cargo_toml_path = os.path.join(cargo_proj_path, "Cargo.toml")
        super().__init__(cargo_proj_path, self.cargo_toml_path, logger)
        self.cargo_toml = None
        init_success = self.read_toml(clean_crates=True)
        if not init_success:
            raise FileNotFoundError("Could not initialize Config.toml file!")

    def read_toml(self, clean_crates=False):
        """
        Read and parse the Cargo.toml file.

        Args:
            clean_crates: If True, remove all entries under the 'dependencies' section

        Returns:
            bool: True if the file was successfully read, False otherwise
        """
        if os.path.isfile(self.cargo_toml_path):
            self.cargo_toml = configparser.ConfigParser()
            self.cargo_toml.read(self.cargo_toml_path)
            if clean_crates:
                if self.cargo_toml.has_section('dependencies'):
                    # Remove all options (crate entries) from the dependencies section
                    for option in self.cargo_toml.options('dependencies'):
                        self.cargo_toml.remove_option('dependencies', option)
                    self.logger.info("Removed all crate entries from 'dependencies' section")
        else:
            self.logger.error(f"Cargo.toml = {self.cargo_toml_path} does not exist!")
            return False
        return True

    def add_crate(self, crate):
        """
        Add a single crate dependency to the Cargo.toml file.

        Args:
            crate: Crate object containing name and version information

        Returns:
            bool: True if the crate was successfully added
        """
        crate_section = "dependencies"
        # Ensure the [dependencies] section exists
        if crate_section not in self.cargo_toml.sections():
            self.cargo_toml.add_section(crate_section)
            self.logger.info(f"Added section 'dependencies' to {self.cargo_toml_path}")

        # Add the crate with its version
        self.cargo_toml.set(crate_section, crate.name, crate.get_cfg_crate_version())
        self.logger.debug(f"Added crate: {crate.name} = {'[LATEST]' if crate.version == '' else crate.version}")

        # Persist changes to file
        self._update_config()
        return True

    def remove_crate(self, crate):
        """
        Remove a single crate dependency from the Cargo.toml file.

        Args:
            crate: Crate object containing the name to remove
        """
        # Re-read to ensure we have the latest state
        self.cargo_toml.read(self.cargo_toml_path)
        self.cargo_toml.remove_option("dependencies", crate.name)
        self._update_config()

    def remove_crates(self):
        """
        Remove all crate dependencies from Cargo.toml, keeping the [dependencies] header.
        """
        # Re-read to ensure we have the latest state
        self.cargo_toml.read(self.cargo_toml_path)

        if self.cargo_toml.has_section('dependencies'):
            for option in self.cargo_toml.options('dependencies'):
                self.cargo_toml.remove_option('dependencies', option)
            self.logger.info("Removed all crates from 'dependencies' section")
            self._update_config()

    def _update_config(self):
        """
        Persist the Cargo.toml configuration to disk.

        Returns:
            bool: True if the write operation was successful
        """
        with open(self.cargo_toml_path, "w") as f:
            self.cargo_toml.write(f)
        return True

    def get_crate(self, name):
        """
        Get the version information for a specific crate dependency.

        Args:
            name: Name of the crate to retrieve

        Returns:
            str: Version specification for the crate
        """
        # Re-read to ensure we have the latest state
        self.cargo_toml.read(self.cargo_toml_path)
        return self.cargo_toml["dependencies"][name]

    def set_edition(self, edition):
        """
        Set the Rust edition for the project.

        Args:
            edition: Edition year as a string (e.g., "2021", "2018", "2015")
        """
        # Format edition with quotes as required by TOML
        edition = f"\"{edition}\""
        self.cargo_toml.read(self.cargo_toml_path)
        self.cargo_toml.set("package", "edition", edition)


class RustToolchainCfg(CargoConfigBase):
    """
    Manages the rust-toolchain configuration file.

    This class handles reading, creating, and updating the rust-toolchain file
    which specifies the Rust compiler toolchain to use for the project.
    """

    def __init__(self, cargo_proj_path, logger):
        """
        Initialize the RustToolchainCfg handler.

        Args:
            cargo_proj_path: Path to the Cargo project root directory
            logger: Optional logger instance for logging operations
        """
        self.rt_path = os.path.join(cargo_proj_path, "rust-toolchain")
        super().__init__(cargo_proj_path, self.rt_path, logger)
        self.cfg_tc = None
        self.logger = logger

    def _update_config(self):
        """
        Persist the toolchain configuration to the rust-toolchain file.

        Returns:
            bool: True if the write operation was successful
        """
        with open(self.rt_path, "w") as f:
            self.cfg_tc.write(f)
        return True

    def create(self, toolchain_data):
        """
        Creates the rust-toolchain file with the provided toolchain configuration.

        This method initializes a new rust-toolchain file or reads an existing one,
        then populates it with the toolchain settings specified in toolchain_data.

        Args:
            toolchain_data: Dictionary containing toolchain configuration keys and values.
                           Common keys include 'channel', 'components', 'targets', etc.

        Returns:
            bool: True if the toolchain configuration was successfully created

        Example:
            toolchain_data = {
                'channel': 'nightly',
                'components': 'rustfmt, clippy',
                'targets': 'x86_64-unknown-linux-gnu'
            }
        """
        self.cfg_tc = configparser.ConfigParser()

        # Read existing file if it exists
        if os.path.isfile(self.rt_path):
            self.cfg_tc.read(self.rt_path)

        # Ensure the [toolchain] section exists
        toolchain_section = "toolchain"
        if toolchain_section not in self.cfg_tc.sections():
            self.cfg_tc.add_section(toolchain_section)
            if self.logger:
                self.logger.debug(f"Added section 'toolchain' to {self.rt_path}")

        # Populate the toolchain configuration
        for key in toolchain_data.keys():
            val = toolchain_data[key]
            self.cfg_tc.set(toolchain_section, key, val)
            if self.logger:
                self.logger.debug(f"Added {key} = {val} to {self.rt_path}")

        # Persist changes to file
        self._update_config()
        return True

    def configure(self, toolchain_data):
        """
        Updates existing toolchain configuration with new values.

        Args:
            toolchain_data: Dictionary containing toolchain configuration keys and values

        Returns:
            bool: True if the configuration was successfully updated
        """
        # Currently an alias for create(), but can be extended for different behavior
        return self.create(toolchain_data)

class CargoCfg(CargoConfigBase):
    """
    Manages the .cargo/config.toml configuration file.

    This class handles operations on the Cargo config.toml file, which contains
    build configuration such as target architectures, linker settings, and other
    build-time options.
    """

    def __init__(self, cargo_proj_path, logger):
        """
        Initialize the CargoCfg handler.

        Creates the .cargo directory if it doesn't exist.

        Args:
            cargo_proj_path: Path to the Cargo project root directory
            logger: Optional logger instance for logging operations
        """
        # Ensure .cargo directory exists
        cargo_cfg_dir = os.path.join(cargo_proj_path, ".cargo")
        os.makedirs(cargo_cfg_dir, exist_ok=True)

        self.cargo_cfg_path = os.path.join(cargo_cfg_dir, "config.toml")
        super().__init__(cargo_proj_path, self.cargo_cfg_path, logger)
        self.cfg_cargo = None

    def create(self, config_data):
        """
        Create or update the .cargo/config.toml file with build configuration.

        This method initializes the config.toml file if it doesn't exist and populates
        it with build settings such as target architectures and linker flags.

        Args:
            config_data: Dictionary containing build configuration keys and values.
                        Common keys include 'target', 'rustflags', etc.
        """
        # Initialize file if it doesn't exist
        if not os.path.isfile(self.cargo_cfg_path):
            self._init_file()

        # Initialize and read the config
        self.cfg_cargo = configparser.ConfigParser()
        self.cfg_cargo.read(self.cargo_cfg_path)

        # Ensure the [build] section exists
        build_section = "build"
        if build_section not in self.cfg_cargo.sections():
            self.cfg_cargo.add_section(build_section)
            if self.logger:
                self.logger.info(f"Added section '{build_section}' to {self.cargo_cfg_path}")

        # Populate the build configuration
        for key in config_data.keys():
            val = config_data[key]
            self.cfg_cargo.set(build_section, key, val)
            if self.logger:
                self.logger.info(f"Added {key} = {val} to {self.cargo_cfg_path}")

        # Persist changes to file
        self._update_config()

    def _update_config(self):
        """
        Persist the Cargo config.toml configuration to disk.

        Returns:
            bool: True if the write operation was successful
        """
        with open(self.cargo_cfg_path, "w") as f:
            self.cfg_cargo.write(f)
        return True
