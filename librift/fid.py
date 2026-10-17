"""
Ghidra Function ID database generation module.

RIFT does not write the .fidb container itself, it drives Ghidra's
analyzeHeadless launcher the same way the FLIRT backend drives pcf and sigmake.

A database is built in two headless phases against one project, which is how
Ghidra's own FunctionID workflow does it: import plus analyze every object file,
then populate the database from the analyzed programs. A single phase is not
possible, since a post-script runs once per imported program while population
needs all of them at once.
"""

import os
import shutil
from librift.utils import exec_cmd
from librift.sig_backend import SignatureBackend, SignatureBackendError

# Throwaway Ghidra project created for one database build.
GHIDRA_PROJECT_NAME = "rift_fid"

# Files Ghidra creates for a project inside its project location. The location
# folder itself must already exist, analyzeHeadless does not create it.
GHIDRA_PROJECT_FILES = (".gpr", ".rep", ".lock", ".lock~")

# Bundled post-script driving the FunctionID populate API.
POPULATE_SCRIPT = "RiftPopulateFid.java"

# Marker the populate script prints, so a failure is detected even though
# analyzeHeadless exits 0 when a script throws.
RESULT_MARKER = "RIFT_FID_RESULT"
SKIP_MARKER = "RIFT_FID_SKIP"

# Ghidra's own FID ingest scripts. They turn off the Function ID, Library
# Identification and demangler analyzers, which corrupt names during ingest,
# and repair switch statements afterwards. Both ship with Ghidra and sit on the
# default script path.
IMPORT_PRESCRIPT = "FunctionIDHeadlessPrescript.java"
IMPORT_POSTSCRIPT = "FunctionIDHeadlessPostscript.java"

# A wrong language id yields a database that loads fine and matches nothing, so
# unmapped architectures raise instead of falling back to a guess.
LANGUAGE_IDS = {
    "x86_64": "x86:LE:64:default",
    "i686": "x86:LE:32:default",
    "aarch64": "AARCH64:LE:64:v8A",
    "arm": "ARM:LE:32:v8",
}

COMPILER_SPECS = {
    "x86_64": {"msvc": "windows", "gnu": "gcc"},
    "i686": {"msvc": "windows", "gnu": "gcc"},
    "aarch64": {"msvc": "windows", "gnu": "gcc"},
    "arm": {"msvc": "default", "gnu": "gcc"},
}


