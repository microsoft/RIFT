import tempfile
import unittest
import sys
from pathlib import Path

sys.path.append("../")
from librift.rift_cfg import RiftConfig
from librift.utils import get_logger


class TestRiftConfig(unittest.TestCase):
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
