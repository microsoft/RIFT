import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from librift.rift_meta import RiftMeta, build_rustmeta_from_strings, build_rustmeta_from_binary, build_rustmeta_from_json
from librift.rift_cfg import RiftConfig
from librift.utils import get_logger

logger = get_logger()


def get_strings(path):
    """Helper function to read strings from a file."""
    lines = []
    with open(path, "r") as f:
        lines = f.readlines()
    return [l.strip("\n") for l in lines]


class TestRiftMeta(unittest.TestCase):
    """Test cases for RiftMeta metadata extraction."""

    def test_spica_from_strings(self):
        """Test metadata extraction from SPICA sample."""
        expected_rust_crates = ['crossbeam-channel-0.5.8', 'spin-0.5.2', 'smallvec-1.11.0', 'once_cell-1.18.0', 'http-0.2.9', 'tokio-tungstenite-0.19.0', 'want-0.3.1', 'rustls-pemfile-1.0.3', 'futures-core-0.3.28', 'tokio-rustls-0.24.1', 'tinyvec-1.6.0',
                               'rustc-demangle-0.1.23', 'tar-0.4.40', 'bytes-1.4.0', 'form_urlencoded-1.2.0', 'cipher-0.3.0', 'mio-0.8.8', 'rand-0.8.5', 'rand_core-0.6.4', 'indexmap-1.9.3', 'reqwest-0.11.18', 'futures-channel-0.3.28', 'futures-util-0.3.28', 'crossbeam-deque-0.8.3', 'hashbrown-0.13.1', 'generic-array-0.14.7', 'percent-encoding-2.3.0', 'tokio-util-0.7.8', 'rayon-1.7.0', 'serde-1.0.185', 'hashbrown-0.12.3', 'rayon-core-1.11.0', 'base64-0.21.2', 'sct-0.7.0', 'socket2-0.4.9', 'rusqlite-0.25.4', 'utf-8-0.7.6', 'rustc-demangle-0.1.21', 'serde_json-1.0.105', 'tungstenite-0.19.0', 'untrusted-0.7.1', 'slab-0.4.8', 'rustls-0.21.6', 'ctr-0.8.0', 'windows-0.48.0', 'tokio-1.32.0', 'jwalk-0.8.1', 'parking_lot-0.12.1', 'parking_lot_core-0.9.8', 'ipnet-2.8.0', 'wmi-0.13.1', 'hyper-rustls-0.24.1', 'h2-0.3.20', 'ahash-0.7.6', 'httparse-1.8.0', 'sysinfo-0.28.4', 'rustls-webpki-0.101.3', 'color-spantrace-0.2.0', 'aes-0.7.5', 'backtrace-0.3.68', 'color-eyre-0.6.2', 'ring-0.16.20', 'hyper-0.14.27', 'unicode-normalization-0.1.22', 'idna-0.4.0', 'open-4.2.0', 'url-2.4.0', 'data-encoding-2.4.0', 'crossbeam-epoch-0.9.15']
        expected_commithash = "eb26296b556cef10fb713a38f3d16b9886080f26"
        expected_rust_ver = "1.71.1"

        strings = get_strings("extracted_strings/strings_spica_37c52481711631a5c73a6341bd8bea302ad57f02199db7624b580058547fb5a9.txt")
        # rift_meta = get_rift_meta(strings)
        rift_cfg = RiftConfig(logger, "../rift_config.cfg")
        rust_meta = build_rustmeta_from_strings(logger, rift_cfg, strings)

        self.assertEqual(rust_meta.commithash, expected_commithash)
        self.assertEqual(rust_meta.get_rust_version(), expected_rust_ver)
        self.assertCountEqual(rust_meta.get_crates_list(), expected_rust_crates)
        print("Test SPICA success")

    def test_hello_world_binary(self):
        """Test metadata extraction from hello world binary file."""
        binary_path = "test_files/hello_world_i686_pc_windows_mscv"
        expected_commithash = "16d2276fa6fccb0cc239a542d4c3f0eb46f660ec"
        expected_arch = "i686"
        expected_rust_version = "nightly-2025-05-17"
        expected_compiler = "msvc"
        rift_cfg = RiftConfig(logger, "../rift_config.cfg")
        rust_meta = build_rustmeta_from_binary(logger, rift_cfg, binary_path)

        # Assert that metadata was extracted
        self.assertIsNotNone(rust_meta)
        self.assertEqual(rust_meta.commithash, expected_commithash)
        self.assertEqual(rust_meta.arch, expected_arch)
        self.assertEqual(rust_meta.get_rust_version(), expected_rust_version)
        self.assertEqual(rust_meta.compiler, expected_compiler)

    def test_build_from_json_1(self):
        """Test metadata creation by parsing legacy JSON file"""
        json_path = "test_files/static_hello_world_i686_pc_windows_mscv.json"
        expected_commithash = "16d2276fa6fccb0cc239a542d4c3f0eb46f660ec"
        expected_arch = "i686"
        expected_crates = ["rustc-demangle-0.1.24"]
        expected_filetype = "PE"

        rift_cfg = RiftConfig(logger, "../rift_config.cfg")
        rust_meta = build_rustmeta_from_json(logger, rift_cfg, json_path)

        # Assert that metadata was extracted
        self.assertIsNotNone(rust_meta)
        self.assertEqual(rust_meta.commithash, expected_commithash)
        self.assertEqual(rust_meta.arch, expected_arch)
        self.assertEqual(rust_meta.filetype, expected_filetype)
        self.assertCountEqual(rust_meta.get_crates_list(), expected_crates)

    def test_build_from_json_2(self):
        """Test metadata creation from SPICA JSON file"""
        json_path = "test_files/static_spica_1.json"
        expected_commithash = "eb26296b556cef10fb713a38f3d16b9886080f26"
        expected_arch = "x86_64"
        expected_filetype = "PE"
        expected_compiler = "msvc"
        expected_rust_version = "1.71.1"
        expected_crates = [
            "smallvec-1.11.0", "rayon-1.7.0", "tokio-util-0.7.8", "futures-core-0.3.28",
            "hashbrown-0.12.3", "ring-0.16.20", "aes-0.7.5", "ctr-0.8.0", "url-2.4.0",
            "futures-channel-0.3.28", "tokio-1.32.0", "hyper-rustls-0.24.1", "indexmap-1.9.3",
            "bytes-1.4.0", "percent-encoding-2.3.0", "idna-0.4.0", "windows-0.48.0",
            "crossbeam-epoch-0.9.15", "http-0.2.9", "color-spantrace-0.2.0", "mio-0.8.8",
            "rustls-pemfile-1.0.3", "color-eyre-0.6.2", "hashbrown-0.13.1", "hyper-0.14.27",
            "data-encoding-2.4.0", "unicode-normalization-0.1.22", "httparse-1.8.0",
            "backtrace-0.3.68", "rand-0.8.5", "rustls-0.21.6", "futures-util-0.3.28",
            "once_cell-1.18.0", "wmi-0.13.1", "tokio-tungstenite-0.19.0", "parking_lot-0.12.1",
            "reqwest-0.11.18", "crossbeam-channel-0.5.8", "utf-8-0.7.6",
            "spin-0.5.2", "serde-1.0.185", "serde_json-1.0.105", "want-0.3.1", "jwalk-0.8.1",
            "generic-array-0.14.7", "rayon-core-1.11.0", "ipnet-2.8.0", "crossbeam-deque-0.8.3",
            "socket2-0.4.9", "tokio-rustls-0.24.1", "tungstenite-0.19.0", "cipher-0.3.0",
            "open-4.2.0", "form_urlencoded-1.2.0", "slab-0.4.8", "sct-0.7.0",
            "rand_core-0.6.4", "tinyvec-1.6.0", "tar-0.4.40", "base64-0.21.2",
            "rustls-webpki-0.101.3", "rusqlite-0.25.4", "rustc-demangle-0.1.23",
            "rustc-demangle-0.1.21", "parking_lot_core-0.9.8", "sysinfo-0.28.4",
            "untrusted-0.7.1", "ahash-0.7.6", "h2-0.3.20"
        ]

        rift_cfg = RiftConfig(logger, "../rift_config.cfg")
        rust_meta = build_rustmeta_from_json(logger, rift_cfg, json_path)

        # Assert that metadata was extracted
        self.assertIsNotNone(rust_meta)
        self.assertEqual(rust_meta.commithash, expected_commithash)
        self.assertEqual(rust_meta.arch, expected_arch)
        self.assertEqual(rust_meta.filetype, expected_filetype)
        self.assertEqual(rust_meta.compiler, expected_compiler)
        self.assertEqual(rust_meta.get_rust_version(), expected_rust_version)
        self.assertCountEqual(rust_meta.get_crates_list(), expected_crates)
        print("Test SPICA JSON success")


