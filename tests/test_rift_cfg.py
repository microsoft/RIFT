import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
import sys
sys.path.append("../")

from librift.rift_cfg import RiftConfig, RiftConfigError


class TestRiftConfig(unittest.TestCase):
    """Test cases for RiftConfig error handling."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.work_folder = os.path.join(self.tmp_dir, "work")
        self.cargo_proj_folder = os.path.join(self.tmp_dir, "cargo")
        os.makedirs(self.work_folder)
        os.makedirs(self.cargo_proj_folder)
        self.logger = MagicMock()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _build(self, **overrides):
        kwargs = dict(work_folder=self.work_folder, cargo_proj_folder=self.cargo_proj_folder)
        kwargs.update(overrides)
        return RiftConfig(self.logger, "does_not_exist.cfg", **kwargs)

    def test_valid_config_does_not_raise(self):
        self._build()

    def test_missing_work_folder_raises_rift_config_error(self):
        with self.assertRaises(RiftConfigError):
            self._build(work_folder=os.path.join(self.tmp_dir, "no_such_folder"))

    def test_missing_cargo_proj_folder_raises_rift_config_error(self):
        with self.assertRaises(RiftConfigError):
            self._build(cargo_proj_folder=os.path.join(self.tmp_dir, "no_such_folder"))

    def test_remote_mode_missing_settings_raises_rift_config_error(self):
        with self.assertRaises(RiftConfigError):
            self._build(server_mode="remote", api_key="", tls_cert="", tls_key="", tls_ca_cert="")

    def _make_tool(self, name):
        path = os.path.join(self.tmp_dir, name)
        open(path, "w").close()
        return path

    def test_analyze_headless_present_enables_fid(self):
        cfg = self._build(analyze_headless=self._make_tool("analyzeHeadless"))
        self.assertTrue(cfg.fid_available)

    def test_analyze_headless_absent_disables_fid(self):
        cfg = self._build()
        self.assertFalse(cfg.fid_available)

    def test_analyze_headless_invalid_path_disables_fid(self):
        cfg = self._build(analyze_headless=os.path.join(self.tmp_dir, "no_such_launcher"))
        self.assertFalse(cfg.fid_available)

    def test_ghidra_only_config_constructs_without_ida(self):
        """R1: a Ghidra user has no pcf/sigmake and must still get a usable config."""
        cfg = self._build(analyze_headless=self._make_tool("analyzeHeadless"), pcf="", sigmake="")
        self.assertFalse(cfg.flirt_available)
        self.assertTrue(cfg.fid_available)

    def test_config_with_neither_toolchain_still_constructs(self):
        """R1: neither IDA nor Ghidra is a valid, non-fatal configuration."""
        cfg = self._build(pcf="", sigmake="", analyze_headless="")
        self.assertFalse(cfg.flirt_available)
        self.assertFalse(cfg.fid_available)


if __name__ == "__main__":
    unittest.main()
