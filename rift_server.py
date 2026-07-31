# copied from https://github.com/ynsrc/python-simple-rest-api/blob/main/server.py

import json
import argparse
import hmac
import signal
import threading
import os
import shutil
import ssl
from collections import namedtuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from librift.utils import get_logger
from rift_engine import RiftEngine
from librift.rift_cfg import RiftConfig
from libsrv.flirtjob import JobRegistry, JobStatus
from libsrv.flirtworker import FlirtWorker
from libsrv.server_storage import ServerStorage

logger = get_logger()

FileResponse = namedtuple("FileResponse", ["path", "download_name"])


class ApiRequestHandler(BaseHTTPRequestHandler):

    def __init__(self, request, client_address, ref_req, api_ref):
        self.api = api_ref
        super().__init__(request, client_address, ref_req)

    def send_json_response(self, status_code, data, message=None):
        self.send_response(status_code, message)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=4).encode())

    def call_api(self, method, path, args):
        if path in self.api.routing[method]:
            try:
                result = self.api.routing[method][path](args)
                if isinstance(result, FileResponse):
                    self.send_file(result)
                else:
                    self.send_json_response(200, result)
            except Exception as e:
                self.send_json_response(500, {"error": e.args}, "Server Error")
        else:
            self.send_json_response(404, {"error": "not found"}, "Not Found")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path not in self.api.auth_exempt_paths and not self._is_authorized():
            self.send_json_response(401, {"error": "unauthorized"})
            return

        if method == "GET":
            args = parse_qs(parsed_url.query)
            for k in args.keys():
                if len(args[k]) == 1:
                    args[k] = args[k][0]
            self.call_api("GET", path, args)
        else:
            if self.headers.get("content-type") != "application/json":
                self.send_json_response(400, {"error": "posted data must be in json format"})
                return
            data_len = int(self.headers.get("content-length"))
            data = self.rfile.read(data_len).decode()
            self.call_api("POST", path, json.loads(data))

    def _is_authorized(self):
        """Perform authentication check if server mode is set to remote."""
        if not self.api.require_auth:
            return True
        provided = self.headers.get("X-RIFT-API-KEY")
        if provided is None:
            return False
        return hmac.compare_digest(provided, self.api.api_key or "")

    def send_file(self, file_response):
        """Send FLIRT signature file"""
        file_size = os.path.getsize(file_response.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{file_response.download_name}"')
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        with open(file_response.path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)



class RIFT_API():
    def __init__(self):
        """Initialization routine."""
        self.routing = { "GET": { }, "POST": { }}
        self.rift_api = None
        self.logger = None
        self.output_folder = None
        self.storage = None
        self.job_registry = JobRegistry(max_jobs=100)
        self.worker = None
        self.api_key = None
        self.require_auth = False
        self.auth_exempt_paths = {"/health"}
        self.server_mode = None



    def get(self, path):
        def wrapper(fn):
            self.routing["GET"][path] = fn
        return wrapper

    def post(self, path):
        def wrapper(fn):
            self.routing["POST"][path] = fn
        return wrapper

    def __call__(self, request, client_address, ref_request):
        api_handler = ApiRequestHandler(request, client_address, ref_request, api_ref=self)
        return api_handler

    def start_worker(self):
        """Initialize and start the background worker."""
        self.worker = FlirtWorker(
            job_registry=self.job_registry,
            rift_api=self.rift_api,
            output_folder=self.output_folder,
            logger=self.logger,
            storage=self.storage,
            is_remote = self.rift_api.cfg.server_mode == "remote"
        )
        self.worker.start()

    def stop_worker(self):
        """Stop the background worker gracefully."""
        if self.worker:
            self.worker.stop()

api = RIFT_API()

@api.post("/flirt")
def submit_flirt_job(json_data):
    """Submit FLIRT generation job. Returns job_id immediately."""
    logger.info("FLIRT job submission received")
    logger.debug(json_data)

    required_fields = ["commithash", "arch", "filetype", "crates", "target_triple"]
    missing = [f for f in required_fields if f not in json_data]
    if missing:
        return {"error": f"Missing required fields: {missing}", "status": "error"}
    if api.output_folder:
        json_data["output_folder"] = api.output_folder
    job = api.job_registry.create_job(json_data)
    api.worker.submit(job.job_id)

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "message": "Job submitted successfully. Use GET /job?id=<job_id> to check status."
    }

