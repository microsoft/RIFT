# copied from https://github.com/ynsrc/python-simple-rest-api/blob/main/server.py

import json
import argparse
import signal
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from librift.utils import get_logger
from rift_engine import RiftEngine
from libsrv.flirtjob import JobRegistry, JobStatus
from libsrv.flirtworker import FlirtWorker

logger = get_logger()


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
                self.send_json_response(200, result)
            except Exception as e:
                self.send_json_response(500, {"error": e.args}, "Server Error")
        else:
            self.send_json_response(404, {"error": "not found"}, "Not Found")

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        args = parse_qs(parsed_url.query)

        for k in args.keys():
            if len(args[k]) == 1:
                args[k] = args[k][0]

        self.call_api("GET", path, args)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if self.headers.get("content-type") != "application/json":
            self.send_json_response(400, {"error": "posted data must be in json format"})
        else:
            data_len = int(self.headers.get("content-length"))
            data = self.rfile.read(data_len).decode()
            self.call_api("POST", path, json.loads(data))


class RIFT_API():
    def __init__(self):
        """Initialization routine."""
        self.routing = { "GET": { }, "POST": { }}
        self.rift_api = None
        self.logger = None
        self.output_folder = None
        self.job_registry = JobRegistry(max_jobs=100)
        self.worker = None

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
            logger=self.logger
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
        "pending_jobs": pending,
        "running_jobs": running,
        "worker_alive": api.worker.is_alive() if api.worker else False
    }

def main(args):
    """Main, loop entry."""
    global logger
    logger = get_logger(args.log, verbose=args.verbose)
    rift_api = RiftEngine(logger, args.cfg, args.o)
    api.rift_api = rift_api
    api.logger = logger
    api.output_folder = args.o

    # Start background worker
    api.start_worker()

    httpd = HTTPServer((rift_api.cfg.api_ip, int(rift_api.cfg.api_port, 10)), api)

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
    parser.add_argument("-o", help="Output folder. When set, overrides any output_folder value received from the client.", default="./Output/")
    args = parser.parse_args()
    main(args)