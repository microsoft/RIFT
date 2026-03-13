import os
from librift.rift_cfg import RiftConfig
from librift.rift_meta import RiftMeta
import idautils
import ida_ida
import ida_loader
import ida_funcs
from librift.rift_connector import RiftConnector

class RIFTNotSupported(Exception):
    """
    Exception raised when a requested RIFT feature or operation
    is not supported by the current environment, architecture, or metadata.
    """

    def __init__(self, message="RIFT operation not supported.", *, feature=None):
        self.feature = feature
        super().__init__(self._build_message(message))

    def _build_message(self, base):
        if self.feature:
            return f"{base} (Feature: {self.feature})"
        return base


class RiftIdaCore:

    def __init__(self, logger, ess_path):
        self.logger = logger
        self.ess_path = ess_path
        self.logger.info(f"Loaded RiftCore")
        self.is_initialized = False
        self.rift_cfg = None
        self.rift_conn = None

    def init_env(self):
        """Initialize the environment, load rustc hashes and RiftConfig class."""
        rustc_hashes_path = os.path.join(self.ess_path, "rustc_hashes.json")
        cfg_path = os.path.join(self.ess_path, "rift_config.cfg")
        self.rift_cfg = RiftConfig(self.logger, cfg_path, rustc_hashes=rustc_hashes_path)
        if self.rift_cfg.api_ip != "NOT_SET" and self.rift_cfg.api_port != "NOT_SET":
            # self.rift_conn = RiftConnector(server_url=f"{self.rift_cfg.api_ip}:{self.rift_cfg.api_port}")
            self.logger.warning("RIFT Server IP and Port are not set, server mode will no be available!")
        self.rift_meta = RiftMeta(self.logger, self.rift_cfg)
        self.logger.info(f"Initialized RiftIdaCore!\nCfgPath = {cfg_path}\nHashesPath = {rustc_hashes_path}")
        self.is_initialized = True
        return True

    def get_rustmeta(self):
        """Initialize RustMeta class from list of strings"""
        strings = self.get_ida_strings()
        rustmeta = self.rift_meta.extract_meta(strings)
        return rustmeta
        # return build_rustmeta_from_strings(self.logger, self.rift_cfg, strings)
        # return rustmeta

    def get_ida_strings(self):
        """Returns strings generated from Ida"""
        sc = idautils.Strings()
        sc = [str(s).strip("\n") for s in sc]
        return sc

    def get_arch(self):
        """Get the architecture of the loaded binary"""
        arch = ida_ida.inf_get_procname()
        if arch == "metapc":
            if ida_ida.inf_is_32bit_exactly():
                return "i686"
            else:
                return "x86_64"
        elif arch == "ARM":
            if ida_ida.inf_is_32bit_exactly():
                return "arm"
            else:
                return "aarch64"
        else:
            raise RIFTNotSupported(f"Architecture {arch} not supported!")
        
    def get_ftype(self):
        """Returns the filetype"""
        ftype = ida_loader.get_file_type_name()
        if "Portable executable" in ftype:
            ftype = "PE"
        elif "ELF" in ftype:
            ftype = "ELF"
        else:
            raise RIFTNotSupported(f"FileType {ftype} not supported!")
        return ftype

    def apply_flirt(self, folder):
        """Apply FLIRT signatures in folder."""
        for file in [os.path.join(folder, f) for f in os.listdir(folder)]:
            if file.endswith(".sig"):
                self.logger.info(f"Applying FLIRT signature = {file}")
                ida_funcs.plan_to_apply_idasgn(file)

    def rift_server_available(self):
        """Check if the configured rift server is available."""
        if self.rift_conn is None:
            server_url = f"http://{self.rift_cfg.api_ip}:{self.rift_cfg.api_port}"
            self.logger.info(f"ServerUrl = {server_url}, checking if RIFT server is available ..")
            self.rift_conn = RiftConnector(server_url=server_url)
        result = self.rift_conn.health_check()
        if "status" in list(result.keys()):
            return result["status"] == "healthy"
        return False
    
    def run(self, dest_folder, rustmeta, apply_silent=False, debug_build=False):
        """"Run flirt signature generation"""
        json_data = rustmeta.to_dict()
        json_data["output_folder"] = dest_folder
        result = self.rift_conn.submit_and_wait(json_data)
        self.logger.info(f"RIFT Server result = {result}")
        if result["status"] == "completed":
            self.logger.info(f"RIFT Server finished, apply_silent = {apply_silent}:")
            for file in result["result_files"]:
                if apply_silent:
                    self.__apply_flirt(file)
                else:
                    self.logger.info(f"Generated FLIRT signature {file}")

    def __apply_flirt(self, flirt_sig_path):
        if os.path.isfile(flirt_sig_path) and flirt_sig_path.endswith(".sig"):
            self.logger.info(f"Applying {flirt_sig_path}")
            ida_funcs.plan_to_apply_idasgn(flirt_sig_path)

    def term(self):
        pass