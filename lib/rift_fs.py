import os
from lib import utils
import shutil

# Constants, used to build folder structure in work
FLIRT_FOLDER = "flirt"
TMP_FOLDER = "tmp"
TMP_TOOLCHAIN_FOLDER = "tmp_toolchain"
TMP_CRATES_FOLDER = "tmp_crates"
PAT_FOLDER = "pat"
SQL_FOLDER = "sql"
SQL_TOOLCHAIN_FOLDER = "sql_toolchain"
SQL_CRATES_FOLDER = "sql_crates"
SQL_CUSTOM_FOLDER = "sql_custom"
SQL_DIFF_FOLDER = "sql_diff"
SQL_DIFF_TOOLCHAIN_FOLDER = "sql_diff_toolchain"
SQL_DIFF_CRATES_FOLDER = "sql_diff_crates"
SQL_DIFF_CUSTOM_FOLDER = "sql_diff_custom"
IDB_FOLDER = "idb"
IDB_TOOLCHAIN_FOLDER = "idb_toolchain"
IDB_CRATES_FOLDER = "idb_crates"
IDB_CUSTOM_FOLDER = "idb_custom"
COFF_FOLDER = "coff"
INFO_FOLDER = "info"
RLIB_FOLDER = "rlib"


class RIFTFileSystem:

    def __init__(self, work_folder, cargo_proj_folder, output_folder, logger, cargo_proj_name=utils.gen_random_name(8)):
        """Init."""
        self.work_folder = work_folder
        self.cargo_proj_folder = cargo_proj_folder
        self.cargo_proj_path = os.path.join(self.cargo_proj_folder, cargo_proj_name)
        self.logger = logger
        self.output_folder = output_folder
        self.flirt_path = None
        self.tmp_path = None
        self.tmp_toolchain_path = None
        self.tmp_crates_path = None
        self.pat_path = None
        self.sql_path = None
        self.sql_toolchain_path = None
        self.sql_crates_path = None
        self.sql_custom_path = None
        self.sql_diff_path = None
        self.sql_diff_toolchain_path = None
        self.sql_diff_crates_path = None
        self.sql_diff_custom_path = None
        self.idb_path = None
        self.idb_toolchain_path = None
        self.idb_crates_path = None
        self.idb_custom_path = None
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

        # init sql folder and corresponding sub folders for crates and toolchain
        self.sql_path = os.path.abspath(os.path.join(path, SQL_FOLDER))
        os.makedirs(self.sql_path, exist_ok=True)

        self.sql_crates_path = os.path.abspath(os.path.join(self.sql_path, SQL_CRATES_FOLDER))
        os.makedirs(self.sql_crates_path, exist_ok=True)

        self.sql_toolchain_path = os.path.abspath(os.path.join(self.sql_path, SQL_TOOLCHAIN_FOLDER))
        os.makedirs(self.sql_toolchain_path, exist_ok=True)

        self.sql_custom_path = os.path.abspath(os.path.join(self.sql_path, SQL_CUSTOM_FOLDER))
        os.makedirs(self.sql_custom_path, exist_ok=True)

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

        # init sql_diff path and corresponding crates, toolchain and custom sub folders
        self.sql_diff_path = os.path.abspath(os.path.join(path, SQL_DIFF_FOLDER))
        os.makedirs(self.sql_diff_path, exist_ok=True)

        self.sql_diff_crates_path = os.path.abspath(os.path.join(self.sql_diff_path, SQL_DIFF_CRATES_FOLDER))
        os.makedirs(self.sql_diff_crates_path, exist_ok=True)

        self.sql_diff_toolchain_path = os.path.abspath(os.path.join(self.sql_diff_path, SQL_DIFF_TOOLCHAIN_FOLDER))
        os.makedirs(self.sql_diff_toolchain_path, exist_ok=True)

        self.sql_diff_custom_path = os.path.abspath(os.path.join(self.sql_diff_path, SQL_DIFF_CUSTOM_FOLDER))
        os.makedirs(self.sql_diff_custom_path, exist_ok=True)

    def init_cargo_project(self):
        if os.path.isdir(self.cargo_proj_path):
            self.logger.error(f"{self.cargo_proj_path} already exist! Cannot initialize cargo project")
            return False

        cmd = ["cargo", "init", self.cargo_proj_path]
        self.logger.info(f"Executing {' '.join(cmd)}")
        code,stdout,stderr = utils.exec_cmd(cmd)
        if code != 0:
            self.logger.error(f"Could not initialize cargo project at {self.cargo_proj_path}")
            self.logger.error(stderr)
            return False
        return True

    def search_rustup_location(self):
        """Searches for default location of .rustup folder."""

        retval = None
        user_profile = os.path.expanduser("~")
        rustup_path = os.path.join(user_profile, ".rustup")
        if os.path.exists(rustup_path):
            retval =  os.path.abspath(rustup_path)
        return retval
    
    def get_tc_rlib_folder(self, rustup_path, target_compiler, target):
        """Builds path to toolchain folder, where rlib files are located in."""
        path = os.path.join(rustup_path, "toolchains")
        path = os.path.join(path, target_compiler)
        path = os.path.join(path, "lib", "rustlib", target, "lib")
        if not os.path.isdir(path):
            path = None
        return path
    
    def get_crates_rlib_folder(self, proj_path, target, compile_type):
        path = os.path.join(proj_path, "target")
        path = os.path.join(path, target)
        path = os.path.join(path, compile_type)
        path = os.path.join(path, "deps")
        if not os.path.isdir(path):
            path = None
        return path

    def unpack_rlibs_to(self, rlib_files, coff_folder, tmp_folder):
        """Unpacks all .rlib files and extracts the coff files to the coff_folder."""
        for rlib_file in rlib_files:
            utils.unpack_rlib(rlib_file, tmp_folder)

        coff_files = utils.get_files_from_dir(tmp_folder, ".o")
        for coff_file in coff_files:
            shutil.move(coff_file, os.path.join(coff_folder, os.path.basename(coff_file)))
        return True
    
    def cleanup_work_folder(self):
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
        return any(files for _, _, files in os.walk(self.work_folder))