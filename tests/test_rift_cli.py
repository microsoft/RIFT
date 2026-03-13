import unittest
import sys
sys.path.append("../")
sys.path.append("../../")
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO
import rift_cli
from librift.rift_meta import RiftInvalidCompiler


class TestHandleGenMode(unittest.TestCase):
    """Test cases for the handle_gen_mode function in rift_cli.py"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        # Create test output directory
        cls.test_output_dir = Path("test_gen")
        cls.test_output_dir.mkdir(exist_ok=True)

        # Default config path (assumes rift_config.cfg exists)
        cls.cfg_path = "./rift_config.cfg"

        # Set up logger for rift_cli
        rift_cli.logger = rift_cli.get_logger(None, False)

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment after all tests"""
        # Clean up test output directory
        if cls.test_output_dir.exists():
            shutil.rmtree(cls.test_output_dir)

    def setUp(self):
        """Set up before each test"""
        # Ensure test output directory is clean
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)
        self.test_output_dir.mkdir(exist_ok=True)

    def test_handle_gen_mode_case1_crate_and_compiler_success(self):
        """
        Test case 1: py rift_cli.py reqwest@0.123 1.88-x86_64-pc-windows-msvc -o test_gen/
        Should succeed and write FLIRT signatures into test_gen/ folder
        """
        crate = "reqwest@0.123"
        compiler = "1.88-x86_64-pc-windows-msvc"
        output_path = str(self.test_output_dir.resolve())

        # Mock the RiftEngine and related functions to avoid actual compilation
        with patch('rift_cli.RiftEngine') as MockRiftEngine, \
             patch('rift_cli.build_rustmeta_from_string') as mock_build_meta, \
             patch('rift_cli.parse_crate_string') as mock_parse_crate:

            # Set up mocks
            mock_api_instance = MagicMock()
            MockRiftEngine.return_value = mock_api_instance

            mock_meta = MagicMock()
            mock_build_meta.return_value = mock_meta

            mock_crate_obj = MagicMock()
            mock_crate_obj.get_id.return_value = "reqwest@0.123"
            mock_parse_crate.return_value = mock_crate_obj

            # Execute the function
            result = rift_cli.handle_gen_mode(
                self.cfg_path,
                output_path,
                compiler=compiler,
                crate=crate
            )

            # Assertions
            self.assertEqual(result, 1, "Function should return 1 for success")
            MockRiftEngine.assert_called_once_with(rift_cli.logger, self.cfg_path, output_folder=output_path)
            mock_build_meta.assert_called_once_with(compiler)
            mock_parse_crate.assert_called_once_with(crate)
            mock_api_instance.generate_crate_flirt.assert_called_once_with(
                mock_meta, mock_crate_obj, output_path
            )

    def test_handle_gen_mode_case2_crate_only_fails(self):
        """
        Test case 2: py rift_cli.py reqwest@0.123
        Should fail, missing compiler
        """
        crate = "reqwest@0.123"
        compiler = ""
        output_path = str(self.test_output_dir.resolve())

        # Capture log output
        with patch('rift_cli.logger') as mock_logger:
            result = rift_cli.handle_gen_mode(
                self.cfg_path,
                output_path,
                compiler=compiler,
                crate=crate
            )

            # Assertions
            self.assertEqual(result, 0, "Function should return 0 for failure")
            mock_logger.error.assert_called_with(
                "Providing only the crate and not the compiler is not supported yet!"
            )

    def test_handle_gen_mode_case3_compiler_only_success(self):
        """
        Test case 3: py rift_cli.py 1.88-i686-pc-windows-gnu
        Should succeed and generate a FLIRT signature in test_gen folder
        """
        compiler = "1.88-i686-pc-windows-gnu"
        crate = ""
        output_path = str(self.test_output_dir.resolve())

        # Mock the RiftEngine and related functions
        with patch('rift_cli.RiftEngine') as MockRiftEngine, \
             patch('rift_cli.build_rustmeta_from_string') as mock_build_meta:

            # Set up mocks
            mock_api_instance = MagicMock()
            MockRiftEngine.return_value = mock_api_instance

            mock_meta = MagicMock()
            mock_build_meta.return_value = mock_meta

            # Execute the function
            result = rift_cli.handle_gen_mode(
                self.cfg_path,
                output_path,
                compiler=compiler,
                crate=crate
            )

            # Assertions
            self.assertEqual(result, 1, "Function should return 1 for success")
            MockRiftEngine.assert_called_once_with(rift_cli.logger, self.cfg_path, output_folder=output_path)
            mock_build_meta.assert_called_once_with(compiler)
            mock_api_instance.generate_compiler_flirt.assert_called_once_with(mock_meta, output_path)

    def test_handle_gen_mode_case4_invalid_toolchain_fails(self):
        """
        Test case 4: py rift_cli.py reqwest@0.123 THIS_IS_CRAP
        Should fail because THIS_IS_CRAP is not a valid toolchain
        """
        crate = "reqwest@0.123"
        compiler = "THIS_IS_CRAP"
        output_path = str(self.test_output_dir.resolve())

        # Mock the RiftEngine and related functions
        with patch('rift_cli.RiftEngine') as MockRiftEngine: #\
            # Set up mocks - simulate that invalid toolchain causes an exception
            mock_api_instance = MagicMock()
            MockRiftEngine.return_value = mock_api_instance

            mock_crate_obj = MagicMock()
            mock_crate_obj.get_id.return_value = "reqwest@0.123"

            with self.assertRaises(RiftInvalidCompiler) as context:
                rift_cli.handle_gen_mode(
                    self.cfg_path,
                    output_path,
                    compiler=compiler,
                    crate=crate
                )
            # Verify the error message
            self.assertIn("Invalid compiler pattern", str(context.exception))


if __name__ == "__main__":
    unittest.main()
