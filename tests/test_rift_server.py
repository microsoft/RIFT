import os
import sys
import sys
import tempfile
import unittest
from pathlib import Path
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rift_server
from libsrv.flirtworker import FlirtWorker


class TestRiftServerStartup(unittest.TestCase):
    def run_server(self, mode, output):
        config = SimpleNamespace(
            flirt_available=True,
            server_mode=mode,
            server_storage="server-storage",
            api_key="test-key",
            tls_cert="cert.pem",
            tls_key="key.pem",
            api_ip="127.0.0.1",
            api_port="5001",
        )
        args = SimpleNamespace(cfg="test.cfg", output=output, log=None, verbose=False)
        engine = MagicMock()
        engine.cfg = config
        storage = MagicMock()
        storage.path = os.path.abspath(config.server_storage)
        fake_api = MagicMock()

        with patch("rift_server.RiftConfig", return_value=config), \
             patch("rift_server.RiftEngine", return_value=engine) as mock_engine, \
             patch("rift_server.ServerStorage", return_value=storage) as mock_storage, \
             patch("rift_server.HTTPServer", return_value=MagicMock()), \
             patch("rift_server.ssl.SSLContext"), \
             patch("rift_server.signal.signal"), \
             patch("rift_server.os.path.isfile", return_value=True), \
             patch("rift_server.os.makedirs"), \
             patch("rift_server.api", fake_api):
            rift_server.main(args)

        return fake_api, mock_engine, mock_storage, storage

    def test_remote_output_and_storage_are_created_before_engine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = os.path.join(temp_dir, "output")
            storage_folder = os.path.join(temp_dir, "storage")
            tls_cert = os.path.join(temp_dir, "cert.pem")
            tls_key = os.path.join(temp_dir, "key.pem")
            open(tls_cert, "w").close()
            open(tls_key, "w").close()

            config = SimpleNamespace(
                flirt_available=True,
                server_mode="remote",
                server_storage=storage_folder,
                api_key="test-key",
                tls_cert=tls_cert,
                tls_key=tls_key,
                api_ip="127.0.0.1",
                api_port="5001",
            )
            args = SimpleNamespace(
                cfg="test.cfg",
                output=output_folder,
                log=None,
                verbose=False,
            )
            engine = MagicMock()
            engine.cfg = config
            engine.output_folder = os.path.abspath(output_folder)

            def create_engine(logger, cfg_path, engine_output):
                self.assertTrue(os.path.isdir(storage_folder))
                self.assertTrue(os.path.isdir(output_folder))
                return engine

            fake_api = MagicMock()
            httpd = MagicMock()
            with patch("rift_server.RiftConfig", return_value=config), \
                 patch("rift_server.RiftEngine", side_effect=create_engine) as mock_engine, \
                 patch("rift_server.HTTPServer", return_value=httpd), \
                 patch("rift_server.ssl.SSLContext"), \
                 patch("rift_server.signal.signal"), \
                 patch("rift_server.api", fake_api):
                rift_server.main(args)

            mock_engine.assert_called_once()
            self.assertEqual(mock_engine.call_args.args[1], "test.cfg")
            self.assertEqual(mock_engine.call_args.args[2], os.path.abspath(output_folder))
            self.assertEqual(fake_api.storage.path, os.path.abspath(storage_folder))
            self.assertEqual(fake_api.output_folder, os.path.abspath(output_folder))
            fake_api.start_worker.assert_called_once()
            httpd.serve_forever.assert_called_once()

    def test_local_without_output_allows_client_output_with_default_fallback(self):
        fake_api, mock_engine, mock_storage, _ = self.run_server("local", None)

        self.assertIsNone(fake_api.output_folder)
        self.assertEqual(mock_engine.call_args.args[2], os.path.abspath("./Output"))
        mock_storage.assert_not_called()

    def test_remote_without_output_uses_server_storage(self):
        fake_api, mock_engine, mock_storage, storage = self.run_server("remote", None)

        self.assertEqual(fake_api.output_folder, storage.path)
        self.assertEqual(mock_engine.call_args.args[2], storage.path)
        mock_storage.assert_called_once()


class TestOutputPrecedence(unittest.TestCase):
    def test_server_output_overrides_client_output(self):
        job = SimpleNamespace(job_id="test-job", status=SimpleNamespace(value="pending"))
        fake_api = MagicMock()
        fake_api.output_folder = "server-output"
        fake_api.job_registry.create_job.return_value = job
        request = {
            "commithash": "hash",
            "arch": "x86_64",
            "filetype": "PE",
            "crates": [],
            "target_triple": "x86_64-pc-windows-msvc",
            "output_folder": "client-output",
        }

        submit_flirt_job = rift_server.api.routing["POST"]["/flirt"]
        with patch("rift_server.api", fake_api):
            submit_flirt_job(request)

        self.assertEqual(request["output_folder"], "server-output")

    def test_client_output_does_not_change_worker_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            default_output = os.path.join(temp_dir, "default")
            client_output = os.path.join(temp_dir, "client")
            rift_api = MagicMock()
            worker = FlirtWorker(MagicMock(), rift_api, default_output, MagicMock())
            request = {
                "commithash": "hash",
                "arch": "x86_64",
                "filetype": "PE",
                "crates": [],
                "target_triple": "x86_64-pc-windows-msvc",
                "output_folder": client_output,
            }

            with patch("libsrv.flirtworker.RiftMeta") as mock_rift_meta, \
                 patch("libsrv.flirtworker.RustMetadata") as mock_rust_metadata:
                mock_rift_meta.return_value.get_rust_version_for_hash.return_value = ("1.0", None, "1.0")
                mock_rust_metadata.return_value.get_crates.return_value = []
                worker._execute_flirt_generation(SimpleNamespace(job_id="first", request_data=request))
                request_without_output = dict(request)
                request_without_output.pop("output_folder")
                worker._execute_flirt_generation(
                    SimpleNamespace(job_id="second", request_data=request_without_output)
                )

            output_calls = rift_api.generate_compiler_flirt.call_args_list
            self.assertEqual(output_calls[0].args[1], client_output)
            self.assertEqual(output_calls[1].args[1], default_output)


if __name__ == "__main__":
    unittest.main()
