"""Serve the local app and its JSON API on the loopback interface."""

import argparse
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, unquote, urlsplit

import api


ROOT = Path(__file__).resolve().parents[1]

CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".txt": "text/plain",
    ".ico": "image/x-icon",
}


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if status == 405:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.respond(status, body, "application/json")

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler dispatches unsupported methods here as 501.
        if code == 501:
            code, message = 405, "Method not allowed"
        self.json_response(code, {"error": message or self.responses[code][0]})

    def do_GET(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path.startswith("/api/"):
            status, payload = api.handle(path, parse_qs(url.query), self.server.root)
            self.json_response(status, payload)
            return

        web_root = (self.server.root / "app/web").resolve()
        try:
            file_path = (web_root / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if not file_path.is_relative_to(web_root) or not file_path.is_file():
                self.json_response(404, {"error": "File not found"})
                return
            body = file_path.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self.json_response(404, {"error": "File not found"})
            return
        content_type = CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
        self.respond(200, body, content_type)

    def do_HEAD(self):
        self.do_GET()


class AppServer(ThreadingHTTPServer):
    # On Windows, address reuse lets a second server bind a port that's already taken.
    allow_reuse_address = sys.platform != "win32"


def make_server(port, root):
    server = AppServer(("127.0.0.1", port), AppHandler)
    server.root = Path(root).resolve()
    return server


def main():
    parser = argparse.ArgumentParser(description="Run the Northfield local web app.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        server = make_server(args.port, ROOT)
    except OSError as error:
        # Windows reports a taken port as WSAEADDRINUSE rather than EADDRINUSE.
        if error.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", None)):
            print(f"Port {args.port} is in use; choose another with --port.")
        else:
            print(f"Could not start the server: {error}")
        return 1

    print(
        f"Northfield app running at http://127.0.0.1:{server.server_port}  (Ctrl+C to stop)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
