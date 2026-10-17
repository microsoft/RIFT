import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.append("../")

from librift.rift_cfg import RiftConfig
from librift.storage_handler import StorageHandler
from librift.rift_gen import RiftGenerator, RiftFlirtGenException
from librift.sig_backend import SignatureBackend, SignatureBackendError, SUPPORTED_FORMATS, DEFAULT_FORMAT
from librift.flirt import FlirtGenerator
from librift.fid import FunctionIdDb_Engine, RESULT_MARKER, SKIP_MARKER
from librift.rustmeta import RustMetadata
from librift.crate import RustCrate


class TestSignatureBackendBase(unittest.TestCase):
    """The ABC contract both backends must satisfy."""

    def test_both_backends_are_signature_backends(self):
        for cls, name, ext in [(FlirtGenerator, "flirt", ".sig"), (FunctionIdDb_Engine, "fid", ".fidb")]:
            with self.subTest(backend=cls.__name__):
                self.assertTrue(issubclass(cls, SignatureBackend))
                self.assertEqual(cls.name, name)
                self.assertEqual(cls.extension, ext)
                self.assertIn(cls.name, SUPPORTED_FORMATS)

    def test_backend_cannot_be_instantiated_without_generate(self):
        class Incomplete(SignatureBackend):
            name = "fid"
            extension = ".fidb"

        with self.assertRaises(TypeError):
            Incomplete(MagicMock())


class TestBackendRegistry(unittest.TestCase):
    """Registry construction under each availability combination."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.work_folder = os.path.join(self.tmp_dir, "work")
        self.cargo_proj_folder = os.path.join(self.tmp_dir, "cargo")
        os.makedirs(self.work_folder)
        os.makedirs(self.cargo_proj_folder)
        self.tool = os.path.join(self.tmp_dir, "tool")
        open(self.tool, "w").close()
        self.logger = MagicMock()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _build_generator(self, **overrides):
        cfg = RiftConfig(
            self.logger, "does_not_exist.cfg",
            work_folder=self.work_folder,
            cargo_proj_folder=self.cargo_proj_folder,
            **overrides
        )
        storage = StorageHandler(self.work_folder, self.cargo_proj_folder, self.tmp_dir, self.logger)
        return RiftGenerator(cfg, self.logger, MagicMock(), MagicMock(), storage, MagicMock())

    def test_ida_only_registers_flirt_backend(self):
        gen = self._build_generator(pcf=self.tool, sigmake=self.tool)
        self.assertEqual(sorted(gen.backends), ["flirt"])

    def test_ghidra_only_registers_fid_backend(self):
        gen = self._build_generator(analyze_headless=self.tool)
        self.assertEqual(sorted(gen.backends), ["fid"])

    def test_both_toolchains_register_both_backends(self):
        gen = self._build_generator(pcf=self.tool, sigmake=self.tool, analyze_headless=self.tool)
        self.assertEqual(sorted(gen.backends), ["fid", "flirt"])

    def test_neither_toolchain_still_constructs(self):
        """R1: a host with no IDA and no Ghidra must not fail to construct."""
        gen = self._build_generator()
        self.assertEqual(gen.backends, {})


class TestFormatDispatch(unittest.TestCase):
    """Format resolution, artifact naming and failure isolation."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.work_folder = os.path.join(self.tmp_dir, "work")
        self.cargo_proj_folder = os.path.join(self.tmp_dir, "cargo")
        os.makedirs(self.work_folder)
        os.makedirs(self.cargo_proj_folder)
        tool = os.path.join(self.tmp_dir, "tool")
        open(tool, "w").close()
        self.logger = MagicMock()

        cfg = RiftConfig(
            self.logger, "does_not_exist.cfg",
            work_folder=self.work_folder,
            cargo_proj_folder=self.cargo_proj_folder,
            pcf=tool, sigmake=tool, analyze_headless=tool
        )
        storage = StorageHandler(self.work_folder, self.cargo_proj_folder, self.tmp_dir, self.logger)
        self.gen = RiftGenerator(cfg, self.logger, MagicMock(), MagicMock(), storage, MagicMock())
        self.meta = RustMetadata(
            arch="x86_64", compiler="gnu", filetype="ELF",
            rust_version="1.75.0", version_short="1.75.0"
        )
        self.crate = RustCrate("serde", "1.0.185")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _handle(self, **kwargs):
        return self.gen._RiftGenerator__handle_gen_signatures(["/coff/a.o"], "/out", self.meta, **kwargs)

    def _stub_backends(self):
        for backend in self.gen.backends.values():
            backend.generate = lambda coff, out, meta, crate=None: out

    def test_resolve_formats(self):
        resolve = self.gen._RiftGenerator__resolve_formats
        self.assertEqual(resolve("fid"), ("fid",))
        self.assertEqual(resolve(["fid", "flirt", "fid"]), ("flirt", "fid"))
        self.assertEqual(resolve([DEFAULT_FORMAT]), ("flirt",))

    def test_resolve_formats_rejects_unknown(self):
        with self.assertRaises(RiftFlirtGenException):
            self.gen._RiftGenerator__resolve_formats("bindiff")

    def test_resolve_formats_rejects_the_removed_both_alias(self):
        """Format selection is two boolean flags; 'both' is not a value anywhere."""
        with self.assertRaises(RiftFlirtGenException):
            self.gen._RiftGenerator__resolve_formats("both")

    def test_artifact_names_use_backend_extension(self):
        self._stub_backends()
        self.assertEqual(
            self._handle(crate=self.crate, formats=("flirt", "fid")),
            ["/out/serde-1.0.185-1.75.0-x86_64-unknown-linux-gnu.sig",
             "/out/serde-1.0.185-1.75.0-x86_64-unknown-linux-gnu.fidb"]
        )

    def test_toolchain_artifact_name(self):
        self._stub_backends()
        self.assertEqual(
            self._handle(formats=("fid",)),
            ["/out/rustc-1.75.0-x86_64-unknown-linux-gnu.fidb"]
        )

    def test_one_failing_backend_does_not_take_the_other_down(self):
        self._stub_backends()
        self.gen.backends["flirt"].generate = MagicMock(side_effect=RuntimeError("pcf exploded"))
        self.assertEqual(
            self._handle(crate=self.crate, formats=("flirt", "fid")),
            ["/out/serde-1.0.185-1.75.0-x86_64-unknown-linux-gnu.fidb"]
        )

    def test_all_backends_failing_raises(self):
        for backend in self.gen.backends.values():
            backend.generate = MagicMock(side_effect=RuntimeError("boom"))
        with self.assertRaises(RiftFlirtGenException):
            self._handle(crate=self.crate, formats=("flirt", "fid"))

    def test_unavailable_backend_raises_a_clear_error(self):
        del self.gen.backends["fid"]
        with self.assertRaises(RiftFlirtGenException):
            self._handle(crate=self.crate, formats=("fid",))