@api.get("/download")
def download_flirt(json_data):
    """Download a specific FLIRT signature"""
    logger.info("Download request received")
    required_fields = ["filename", "mode"]
    missing = [f for f in required_fields if f not in json_data]
    if missing:
        return {"error": f"Missing required fields: {missing}", "status": "error"}
    mode = json_data["mode"]
    filename = json_data["filename"]
    path = api.storage.get_flirt_path(filename) if api.storage else None
    if not path:
        return {"error": f"File not found: {filename}", "status": "error"}
    if mode == "local":
        return {"filename": filename, "path": path, "status": "ok"}
    elif mode == "remote":
        return FileResponse(path=path, download_name=filename)
    else:
        return {"error": f"Invalid mode: {mode}", "status": "error"}

@api.get("/job")
def get_job_status(args):
    """Get status of a specific job."""
    job_id = args.get("id")
    if not job_id:
        return {"error": "Missing required parameter: id"}

    job = api.job_registry.get_job(job_id)
    if not job:
        return {"error": f"Job not found: {job_id}"}

    return job.to_dict()


@api.get("/jobs")
def list_jobs(args):
    """List all jobs, optionally filtered by status."""
    status_filter = args.get("status")
    if status_filter:
        try:
            status = JobStatus(status_filter)
            return {"jobs": api.job_registry.list_jobs(status=status)}
        except ValueError:
            return {"error": f"Invalid status: {status_filter}"}
    return {"jobs": api.job_registry.list_jobs()}


@api.get("/health")
def health_check(args):
    """Health check endpoint."""
    pending = len(api.job_registry.list_jobs(status=JobStatus.PENDING))
    running = len(api.job_registry.list_jobs(status=JobStatus.RUNNING))
    return {
        "status": "healthy",
        "server_mode": api.server_mode,
        "pending_jobs": pending,
        "running_jobs": running,
        "worker_alive": api.worker.is_alive() if api.worker else False
    }

def main(args):
    """Main, loop entry."""
    global logger
    logger = get_logger(args.log, verbose=args.verbose)
    rift_cfg = RiftConfig(logger, args.cfg)
    if not rift_cfg.flirt_available:
        logger.error("PCF.exe or sigmake.exe not found. Both files are necessary for rift_server to run")
        return

    if rift_cfg.server_mode == "remote":
        missing = []
        if not rift_cfg.api_key or rift_cfg.api_key == "NOT_SET":
            missing.append("ApiKey")
        if not rift_cfg.tls_cert or rift_cfg.tls_cert == "NOT_SET" or not os.path.isfile(rift_cfg.tls_cert):
            missing.append("TlsCert")
        if not rift_cfg.tls_key or rift_cfg.tls_key == "NOT_SET" or not os.path.isfile(rift_cfg.tls_key):
            missing.append("TlsKey")
        if missing:
            logger.error(f"server_mode=remote requires a valid {', '.join(missing)} in the config. Refusing to start.")
            return
        # if remote, we want to set the api storage here. This is the folder we store the flirt signature on the server device

    # However, if we are in local mode, we do not need this server storage! We store the files, whatever the user configures through the mask

    rift_api = RiftEngine(logger, args.cfg, rift_cfg.server_storage)
    api.rift_api = rift_api
    api.logger = logger
    api.storage = ServerStorage(logger, rift_cfg.server_storage)
    api.api_key = rift_cfg.api_key
    api.server_mode = rift_api.cfg.server_mode
    api.require_auth = api.server_mode == "remote"

    # Start background worker
    api.start_worker()

    httpd = HTTPServer((rift_api.cfg.api_ip, int(rift_api.cfg.api_port, 10)), api)
    if api.server_mode == "remote":
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=rift_cfg.tls_cert, keyfile=rift_cfg.tls_key)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        except Exception:
            logger.exception("Failed initializing TLS socket for remote mode")
            api.stop_worker()
            httpd.server_close()
            return


    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received, stopping server...")
        api.stop_worker()
        threading.Thread(target=httpd.shutdown).start()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info(f"Starting RIFT_Server at {rift_api.cfg.api_ip}:{int(rift_api.cfg.api_port, 10)}")
    httpd.serve_forever()
    logger.info("Server stopped.") 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", help="Log file output")
    parser.add_argument("--verbose", default=False, action="store_true", help="Enable verbose logging")
    parser.add_argument("--cfg", help="Path to rift_config.cfg", default="./rift_config.cfg")
    args = parser.parse_args()
    main(args)