class TestRiftMetaStringExtraction(unittest.TestCase):
    def setUp(self):
        self.commithash = "07dca489ac2d933c78d3c5158e3f43beefeb02ce"
        cfg = SimpleNamespace(rustc_hashes=[{
            "git_commit_hash": self.commithash,
            "hash_short": self.commithash[:9],
            "version": "1.0.0",
            "version_short": "1.0.0",
            "ts": None,
        }])
        self.rift_meta = RiftMeta(MagicMock(), cfg)

    def extract_meta(self, strings):
        rustc_path = rf"/rustc/{self.commithash}\library\core\src\lib.rs"
        return self.rift_meta.extract_meta([rustc_path] + strings)

    def test_get_crates(self):
        test_cases = [
            ([
                "/home/kali/.cargo/registry/src/index.crates.io-6f17d22bba15001f/clap-3.2.25/src/mkeymap.rs",
                "/rust/deps/miniz_oxide-0.7.4/src/inflate/core.rs",
                ".cargo\\registry\\src\\index.crates.io-6f17d22bba15001f\\tokio-1.32.0\\src\\sync\\mpsc\\chan.rs",
            ], ["clap-3.2.25", "miniz_oxide-0.7.4", "tokio-1.32.0"]),
            ([
                "/home/kali/.cargo/registry/src/index.crates.io-6f17d22bba15001f/clap/src/mkeymap.rs",
                "/home/kali/.cargo/registry/src//inflate/src/mkeymap.rs",
                "/deps/miniz_oxide-0.7.4/src/inflate/core.rs",
            ], ["miniz_oxide-0.7.4"]),
            (["src/.cargo/registry/src/gitlab.local-6e6d3f8bd0b6968f/tokio-1.34.0/src/runtime/context/runtime.rs"],
             ["tokio-1.34.0"]),
            (["C:\\Users\\user\\.cargo\\registry\\src\\index.crates.io-6f17d22bba15001f\\rand-0.9.0-alpha.2\\src\\rngs\\thread.rs"],
             ["rand-0.9.0-alpha.2"]),
        ]

        for strings, expected in test_cases:
            with self.subTest(expected=expected):
                self.assertCountEqual(self.extract_meta(strings).get_crates_list(), expected)

    def test_get_commithash(self):
        strings = [rf"/rustc/{self.commithash}\library\core\src", "_CxxThrowException"]
        self.assertEqual(self.rift_meta.extract_meta(strings).commithash, self.commithash)

        malformed = [r"/rustc/7dca489ac2d933c78d3c5158e3f43beefeb02ce\library\core\src"]
        self.assertIsNone(self.rift_meta.extract_meta(malformed))

    def test_determine_env(self):
        test_cases = [
            (["Mingw-w64 runtime failure:"], "gnu"),
            (["_CxxThrowException"], "msvc"),
            (["std/src/sys/alloc/uefi.rs"], "uefi"),
        ]

        for strings, expected in test_cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.extract_meta(strings).compiler, expected)


if __name__ == '__main__':
    unittest.main()