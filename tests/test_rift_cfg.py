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


if __name__ == "__main__":
    unittest.main()
