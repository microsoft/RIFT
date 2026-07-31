import os
import shutil
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.append("../")
from librift.rift_cfg import RiftConfig, RiftConfigError
from librift.utils import get_logger


class TestRiftConfig(unittest.TestCase):
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

    def test_relative_paths_resolve_from_config_directory(self):
        with tempfile.TemporaryDirectory(prefix="rift-config-tests-") as temp_dir:
            root = Path(temp_dir)
            (root / "work").mkdir()
            (root / "tmp").mkdir()
            strings_tool = root / "strings.exe"
            strings_tool.write_text("stub")

            config_path = root / "rift_config.cfg"
            config_path.write_text(
                "[Default]\n"
                "PcfPath = bin/pcf.exe\n"
                "SigmakePath = bin/sigmake.exe\n"
                "WorkFolder = work\n"
                "CargoProjFolder = tmp\n"
                "RustcHashes = missing.json\n"
                "StringsTool = strings.exe\n\n"
                "[RiftServer]\n"
                "Ip = 127.0.0.1\n"
                "Port = 5001\n"
            )

            config = RiftConfig(get_logger(), str(config_path))

            self.assertEqual(config.work_folder, str(root / "work"))
            self.assertEqual(config.cargo_proj_folder, str(root / "tmp"))
            self.assertEqual(config.strings, str(strings_tool))


if __name__ == "__main__":
    unittest.main()
