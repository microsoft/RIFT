import os
import queue
import threading
from datetime import datetime
from typing import Optional, List

from libsrv.flirtjob import JobRegistry, JobStatus, FlirtJob
from librift.rift_meta import RiftMeta
from librift.rustmeta import RustMetadata
from librift.sig_backend import DEFAULT_FORMAT


def get_requested_formats(json_data):
    """
    Maps the optional "flirt" / "fidb" request fields onto signature formats.

    Each field selects one format and they combine. A request asking for neither
    gets FLIRT, so the shipped IDA plugin keeps working unchanged.
    """
    formats = []
    if json_data.get("flirt"):
        formats.append("flirt")
    if json_data.get("fidb"):
        formats.append("fid")
    if not formats:
        formats.append(DEFAULT_FORMAT)
    return tuple(formats)


class FlirtWorker:
    """Background worker that processes FLIRT jobs sequentially."""

    def __init__(self, job_registry: JobRegistry, rift_api, output_folder: str, logger, storage=None, is_remote=False):
        self._registry = job_registry
        self._rift_api = rift_api
        self._output_folder = output_folder
        self._logger = logger
        self._storage = storage
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self.is_remote = is_remote

    def start(self):
        """Start the worker thread."""
        self._worker_thread = threading.Thread(
            target=self._run_worker,
            name="FlirtWorker",
            daemon=True
        )
        self._worker_thread.start()
        self._logger.info("FlirtWorker started")

    def stop(self, timeout: float = 30.0):
        """Signal worker to stop and wait for current job to finish."""
        self._shutdown_event.set()
        self._queue.put(None)  # Sentinel to wake up worker
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)
            self._logger.info("FlirtWorker stopped")

    def submit(self, job_id: str):
        """Add a job to the processing queue."""
        self._queue.put(job_id)
        self._logger.info(f"Job {job_id} submitted to queue")

    def is_alive(self) -> bool:
        """Check if worker thread is running."""
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _run_worker(self):
        """Main worker loop - processes jobs sequentially."""
        while not self._shutdown_event.is_set():
            try:
                job_id = self._queue.get(timeout=1.0)

                if job_id is None:  # Shutdown sentinel
                    break

                self._process_job(job_id)

            except queue.Empty:
                continue
            except Exception as e:
                self._logger.exception(f"Unexpected error in worker loop: {e}")

    def _process_job(self, job_id: str):
        """Process a single FLIRT job."""
        job = self._registry.get_job(job_id)
        if not job:
            self._logger.error(f"Job {job_id} not found in registry")
            return

        self._registry.update_job(
            job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now()
        )

        try:
            result_files = self._execute_flirt_generation(job)

            self._registry.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                completed_at=datetime.now(),
                result_files=result_files,
                progress="Completed"
            )
            self._logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            self._registry.update_job(
                job_id,
                status=JobStatus.FAILED,
                completed_at=datetime.now(),
                error_message=str(e),
                progress="Failed"
            )
            self._logger.error(f"Job {job_id} failed: {e}")

    def _execute_flirt_generation(self, job: FlirtJob) -> List[str]:
        """Execute the actual FLIRT generation. Returns list of output files."""
        json_data = job.request_data
        result_files = []
        self._logger.info(f"JobRequestData = {json_data}")

        if "commithash" not in json_data:
            raise ValueError("Missing required field: commithash")

        # Build RustMetadata
        rift_meta = RiftMeta(self._logger, self._rift_api.cfg)
        rust_version, ts, version_short = rift_meta.get_rust_version_for_hash(
            json_data["commithash"]
        )

        rust_meta = RustMetadata(
            commithash=json_data["commithash"],
            rust_version=rust_version,
            version_short=version_short,
            arch=json_data["arch"],
            filetype=json_data["filetype"],
            crates=json_data["crates"],
            ts=ts
        )
        rust_meta.compiler = rust_meta.get_compiler_from_target_triple(
            json_data["target_triple"]
        )
        output_folder = json_data.get("output_folder") or self._output_folder
        os.makedirs(output_folder, exist_ok=True)

        formats = get_requested_formats(json_data)
        self._logger.info(f"Job {job.job_id} requested formats = {', '.join(formats)}")
        crates = rust_meta.get_crates()

        for fmt in formats:
            # Generate the toolchain signature
            self._registry.update_job(job.job_id, progress=f"Generating compiler {fmt} signature...")
            try:
                compiler_sig = self._generate_compiler(rust_meta, output_folder, fmt)
                if compiler_sig:
                    result_files.append(str(compiler_sig))
                    if self._storage and self.is_remote:
                        self._storage.register(str(compiler_sig), job_id=job.job_id)
            except Exception as e:
                self._logger.warning(f"Failed to generate compiler {fmt} signature: {e}")

            # Generate the crate signatures with progress updates
            for i, crate in enumerate(crates, 1):
                self._registry.update_job(
                    job.job_id,
                    progress=f"Processing crate {i}/{len(crates)} ({fmt}): {crate.get_id()}"
                )
                try:
                    crate_sig = self._generate_crate(
                        rust_meta, crate, output_folder, fmt,
                        debug_build=json_data.get("debug_build", False)
                    )
                    if crate_sig:
                        result_files.append(str(crate_sig))
                        if self._storage and self.is_remote:
                            self._storage.register(str(crate_sig), job_id=job.job_id)
                except Exception as e:
                    self._logger.warning(f"Failed to generate {fmt} signature for {crate.get_id()}: {e}")

        return result_files

    def _generate_compiler(self, rust_meta, output_folder, fmt):
        """Dispatches the toolchain signature to the engine method of the given format."""
        if fmt == "flirt":
            return self._rift_api.generate_compiler_flirt(rust_meta, output_folder)
        return self._rift_api.generate_compiler_fid(rust_meta, output_folder)

    def _generate_crate(self, rust_meta, crate, output_folder, fmt, debug_build=False):
        """Dispatches a crate signature to the engine method of the given format."""
        if fmt == "flirt":
            return self._rift_api.generate_crate_flirt(rust_meta, crate, output_folder, debug_build=debug_build)
        return self._rift_api.generate_crate_fid(rust_meta, crate, output_folder, debug_build=debug_build)
