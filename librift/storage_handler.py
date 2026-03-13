import os
from librift.utils import gen_random_name, unpack_rlib, get_files_from_dir,cleanup_folder
import shutil

# Constants, used to build folder structure in work
FLIRT_FOLDER = "flirt"
TMP_FOLDER = "tmp"
TMP_TOOLCHAIN_FOLDER = "tmp_toolchain"
TMP_CRATES_FOLDER = "tmp_crates"
PAT_FOLDER = "pat"
IDB_FOLDER = "idb"
IDB_TOOLCHAIN_FOLDER = "idb_toolchain"
IDB_CRATES_FOLDER = "idb_crates"
IDB_CUSTOM_FOLDER = "idb_custom"
COFF_FOLDER = "coff"
INFO_FOLDER = "info"
RLIB_FOLDER = "rlib"


class StorageHandler:

    def __init__(self, work_folder, cargo_proj_path, output_folder, logger, cargo_proj_name=None):
        """Init."""
        self.work_folder = work_folder
        self.cargo_proj_path = cargo_proj_path
        self.logger = logger
        self.output_folder = output_folder
        self.flirt_path = None
        self.tmp_path = None
        self.tmp_toolchain_path = None
        self.tmp_crates_path = None
        self.pat_path = None
        self.coff_path = None
        self.coff_toolchain_path = None
        self.coff_crates_path = None
        self.info_path = None
        self.rlib_path = None
        self.init_work_folder(self.work_folder)

    def init_work_folder(self, path):
        """Initializes all folders in the work folder."""

        # init flirt files folder
        self.flirt_path = os.path.abspath(os.path.join(path, FLIRT_FOLDER))
        os.makedirs(self.flirt_path, exist_ok=True)
        
        # init tmp folder
        self.tmp_path = os.path.abspath(os.path.join(path, TMP_FOLDER))
        os.makedirs(self.tmp_path, exist_ok=True)

        self.tmp_toolchain_path = os.path.abspath(os.path.join(self.tmp_path, TMP_TOOLCHAIN_FOLDER))
        os.makedirs(self.tmp_toolchain_path, exist_ok=True)
        
        self.tmp_crates_path = os.path.abspath(os.path.join(self.tmp_path, TMP_CRATES_FOLDER))
        os.makedirs(self.tmp_crates_path, exist_ok=True)

        # init pat folder
        self.pat_path = os.path.abspath(os.path.join(path, PAT_FOLDER))
        os.makedirs(self.pat_path, exist_ok=True)

        # init idb folder, as well as sub folders to store .idb files in
        self.idb_path = os.path.abspath(os.path.join(path, IDB_FOLDER))
        os.makedirs(self.idb_path, exist_ok=True)

        self.idb_toolchain_path = os.path.abspath(os.path.join(self.idb_path, IDB_TOOLCHAIN_FOLDER))
        os.makedirs(self.idb_toolchain_path, exist_ok=True)

        self.idb_crates_path = os.path.abspath(os.path.join(self.idb_path, IDB_CRATES_FOLDER))
        os.makedirs(self.idb_crates_path, exist_ok=True)

        self.idb_custom_path = os.path.abspath(os.path.join(self.idb_path, IDB_CUSTOM_FOLDER))
        os.makedirs(self.idb_custom_path, exist_ok=True)

        # init coff folder
        self.coff_path = os.path.abspath(os.path.join(path, COFF_FOLDER))
        os.makedirs(self.coff_path, exist_ok=True)

        # Init coff_compiler_path
        self.coff_toolchain_path = os.path.abspath(os.path.join(self.coff_path, "toolchain"))
        os.makedirs(self.coff_toolchain_path, exist_ok=True)

        # Init coff_crates_path
        self.coff_crates_path = os.path.abspath(os.path.join(self.coff_path, "crates"))
        os.makedirs(self.coff_crates_path, exist_ok=True)

        # init information files
        self.info_path = os.path.abspath(os.path.join(path, INFO_FOLDER))
        os.makedirs(self.info_path, exist_ok=True)

        # init path to store rlib files in
        self.rlib_path = os.path.abspath(os.path.join(path, RLIB_FOLDER))
        os.makedirs(self.rlib_path, exist_ok=True)

    def search_rustup_location(self):
        """Searches for default location of .rustup folder."""

        retval = None
        user_profile = os.path.expanduser("~")
        rustup_path = os.path.join(user_profile, ".rustup")
        if os.path.exists(rustup_path):
            retval =  os.path.abspath(rustup_path)
        return retval
    
    def get_tc_rlib_folder(self, rustup_path, meta):
        """Builds path to toolchain folder, where rlib files are located in."""
        path = os.path.join(rustup_path, "toolchains")
        path = os.path.join(path, meta.get_target_compiler())
        path = os.path.join(path, "lib", "rustlib", meta.get_target_triple(), "lib")
        if not os.path.isdir(path):
            path = None
        return path
    
    def get_crates_rlib_folder(self, proj_path, meta, compile_type="release"):
        """Build path to crates deps folder. Args: proj_path (str), meta (RustMetadata), compile_type (str). Returns: str or None."""
        path = os.path.join(proj_path, "target", meta.get_target_triple(), compile_type, "deps")
        if not os.path.isdir(path):
            path = None
        return path

    def unpack_rlibs_to(self, rlib_files, coff_folder, tmp_folder):
        """Unpacks all .rlib files and extracts the coff files to the coff_folder."""
        for rlib_file in rlib_files:
            unpack_rlib(rlib_file, tmp_folder)

        coff_files = get_files_from_dir(tmp_folder, ".o")
        for coff_file in coff_files:
            shutil.move(coff_file, os.path.join(coff_folder, os.path.basename(coff_file)))
        return True
    
    def cleanup_work_folder(self):
        """Remove all files from work folder. Args: None. Returns: bool: True if successful, False otherwise."""
        for root, dirs, files in os.walk(self.work_folder):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    os.remove(file_path)
                except Exception as e:
                    self.logger.exception(e)
                    return False
        return True
    
    def has_old_files(self, work_folder):
        """Check if work folder contains any files. Args: work_folder (str). Returns: bool: True if files exist."""
        return any(files for _, _, files in os.walk(self.work_folder))
    
    def cleanup_files(self):
        """Cleans up the work environment"""
        self.logger.debug(f"Cleaning up files in folder = {self.coff_crates_path}")
        cleanup_folder(self.coff_crates_path)
        self.logger.debug(f"Cleaning up files in folder = {self.coff_toolchain_path}")
        cleanup_folder(self.coff_toolchain_path)
        self.logger.debug(f"Cleaning up files in folder = {self.tmp_crates_path}")
        cleanup_folder(self.tmp_crates_path)
        self.logger.debug(f"Cleaning up files in folder = {self.tmp_toolchain_path}")
        cleanup_folder(self.tmp_toolchain_path)
        self.logger.debug(f"Cleaning up files in folder = {self.rlib_path}")
        cleanup_folder(self.rlib_path)
        self.logger.debug(f"Cleaning up files in folder = {self.pat_path}")
        cleanup_folder(self.pat_path)