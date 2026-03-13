"""
FLIRT signature generation module.

This module provides functionality to generate FLIRT (Function Library Identification
and Recognition Technology) signature files from COFF object files.
"""

import os
from librift.utils import exec_cmd

class FlirtGenerator:
    """
    Generator for FLIRT signature files.

    This class handles the creation of FLIRT signature files by converting COFF
    object files to pattern (.pat) files and then combining them into a FLIRT
    signature (.sig) file using IDA Pro's sigmake and pcf utilities.
    """

    def __init__(self, logger, sigmake_path, pcf_path, pat_dir):
        """
        Initialize the FLIRT generator.

        Args:
            logger: Logger instance for debug and error messages.
            sigmake_path (str): Path to the sigmake executable (IDA Pro utility).
            pcf_path (str): Path to the pcf executable (Pattern Creation Utility).
            pat_dir (str): Directory where pattern files will be stored.
        """
        self.logger = logger
        self.sigmake = sigmake_path
        self.pcf = pcf_path
        self.pat_dir = pat_dir
    
    def gen_pat(self, coff_files):
        """
        Generate pattern files from COFF object files.

        Converts each COFF object file (.o) to a pattern file (.pat) using
        the pcf (Pattern Creation Utility) tool.

        Args:
            coff_files (list): List of paths to COFF object files.

        Returns:
            list: List of paths to generated pattern files.
        """
        pat_files = []
        for coff_file in coff_files:
            pat_file = self.__pat_abspath(self.pat_dir, coff_file)
            cmd = [self.pcf, coff_file, pat_file]
            exec_cmd(cmd, True, True)
            pat_files.append(pat_file)
        return pat_files
    
    def __pat_abspath(self, pat_dir, file):
        """
        Generate absolute path for a pattern file.

        Args:
            pat_dir (str): Directory for pattern files.
            file (str): Path to COFF object file.

        Returns:
            str: Absolute path to the pattern file with .pat extension.
        """
        return os.path.join(pat_dir, os.path.basename(file).replace(".o", ".pat"))
    
    def gen_flirt(self, pat_dir, flirt_path, ignore_collisions=True):
        """
        Generate a FLIRT signature file from pattern files.

        Combines all pattern files in the specified directory into a single
        FLIRT signature file (.sig) using sigmake.

        Args:
            pat_dir (str): Directory containing pattern files.
            flirt_path (str): Output path for the FLIRT signature file.
            ignore_collisions (bool, optional): If True, automatically resolve
                signature collisions using the -r flag. Defaults to True.

        Returns:
            str: Path to the generated FLIRT signature file.
        """
        curdir = os.getcwd()
        cmd = [self.sigmake]
        if ignore_collisions:
            cmd.append("-r")
        cmd.extend(["*", flirt_path])
        os.chdir(pat_dir)
        self.logger.debug(f"Executing {' '.join(cmd)}")
        exec_cmd(cmd, True, True)
        os.chdir(curdir)
        return flirt_path