import os
from librift.cargo_configs import CargoToml, RustToolchainCfg, CargoCfg
from librift.rift_cfg import RiftConfig
from librift.rift_os import RiftOs
from librift.utils import get_latest_dir,is_cargo_proj,gen_random_name


class RiftProjectHandlerError(Exception):
    """Base exception for RIFT API errors."""
    pass

def get_project_handler(rift_os: RiftOs, cfg: RiftConfig, logger):
    """Get or create project handler. Args: rift_os (RiftOs), cfg (RiftConfig), logger. Returns: ProjectHandler instance."""
    logger.info(f"Configuring RIFT to use latest cargo project from {cfg.cargo_proj_folder}")
    proj_handler = None
    cargo_proj_dir = get_latest_dir(cfg.cargo_proj_folder)

    if cargo_proj_dir is None:
        cargo_proj_dir = os.path.join(cfg.cargo_proj_folder, gen_random_name(8))
        logger.info(f"Initializing new cargo project at {cargo_proj_dir}")
        cargo_proj_dir = rift_os.init_cargo_project(cargo_proj_dir)
    else:
        logger.info(f"Using existing cargo project {cargo_proj_dir}, cleaning up ..")
        rift_os.cleanup_project(cargo_proj_dir)
        rift_os.clean_configs(cargo_proj_dir)
        # Now delete the existing rust-toolchain, .cargo/config.toml files and update the Cargo.toml file to remove all existing dependencies
    if not is_cargo_proj(cargo_proj_dir):
        raise RiftProjectHandlerError("Could not obtain valid cargo project dir")

    proj_handler = ProjectHandler(cargo_proj_dir, logger, rift_os)
    return proj_handler


class ProjectHandler():

    def __init__(self, cargo_proj_path, logger, rift_os: RiftOs = None):
        """Initialize the config handler."""

        self.logger = logger
        self.cargo_proj_path = cargo_proj_path
        self.rift_os = rift_os

        # Initialize config handlers using cargo_configs classes
        self.cargo_toml = None
        self.rust_toolchain = None
        self.cargo_cfg = None

    def init_toml_config(self):
        """Initialize all configurations, Cargo.toml, Config.toml, toolchain."""
        try:
            self.cargo_toml = CargoToml(self.cargo_proj_path, self.logger)
            # Set edition 2021 as default for now
            # self.cargo_toml.set_edition("2021")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Cargo.toml: {e}")
            return False
    
    def init_cargo_config(self, meta):
        """Creates the .cargo/Config.toml file that contains information about which architectures we compile for."""
        self.cargo_cfg = CargoCfg(self.cargo_proj_path, self.logger)
        cargo_config_data = {"target": f"\"{meta.get_target_triple()}\""}
        self.cargo_cfg.create(cargo_config_data)
        return True

    def insert_crate(self, crate):
        """Insert a single crate"""
        return self.cargo_toml.add_crate(crate)

    def init_toolchain_config(self, meta):
        """Creates the rust-toolchain file that contains information about the toolchain to use"""
        self.rust_toolchain = RustToolchainCfg(self.cargo_proj_path, self.logger)
        tc_config_data = {"channel": f"\"{meta.get_channel()}\"", "targets": f"[ \"{meta.get_target_triple()}\" ]"}
        self.rust_toolchain.create(tc_config_data)
        return True
    
    def get_crate_version(self, crate):
        """Returns the configured version for the crate."""
        return self.cargo_toml.get_crate(crate)

    def update_crate(self, crate, val):
        """Updates the version for the specific create."""
        self.cargo_toml.update_crate(crate, val)

    def remove_crate(self, crate):
        """Removes a single crate from the config file."""
        self.cargo_toml.remove_crate(crate)

    def reset_project(self):
        """Reset the cargo project by running cargo clean."""
        if self.rift_os is None:
            self.logger.error("Cannot reset project: rift_os not initialized")
            return False
        self.rift_os.cleanup_project(self.cargo_proj_path)
        self.logger.info(f"Reset cargo project at {self.cargo_proj_path}")
        return True

