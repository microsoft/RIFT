import sys
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Callable

DEFAULT_SERVER = "http://localhost:5001"
DEFAULT_POLL_INTERVAL = 10

class RiftConnector:
    """Client connector for RIFT server API. Portable to other applications."""

    def __init__(self, server_url: str = DEFAULT_SERVER, poll_interval: int = DEFAULT_POLL_INTERVAL):
        self.server_url = server_url.rstrip("/")
        self.poll_interval = poll_interval

    def _send_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a POST request with JSON data."""
        url = f"{self.server_url}{endpoint}"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.reason, "status_code": e.code}
        except urllib.error.URLError as e:
            return {"error": str(e.reason)}

    def _send_get(self, endpoint: str) -> Dict[str, Any]:
        """Send a GET request."""
        url = f"{self.server_url}{endpoint}"
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": e.reason, "status_code": e.code}
        except urllib.error.URLError as e:
            return {"error": str(e.reason)}

    def submit_job(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a FLIRT generation job. Returns response with job_id."""
        return self._send_post("/flirt", request_data)

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific job."""
        return self._send_get(f"/job?id={job_id}")

    def list_jobs(self, status: Optional[str] = None) -> Dict[str, Any]:
        """List all jobs, optionally filtered by status."""
        endpoint = "/jobs"
        if status:
            endpoint = f"/jobs?status={status}"
        return self._send_get(endpoint)

    def health_check(self) -> Dict[str, Any]:
        """Check server health status."""
        return self._send_get("/health")

    def submit_and_wait(
        self,
        request_data: Dict[str, Any],
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Submit job and poll until completion.

        Args:
            request_data: The FLIRT request data
            on_progress: Optional callback called with status dict on each poll

        Returns:
            Final job status dict
        """
        result = self.submit_job(request_data)
        if "error" in result:
            return result

        job_id = result["job_id"]

        while True:
            status = self.get_job_status(job_id)

            if "error" in status:
                return status

            if on_progress:
                on_progress(status)

            if status["status"] in ("completed", "failed"):
                return status

            time.sleep(self.poll_interval)

    def wait_for_job(
        self,
        job_id: str,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Wait for an existing job to complete.

        Args:
            job_id: The job ID to wait for
            on_progress: Optional callback called with status dict on each poll

        Returns:
            Final job status dict
        """
        while True:
            status = self.get_job_status(job_id)

            if "error" in status:
                return status

            if on_progress:
                on_progress(status)

            if status["status"] in ("completed", "failed"):
                return status

            time.sleep(self.poll_interval)


def _default_progress_callback(status: Dict[str, Any]) -> None:
    """Default progress callback for CLI usage."""
    progress = status.get("progress", "")
    msg = f"Status: {status['status']}"
    if progress:
        msg += f" - {progress}"
    print(msg)
