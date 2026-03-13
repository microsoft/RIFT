"""OS-related functionality for RIFT."""

from typing import List
from librift.rift_cfg import RiftConfig
from librift.utils import exec_cmd
import os

class RiftOs:
    """Encapsulates OS-related functionality for RIFT."""

    def __init__(self, logger, cfg: RiftConfig):
        """
        Initialize RiftOs with logger and configuration.

        Args:
            logger: Logger instance for logging messages
            cfg: RiftConfig instance containing configuration settings
        """
        self.logger = logger
        self.cfg = cfg

    def get_strings(self, file_path) -> List[str]:
        """
        Extract strings from a binary file using the configured StringsTool.

        Args:
            file_path: Path to the binary file to extract strings from (str or Path)

        Returns:
            List of distinct strings found in the file
        """
        file_path = str(file_path)

        if not self.cfg.strings or self.cfg.strings == "NOT_SET":
            self.logger.error("StringsTool is not configured in config file")
            return []

        cmd = [self.cfg.strings, file_path]

        returncode, stdout, stderr = exec_cmd(cmd, capture_output=True, check=False)

        if returncode != 0:
            self.logger.error(f"StringsTool failed with return code {returncode}")
            if stderr:
                self.logger.error(f"Error: {stderr}")
            return []

        if not stdout:
            self.logger.warning(f"No output from StringsTool for file: {file_path}")
            return []

        strings_list = stdout.strip().split('\n')
        distinct_strings = list(set(line.strip() for line in strings_list if line.strip()))

        self.logger.debug(f"Extracted {len(distinct_strings)} distinct strings from {file_path}")
        return distinct_strings

    def get_installed_toolchains(self):
        """List all installed toolchains. Args: None. Returns: list: List of installed toolchain strings."""
        cmd = ["rustup", "toolchain", "list"]
        output = []
        code, stdout, _ = exec_cmd(cmd, True)
        if code != 0:
            self.logger.error(f"Failed querying installed toolchains!")
            return output
        output = stdout.split("\n")
        return output

    def install_target_compiler(self, target_compiler):
        """Install a specific target compiler. Args: target_compiler (str). Returns: bool: True if successful."""
        cmd = ["rustup", "toolchain", "install", target_compiler]
        code, _, stderr = exec_cmd(cmd, True)
        if code != 0:
            self.logger.error(stderr)
            return False
        return True

    def add_target(self, target):
        """Add a target to rustup. Args: target (str). Returns: bool: True if successful."""
        cmd = ["rustup", "target", "add", target]
        code, _, _ = exec_cmd(cmd, False)
        if code != 0:
            return False
        return True

    def get_added_targets(self):
        """Get list of installed targets. Args: None. Returns: list: List of installed target strings."""
        cmd = ["rustup", "target", "list"]
        output = []
        code, stdout, _ = exec_cmd(cmd, True)
        if code != 0:
            self.logger.error(f"Failed querying added targets!")
            return output
        lines = stdout.split("\n")
        for target in lines:
            if "(installed)" in target:
                target = target.split(" ")[0]
                output.append(target)
        return output

    def cleanup_project(self, cargo_proj_path):
        """Run cargo clean on project. Args: cargo_proj_path (str). Returns: list: Empty list."""
        curdir = os.getcwd()
        self.set_dir(cargo_proj_path)
        cmd = ["cargo", "clean"]
        output = []
        code, _, stderr = exec_cmd(cmd, True, True)
        if code != 0:
            self.logger.error("Failed cleaning up cargo project!")
            self.logger.error(stderr)
        self.set_dir(curdir)
        return output
    
    def clean_configs(self, cargo_proj_path):
        """Cleans up the existing config files"""
        # Delete rust-toolchain file
        rust_toolchain_path = os.path.join(cargo_proj_path, "rust-toolchain")
        if os.path.isfile(rust_toolchain_path):
            try:
                os.remove(rust_toolchain_path)
                self.logger.info(f"Deleted {rust_toolchain_path}")
            except Exception as e:
                self.logger.error(f"Failed to delete {rust_toolchain_path}: {e}")

        # Delete config.toml in .cargo folder
        cargo_config_path = os.path.join(cargo_proj_path, ".cargo", "config.toml")
        if os.path.isfile(cargo_config_path):
            try:
                os.remove(cargo_config_path)
                self.logger.info(f"Deleted {cargo_config_path}")
            except Exception as e:
                self.logger.error(f"Failed to delete {cargo_config_path}: {e}")

    def init_cargo_project(self, cargo_proj_path):
        """Initialize a cargo project at the given path."""
        if os.path.isdir(cargo_proj_path):
            self.logger.error(f"{cargo_proj_path} already exist! Cannot initialize cargo project")
            return None

        cmd = ["cargo", "init", cargo_proj_path]
        self.logger.info(f"Executing {' '.join(cmd)}")
        code, stdout, stderr = exec_cmd(cmd, True)
        if code != 0:
            self.logger.error(f"Could not initialize cargo project at {cargo_proj_path}")
            self.logger.error(stderr)
            return None
        return cargo_proj_path
    
    def set_dir(self, dir):
        """Change working directory. Args: dir (str). Returns: None."""
        os.chdir(dir)
