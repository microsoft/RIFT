import os
import configparser
import shutil
from typing import Optional, Dict, Any
from librift.utils import read_json

class RiftConfigError(Exception):
    """FLIRT generation errors."""
    pass


class RiftConfig:
    def __init__(
        self,
        logger,
        config_path: str,
        *,
        work_folder: Optional[str] = None,
        cargo_proj_folder: Optional[str] = None,
        pcf: Optional[str] = None,
        sigmake: Optional[str] = None,
        strings: Optional[str] = None,
        # NOTE: treat rustc_hashes strictly as a *path* to a JSON file
        rustc_hashes: Optional[str] = None,
        api_ip: Optional[str] = None,
        api_port: Optional[str] = None,
        server_storage: Optional[str] = None,
        server_mode: Optional[str] = None,
        api_key: Optional[str] = None,
        tls_cert: Optional[str] = None,
        tls_key: Optional[str] = None,
        tls_ca_cert: Optional[str] = None,
    ):
        self.logger = logger
        self.config_path = config_path

        self.pcf: Optional[str] = None
        self.sigmake: Optional[str] = None
        self.work_folder: Optional[str] = None
        self.cargo_proj_folder: Optional[str] = None
        self.flirt_available: bool = True
        self.diff_available: bool = True

        # Always a dict after _validate_and_finalize()
        self.rustc_hashes: Dict[str, Any] = {}

        self.strings: Optional[str] = None
        self.api_ip: Optional[str] = None
        self.api_port: Optional[str] = None
        self.server_storage: Optional[str] = None
        self.server_mode: Optional[str] = None
        self.api_key: Optional[str] = None
        self.tls_cert: Optional[str] = None
        self.tls_key: Optional[str] = None
        self.tls_ca_cert: Optional[str] = None

        config = configparser.ConfigParser()
        read_files = config.read(self.config_path)
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        if not read_files:
            self.logger.warning(
                f"Config file '{self.config_path}' not found or unreadable. "
                "Only constructor overrides (if any) will be used."
            )

        def _cfg_get(section: str, option: str, default: str = "NOT_SET") -> str:
            """Get config value or default. Args: section (str), option (str), default (str). Returns: str: Config value."""
            try:
                return config.get(section, option)
            except (configparser.NoSectionError, configparser.NoOptionError):
                return default

        def _resolve(override: Optional[str], cfg_value: str, default: str = "NOT_SET") -> str:
            """Resolve config with override priority. Args: override (str or None), cfg_value (str), default (str). Returns: str: Resolved value."""
            if override is not None:
                return override
            if cfg_value != "NOT_SET":
                return cfg_value
            return default

        def _norm_path(p: Optional[str], *, allow_command: bool = False) -> Optional[str]:
            """Normalize and expand path. Args: p (str or None). Returns: str or None: Absolute expanded path."""
            if not p or p == "NOT_SET":
                return p
            # Expand %VAR%, $VAR, ~ and make absolute
            expanded = os.path.expanduser(os.path.expandvars(p))
            if allow_command and not os.path.dirname(expanded) and not os.path.isabs(expanded):
                config_relative = os.path.join(config_dir, expanded)
                if os.path.isfile(config_relative):
                    return os.path.abspath(config_relative)
                return expanded
            if not os.path.isabs(expanded):
                expanded = os.path.join(config_dir, expanded)
            return os.path.abspath(expanded)

        # ---- read config values
        cfg_work_folder       = _cfg_get("Default", "WorkFolder")
        cfg_cargo_proj_folder = _cfg_get("Default", "CargoProjFolder")
        cfg_pcf               = _cfg_get("Default", "PcfPath")
        cfg_sigmake           = _cfg_get("Default", "SigmakePath")
        cfg_strings           = _cfg_get("Default", "StringsTool")
        cfg_rustc_hashes      = _cfg_get("Default", "RustcHashes")
        cfg_api_ip            = _cfg_get("RiftServer", "Ip")
        cfg_api_port          = _cfg_get("RiftServer", "Port")
        cfg_server_storage    = _cfg_get("RiftServer", "flirt_dir")
        cfg_server_mode       = _cfg_get("RiftServer", "server_mode")
        cfg_api_key           = _cfg_get("RiftServer", "ApiKey")
        cfg_tls_cert          = _cfg_get("RiftServer", "TlsCert")
        cfg_tls_key           = _cfg_get("RiftServer", "TlsKey")
        cfg_tls_ca_cert       = _cfg_get("RiftServer", "TlsCaCert")

        # ---- resolve with overrides
        self.work_folder       = _norm_path(_resolve(work_folder,       cfg_work_folder))
        self.cargo_proj_folder = _norm_path(_resolve(cargo_proj_folder, cfg_cargo_proj_folder))
        self.pcf               = _norm_path(_resolve(pcf,               cfg_pcf))
        self.sigmake           = _norm_path(_resolve(sigmake,           cfg_sigmake))
        self.strings           = _norm_path(_resolve(strings,           cfg_strings), allow_command=True)
        rustc_hashes_path      = _norm_path(_resolve(rustc_hashes,      cfg_rustc_hashes, default="NOT_SET"))
        self.api_ip            = _resolve(api_ip,                        cfg_api_ip)
        self.api_port          = _resolve(api_port,                      cfg_api_port)
        self.server_storage    = _norm_path(_resolve(server_storage,    cfg_server_storage))
        self.server_mode       = _resolve(server_mode,                   cfg_server_mode)
        self.api_key           = _resolve(api_key,                       cfg_api_key)
        self.tls_cert          = _norm_path(_resolve(tls_cert,          cfg_tls_cert))
        self.tls_key           = _norm_path(_resolve(tls_key,           cfg_tls_key))
        self.tls_ca_cert       = _norm_path(_resolve(tls_ca_cert,       cfg_tls_ca_cert))

        # Always convert rustc_hashes_path into a dict via read_json()
        self._load_rustc_hashes(rustc_hashes_path)

        self._validate_and_finalize()

    # ---------------- internal helpers ----------------

    def _load_rustc_hashes(self, path: Optional[str]) -> None:
        """
        Whatever happens, self.rustc_hashes must end up as the dict returned by read_json(path).
        If path is missing or invalid, set to {} and warn.
        """
        if path is None or path == "NOT_SET":
            self.logger.warning("RustcHashes path not set. Using empty rustc_hashes dict.")
            self.rustc_hashes = {}
            return

        if not os.path.isfile(path):
            self.logger.warning(f"RustcHashes path '{path}' does not exist. Using empty rustc_hashes dict.")
            self.rustc_hashes = {}
            return

        try:
            loaded = read_json(path)
            # If the file contains a top-level "rustc_hashes" key, preserve previous behavior.
            if isinstance(loaded, dict):
                self.rustc_hashes = loaded["rustc_hashes"]
            else:
                self.logger.warning(
                    f"RustcHashes JSON at '{path}' did not deserialize to a dict. Using empty rustc_hashes dict."
                )
                self.rustc_hashes = {}
        except Exception as ex:
            self.logger.warning(f"Failed to parse RustcHashes JSON from '{path}': {ex}. Using empty rustc_hashes dict.")
            self.rustc_hashes = {}

    # ---------------- validation & finalization ----------------

    def _validate_and_finalize(self) -> None:
        if not self.work_folder or not os.path.isdir(self.work_folder):
            raise RiftConfigError(f"{self.work_folder} does not exist. Set a valid work folder.")

        if not self.cargo_proj_folder or not os.path.isdir(self.cargo_proj_folder):
            raise RiftConfigError(f"{self.cargo_proj_folder} does not exist. Set a valid tmp folder.")

        if not self.pcf or self.pcf == "NOT_SET" or not os.path.isfile(self.pcf):
            self.logger.warning(
                f"PcfPath = {self.pcf} does not exist. Flirt signature generation will be disabled."
            )
            self.flirt_available = False

        if not self.sigmake or self.sigmake == "NOT_SET" or not os.path.isfile(self.sigmake):
            self.logger.warning(
                f"SigMakePath = {self.sigmake} does not exist. Flirt signature generation will be disabled."
            )
            self.flirt_available = False

        strings_available = self.strings and (
            os.path.isfile(self.strings) or shutil.which(self.strings) is not None
        )
        if not strings_available:
            self.logger.warning(
                f"StringsTool = {self.strings} does not exist. Running RIFT as standalone tool will fail."
            )

        if not self.api_ip or self.api_ip == "NOT_SET":
            self.logger.warning("API IP address is not set in config file or overrides!")

        if not self.server_storage or self.server_storage == "NOT_SET" or not os.path.isdir(self.server_storage):
            self.logger.warning(
                f"flirt_dir = {self.server_storage} does not exist. RIFT server storage features will be unavailable."
            )

        if self.server_mode not in ("local", "remote"):
            self.logger.warning(
                f"mode = {self.server_mode} is not valid (expected 'local' or 'remote'). Defaulting to 'local'."
            )
            self.server_mode = "local"

        if self.server_mode == "remote":
            self.logger.warning(
                "server_mode=remote: RIFT server will accept connections from the network. "
                "ApiKey authentication and a full TLS certificate chain (TlsCert, TlsKey, TlsCaCert) "
                "are required to avoid exposing the server to unauthorized access or plaintext traffic."
            )

            missing_remote_settings = []

            if not self.api_key or self.api_key == "NOT_SET":
                self.logger.warning(
                    "server_mode=remote but ApiKey is not set. Without an API key, any client that "
                    "can reach this server will be able to submit requests. Set 'ApiKey' under the "
                    "[RiftServer] section of the config."
                )
                missing_remote_settings.append("ApiKey is not set")

            if not self.tls_cert or self.tls_cert == "NOT_SET" or not os.path.isfile(self.tls_cert):
                self.logger.warning(
                    f"server_mode=remote but TlsCert = {self.tls_cert} is not set or does not exist. "
                    "Without a valid TLS certificate the server cannot serve HTTPS. Set 'TlsCert' "
                    "under the [RiftServer] section of the config."
                )
                missing_remote_settings.append("TlsCert is missing or invalid")

            if not self.tls_key or self.tls_key == "NOT_SET" or not os.path.isfile(self.tls_key):
                self.logger.warning(
                    f"server_mode=remote but TlsKey = {self.tls_key} is not set or does not exist. "
                    "Without a valid TLS private key the server cannot serve HTTPS. Set 'TlsKey' "
                    "under the [RiftServer] section of the config."
                )
                missing_remote_settings.append("TlsKey is missing or invalid")

            if not self.tls_ca_cert or self.tls_ca_cert == "NOT_SET" or not os.path.isfile(self.tls_ca_cert):
                self.logger.warning(
                    f"server_mode=remote but TlsCaCert = {self.tls_ca_cert} is not set or does not exist. "
                    "Clients will not be able to validate the server's certificate chain. Set "
                    "'TlsCaCert' under the [RiftServer] section of the config."
                )
                missing_remote_settings.append("TlsCaCert is missing or invalid")

            if missing_remote_settings:
                raise RiftConfigError(
                    "server_mode=remote is misconfigured: " + "; ".join(missing_remote_settings) +
                    ". Remote mode requires a valid ApiKey, TlsCert, TlsKey and TlsCaCert to be configured."
                )
