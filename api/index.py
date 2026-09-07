"""Minimal Vercel Function entrypoint for deployment health checks.

The desktop Organizer remains a Windows application. This function only gives
Vercel a valid HTTP entrypoint and reports whether the deployment is reachable.
"""

from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):
    """Return a small health response for the deployed service."""

    def do_GET(self) -> None:
        payload = json.dumps({"service": "download-organizer", "status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