class FunctionIdDb_Engine(SignatureBackend):
    """
    Generator for Ghidra Function ID databases.

    Imports a folder of object files into a throwaway Ghidra project with an
    explicit language and compiler spec, and runs a bundled post-script that
    populates the database with the crate or toolchain identity. One
    analyzeHeadless invocation per database, never one per object file.
    """

    name = "fid"
    extension = ".fidb"

    def __init__(self, logger, ghidra_headless_path, work_dir, script_dir=None):
        """
        Initialize the Function ID database generator.

        Args:
            logger: Logger instance for debug and error messages.
            ghidra_headless_path (str): Path to the analyzeHeadless launcher.
            work_dir (str): Managed work folder, used as the Ghidra project location.
            script_dir (str, optional): Folder with the bundled Ghidra scripts.
                Defaults to the repository's scripts/ folder.
        """
        super().__init__(logger)
        self.headless = ghidra_headless_path
        self.work_dir = work_dir
        self.proj_dir = work_dir
        if script_dir is None:
            script_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
        self.script_dir = script_dir

    def generate(self, coff_files, out_path, meta, crate=None):
        """
        Generate a Function ID database from the given object files.

        Args:
            coff_files (list): Paths to the object files, all in one folder.
            out_path (str): Absolute output path of the .fidb file.
            meta (RustMetadata): Supplies language spec and library identity.
            crate (RustCrate, optional): None for the rustc toolchain itself.

        Returns:
            str: Path to the generated database (out_path).

        Raises:
            SignatureBackendError: On unmapped triple or failed headless run.
        """
        if len(coff_files) < 1:
            raise SignatureBackendError("No object files to import into the FID database!")

        coff_dir = self.get_coff_dir(coff_files)
        language_id, cspec = self.get_language_spec(meta)
        family, version, variant = self.get_library_identity(meta, crate)
        if not all((family, version, variant)):
            raise SignatureBackendError(
                f"Incomplete library identity ({family}, {version}, {variant})!")

        self.check_proj_dir()
        self.cleanup_project()
        try:
            self.import_objects(coff_dir, language_id, cspec)
            self.populate_db(out_path, family, version, variant, language_id)
        finally:
            # analyzeHeadless only honours -deleteProject for projects it created
            # in the same session, so the populate phase can never clean up.
            self.cleanup_project()

        if not os.path.isfile(out_path):
            raise SignatureBackendError(f"Headless run produced no database at {out_path}!")
        return out_path

    def import_objects(self, coff_dir, language_id, cspec):
        """Phase one. Imports and analyzes every object file into a fresh Ghidra project."""
        cmd = self.get_headless_cmd() + [
            "-import", os.path.abspath(coff_dir),
            "-processor", language_id,
            "-cspec", cspec,
            "-preScript", IMPORT_PRESCRIPT,
            "-postScript", IMPORT_POSTSCRIPT,
        ]
        self.logger.debug(f"Executing {' '.join(cmd)}")
        # Output is streamed, not captured. A toolchain build imports thousands of
        # object files and the analysis log would otherwise be held in memory.
        resultcode, _, _ = exec_cmd(cmd, capture_output=False, check=False)
        if resultcode != 0:
            raise SignatureBackendError(f"Headless import failed with code {resultcode}!")

    def populate_db(self, out_path, family, version, variant, language_id):
        """Phase two. Builds one FID library from the analyzed programs in the project."""
        # -recursive is required, the import phase stores programs in a sub folder
        # named after the imported directory, never in the project root.
        cmd = self.get_headless_cmd() + [
            "-process",
            "-recursive",
            "-noanalysis",
            "-scriptPath", os.path.abspath(self.script_dir),
            "-postScript", POPULATE_SCRIPT,
            os.path.abspath(out_path), family, version, variant, language_id,
        ]
        self.logger.debug(f"Executing {' '.join(cmd)}")
        resultcode, stdout, stderr = exec_cmd(cmd, capture_output=True, check=False)
        if resultcode != 0:
            self.logger.error(stdout)
            self.logger.error(stderr)
            raise SignatureBackendError(f"Headless populate failed with code {resultcode}!")
        self.check_populate_output(stdout)

    def check_populate_output(self, stdout):
        """
        Raises unless the populate script reported a library with at least one function.

        Script output reaches stdout through Ghidra's console log appender, so a
        marker is never at the start of a line:
        INFO  RiftPopulateFid.java> RIFT_FID_RESULT added=100 ... (GhidraScript)
        """
        for line in (stdout or "").splitlines():
            if SKIP_MARKER in line:
                return
            idx = line.find(RESULT_MARKER)
            if idx >= 0:
                line = line[idx:].strip()
                self.logger.info(line)
                fields = dict(f.split("=", 1) for f in line.split()[1:] if "=" in f)
                if int(fields.get("added", 0)) > 0:
                    return
                raise SignatureBackendError(f"No functions were added to the FID database! {line}")
        raise SignatureBackendError(f"Populate script did not report a result! Missing {RESULT_MARKER}")

    def get_headless_cmd(self):
        """Returns the analyzeHeadless invocation prefix. All paths absolute, no working directory needed."""
        return [self.headless, os.path.abspath(self.proj_dir), GHIDRA_PROJECT_NAME]

    def check_proj_dir(self):
        """Raises unless the Ghidra project location exists. analyzeHeadless fails on a missing location."""
        if not self.proj_dir or not os.path.isdir(self.proj_dir):
            msg = f"Ghidra project location {self.proj_dir} does not exist!"
            self.logger.error(msg)
            raise SignatureBackendError(msg)

    def get_project_paths(self):
        """Returns the paths of all files Ghidra creates for the throwaway project."""
        return [os.path.join(self.proj_dir, GHIDRA_PROJECT_NAME + ext) for ext in GHIDRA_PROJECT_FILES]

    def cleanup_project(self):
        """Removes the throwaway Ghidra project, leaving the project location in place."""
        for path in self.get_project_paths():
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.remove(path)

    def get_coff_dir(self, coff_files):
        """Returns the single folder holding the object files. Ghidra imports a directory, not a file list."""
        folders = {os.path.dirname(os.path.abspath(f)) for f in coff_files}
        if len(folders) != 1:
            raise SignatureBackendError(f"Object files span {len(folders)} folders, expected exactly one!")
        return folders.pop()

    def get_language_spec(self, meta):
        """Maps the target triple onto a Ghidra language id and compiler spec. Returns a tuple, raises if unmapped."""
        language_id = LANGUAGE_IDS.get(meta.arch)
        if language_id is None:
            raise SignatureBackendError(f"No Ghidra language id for arch = {meta.arch}!")
        cspec = COMPILER_SPECS.get(meta.arch, {}).get(meta.compiler)
        if cspec is None:
            raise SignatureBackendError(f"No Ghidra compiler spec for arch = {meta.arch}, compiler = {meta.compiler}!")
        return language_id, cspec

    def get_library_identity(self, meta, crate=None):
        """Returns the FID (family, version, variant) tuple shown to the user on a match."""
        # TODO: Append the cargo build profile once rift_gen passes debug_build
        # down to the backends. The variant is the only field left to tell a
        # debug and a release database apart.
        if crate is None:
            return ("rustc", meta.get_rust_version(), meta.get_target_triple())
        # Crates shipped with the toolchain (std, core, alloc) carry no version
        # of their own. Their rustc version is the meaningful one, and an empty
        # string here would reach analyzeHeadless as an empty argument and shift
        # the post-script's argument positions.
        version = crate.version if crate.version else meta.get_rust_version()
        return (crate.name, version, f"{meta.get_rust_version()}-{meta.get_target_triple()}")