class TestFunctionIdDbEngine(unittest.TestCase):
    """The FID backend's own logic, with no Ghidra present."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.out_path = os.path.join(self.tmp_dir, "serde.fidb")
        self.coff_dir = os.path.join(self.tmp_dir, "coff")
        os.makedirs(self.coff_dir)
        self.objs = []
        for name in ("a.o", "b.o"):
            path = os.path.join(self.coff_dir, name)
            open(path, "w").close()
            self.objs.append(path)
        self.engine = FunctionIdDb_Engine(MagicMock(), "/opt/ghidra/support/analyzeHeadless", self.tmp_dir)
        self.meta = RustMetadata(
            arch="x86_64", compiler="gnu", filetype="ELF",
            rust_version="1.75.0", version_short="1.75.0"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_language_spec_mapping(self):
        cases = [
            ("x86_64", "gnu", ("x86:LE:64:default", "gcc")),
            ("x86_64", "msvc", ("x86:LE:64:default", "windows")),
            ("i686", "gnu", ("x86:LE:32:default", "gcc")),
            ("aarch64", "msvc", ("AARCH64:LE:64:v8A", "windows")),
            ("arm", "msvc", ("ARM:LE:32:v8", "default")),
        ]
        for arch, compiler, expected in cases:
            with self.subTest(arch=arch, compiler=compiler):
                self.meta.arch, self.meta.compiler = arch, compiler
                self.assertEqual(self.engine.get_language_spec(self.meta), expected)

    def test_unmapped_arch_raises_instead_of_guessing(self):
        self.meta.arch = "mips"
        with self.assertRaises(SignatureBackendError):
            self.engine.get_language_spec(self.meta)

    def test_unmapped_compiler_raises_instead_of_guessing(self):
        self.meta.compiler = "uefi"
        with self.assertRaises(SignatureBackendError):
            self.engine.get_language_spec(self.meta)

    def test_library_identity(self):
        self.assertEqual(
            self.engine.get_library_identity(self.meta),
            ("rustc", "1.75.0", "x86_64-unknown-linux-gnu")
        )
        self.assertEqual(
            self.engine.get_library_identity(self.meta, RustCrate("serde", "1.0.185")),
            ("serde", "1.0.185", "1.75.0-x86_64-unknown-linux-gnu")
        )

    def test_versionless_crate_never_yields_an_empty_identity_field(self):
        """An empty argument would shift the post-script's argument positions."""
        identity = self.engine.get_library_identity(self.meta, RustCrate("std", ""))
        self.assertTrue(all(identity), identity)

    def test_coff_dir_must_be_unambiguous(self):
        self.assertEqual(self.engine.get_coff_dir(self.objs), self.coff_dir)
        with self.assertRaises(SignatureBackendError):
            self.engine.get_coff_dir(["/a/x.o", "/b/y.o"])

    def test_empty_object_list_raises(self):
        with self.assertRaises(SignatureBackendError):
            self.engine.generate([], self.out_path, self.meta)

    def test_generate_runs_two_phases_and_cleans_the_project(self):
        calls = []

        def fake_exec(cmd, capture_output=False, check=True):
            calls.append(cmd)
            if "-process" in cmd:
                open(self.out_path, "w").close()
                return (0, f"{RESULT_MARKER} added=512 excluded=3 attempted=515", "")
            return (0, None, None)

        with patch("librift.fid.exec_cmd", fake_exec):
            result = self.engine.generate(self.objs, self.out_path, self.meta, RustCrate("serde", "1.0.185"))

        self.assertEqual(result, self.out_path)
        self.assertEqual(len(calls), 2, "expected exactly one import and one populate invocation")
        self.assertIn("-import", calls[0])
        self.assertIn("-process", calls[1])
        self.assertIn("-noanalysis", calls[1])
        self.assertIn("-recursive", calls[1], "imported programs live in a sub folder, not the root")
        self.assertNotIn("-deleteProject", calls[1])
        self.assertEqual(calls[0][1], os.path.abspath(self.tmp_dir), "project location is the work dir")
        self.assertTrue(os.path.isdir(self.engine.proj_dir), "project location must be kept")
        for path in self.engine.get_project_paths():
            self.assertFalse(os.path.exists(path), f"throwaway project file {path} must be removed")

    def test_cleanup_removes_only_project_files(self):
        gpr, rep = self.engine.get_project_paths()[:2]
        open(gpr, "w").close()
        os.makedirs(os.path.join(rep, "idata"))
        self.engine.cleanup_project()
        self.assertFalse(os.path.exists(gpr))
        self.assertFalse(os.path.exists(rep))
        self.assertTrue(os.path.isdir(self.coff_dir), "unrelated content in the location must survive")

    def test_missing_project_location_logs_and_raises(self):
        engine = FunctionIdDb_Engine(MagicMock(), "/opt/ghidra/support/analyzeHeadless",
                                     os.path.join(self.tmp_dir, "missing"))
        with patch("librift.fid.exec_cmd") as fake_exec:
            with self.assertRaises(SignatureBackendError):
                engine.generate(self.objs, self.out_path, self.meta)
        fake_exec.assert_not_called()
        engine.logger.error.assert_called_once()

    def test_failed_import_raises_and_skips_populate(self):
        calls = []

        def fake_exec(cmd, capture_output=False, check=True):
            calls.append(cmd)
            return (1, "", "boom")

        with patch("librift.fid.exec_cmd", fake_exec):
            with self.assertRaises(SignatureBackendError):
                self.engine.generate(self.objs, self.out_path, self.meta)
        self.assertEqual(len(calls), 1)

    def test_failed_populate_logs_headless_output(self):
        def fake_exec(cmd, capture_output=False, check=True):
            if "-process" in cmd:
                return (1, "No program files found", "stack trace")
            return (0, None, None)

        with patch("librift.fid.exec_cmd", fake_exec):
            with self.assertRaises(SignatureBackendError):
                self.engine.generate(self.objs, self.out_path, self.meta)
        logged = [c.args[0] for c in self.engine.logger.error.call_args_list]
        self.assertIn("No program files found", logged)
        self.assertIn("stack trace", logged)

    def test_populate_output_checks(self):
        self.engine.check_populate_output(f"{RESULT_MARKER} added=5 excluded=0 attempted=5")
        self.engine.check_populate_output(f"{SKIP_MARKER} serde:1.0.185:x")

        # Real headless stdout, as formatted by Ghidra's console log appender
        self.engine.check_populate_output(
            "INFO  RiftPopulateFid.java> Ingesting 1 programs into serde:1.0.185:x (GhidraScript)  \n"
            f"INFO  RiftPopulateFid.java> {RESULT_MARKER} added=100 excluded=4 attempted=104 (GhidraScript)  \n"
            "INFO  REPORT: Save succeeded for processed file: /crates/a.o (HeadlessAnalyzer)  ")
        self.engine.check_populate_output(
            f"INFO  RiftPopulateFid.java> {SKIP_MARKER} serde:1.0.185:x (GhidraScript)  ")

        for payload in (f"{RESULT_MARKER} added=0 excluded=9 attempted=9",
                        f"INFO  RiftPopulateFid.java> {RESULT_MARKER} added=0 excluded=9 attempted=9 (GhidraScript)",
                        "Analysis complete"):
            with self.subTest(payload=payload):
                with self.assertRaises(SignatureBackendError):
                    self.engine.check_populate_output(payload)


if __name__ == "__main__":
    unittest.main()
