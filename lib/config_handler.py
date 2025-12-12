import os
import configparser



class ConfigHandler():

    def __init__(self, proj_path, logger):
        """Initialize the config handler."""

        self.logger = logger
        self.proj_path = proj_path

        # Build path to Cargo.toml. It contains all crates that should be
        # compiled
        self.cargo_proj_path = os.path.join(proj_path, "Cargo.toml")

        # Build path to toolchain file. It contains compiler
        # specific information
        self.tc_toml_path = os.path.join(proj_path, "rust-toolchain")
        
        # Build path to config.toml. It contains information which 
        # architectures the libraries should be compiled for
        self.cfg_toml_path = os.path.join(proj_path, ".cargo")
        self.cfg_toml_path = os.path.join(self.cfg_toml_path, "config.toml")

        # Init variables holding configparse instances
        self.cfg_cargo = None
        self.cfg_tc = None
        self.cfg_proj = None


    def init_proj_config(self):
        """Initialize all configurations, Cargo.toml, Config.toml, toolchain."""
        if os.path.isfile(self.cargo_proj_path):

            self.cfg_proj = configparser.ConfigParser()
            self.cfg_proj.read(self.cargo_proj_path)
        else:
            self.logger.error(f"Config.toml = {self.cargo_proj_path} does not exist yet!")
            return False
        return True

    def create_cargo_config(self, cargo_config_data):
        """Creates the .cargo/Config.toml file that contains information about which architectures we compile for."""
        cargo_folder_path = os.path.join(self.proj_path, ".cargo")
        os.makedirs(cargo_folder_path, exist_ok=True)

        self.cfg_cargo = configparser.ConfigParser()
        if os.path.isfile(self.cfg_toml_path):
            self.cfg_cargo.read(self.cfg_toml_path)

        build_section = "build"
        if build_section not in self.cfg_cargo.sections():
            self.cfg_cargo.add_section(build_section)
            self.logger.info(f"Added section '{build_section}' to {self.cfg_toml_path}")
        
        for key in cargo_config_data.keys():
            val = cargo_config_data[key]
            self.cfg_cargo.set(build_section, key, val)
            self.logger.info(f"Added {key} = {val} to {self.cfg_toml_path}")

        self.__update_config(self.cfg_cargo, self.cfg_toml_path)        
        
        return True

    def insert_crates(self, crates_data):
        """Inserts all identified crates into the Cargo.toml file."""
        
        # Add section if necessary
        EXCL_LIST = [".cargo", "github.com", "\\"]
        crate_section = "dependencies"
        if crate_section not in self.cfg_proj.sections():
            self.cfg_proj.add_section(crate_section)
            self.logger.info(f"Added section 'dependencies' to {self.cargo_proj_path}")
        
        # Iterate through all crates we identified and add one after another
        for crate in crates_data.keys():

            #TODO: Extremely ugly, this should be fixed in the static analyser
            if any(string in crate for string in EXCL_LIST):
                continue
            version = crates_data[crate]
            # if version == "NO_VERSION":
            #    if not exclude_no_ver:
            #        version = "\"*\""
            #    else:
            #        continue
            self.cfg_proj.set(crate_section, crate, version)
            self.logger.debug(f"Added crate: {crate} = {version}")
        
        # Persist updates
        self.__update_config(self.cfg_proj, self.cargo_proj_path)

        return True

    def create_toolchain_config(self, toolchain_data):
        """Creates the rust-toolchain file that contains information about the toolchain to use"""
        
        self.cfg_tc = configparser.ConfigParser()
        if os.path.isfile(self.tc_toml_path):
            self.cfg_tc.read(self.tc_toml_path)
        toolchain_section = "toolchain"
        if toolchain_section not in self.cfg_tc.sections():
            self.cfg_tc.add_section(toolchain_section)
            self.logger.debug(f"Added section toolchain to {self.tc_toml_path}")
        
        for key in toolchain_data.keys():
            val = toolchain_data[key]
            self.cfg_tc.set(toolchain_section, key, val)
            self.logger.debug(f"Added {key} = {val} to {self.tc_toml_path}")
        
        self.__update_config(self.cfg_tc, self.tc_toml_path)
        return True
    
    def get_crate_version(self, crate):
        """Returns the configured version for the crate."""
        self.cfg_proj.read(self.cargo_proj_path)
        return self.cfg_proj["dependencies"][crate]
    
    def update_crate(self, crate, val):
        """Updates the version for the specific crate."""
        self.cfg_proj.read(self.cargo_proj_path)
        self.cfg_proj["dependencies"][crate] = val
        self.logger.info(f"Updated crate {crate} = {val}")
        self.__update_config(self.cfg_proj, self.cargo_proj_path)

    def downgrade_edition(self):
        """Downgrades configured edition."""
        downgrade_dict = {"\"2024\"": "\"2021\"",
                          "\"2021\"": "\"2018\"",
                          "\"2018\"": "\"2015\""}
        self.cfg_proj.read(self.cargo_proj_path)
        curr_edition = self.cfg_proj["package"]["edition"]
        self.cfg_proj.set("package", "edition", downgrade_dict[curr_edition])
        self.__update_config(self.cfg_proj, self.cargo_proj_path)

    def remove_crate(self, crate):
        """Removes a single create from the config file."""

        self.cfg_proj.read(self.cargo_proj_path)
        self.cfg_proj.remove_option("dependencies", crate)
        self.__update_config(self.cfg_proj, self.cargo_proj_path)

    def __update_config(self, cfg, path):
        with open(path, "w") as f:
            cfg.write(f)
        return True


