#!/usr/bin/env python3
"""
Simple MCP server – no external deps, pure stdlib.
Endpoints:
    GET   /capabilities          → advertise tools
    POST  /conversation         → store a chat entry (role + content)
    GET   /conversation (opt.)  → read the stored log

    POST  /add                  → add two integers and return the sum
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ------------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 8000
LOG_FILE = "chat.log"            # file where we append JSON lines


# ------------------------------------------------------------------
class MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # --------------------------------------------------------------
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --------------------------------------------------------------
    def do_GET(self):
        parsed_path = urlparse(self.path).path

        if parsed_path == "/capabilities":
            capabilities = {
                "save_conversation": {
                    "method": "POST",
                    "uri": "/conversation",
                    "description": "Append the incoming JSON to a file.",
                    "request_body_schema": {
                        "type": "object",
                        "required": ["role", "content"],
                        "properties": {
                            "role":   {"type":"string"},
                            "content":{"type":"string"}
                        }
                    },
                    "response_body_schema": {
                        "type":"object",
                        "properties":{
                            "status":{"type":"string"},
                            "entry":  {"$ref":"#/components/schemas/ChatEntry"}
                        }
                    }
                },

                # ------- NEW CAPABILITY ----------------------------------
                "add_numbers": {
                    "method": "POST",
                    "uri": "/add",
                    "description": "Return the sum of two integers.",
                    "request_body_schema": {
                        "type": "object",
                        "required": ["a", "b"],
                        "properties": {
                            "a": {"type":"integer"},
                            "b": {"type":"integer"}
                        }
                    },
                    "response_body_schema": {
                        "type": "object",
                        "properties": {
                            "result": {"type":"integer"}
                        }
                    }
                }
            }
            self._send_json(200, capabilities)

        elif parsed_path == "/conversation":
            # GET /conversation – optional read‑back of the log
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as fh:
                    lines = [json.loads(l) for l in fh if l.strip()]
                self._send_json(200, {"entries": lines})
            except FileNotFoundError:
                self._send_json(404, {"detail":"No conversation log found"})

        else:
            self._send_json(404, {"detail":"Endpoint not found"})

    # --------------------------------------------------------------
    def do_POST(self):
        parsed_path = urlparse(self.path).path

        if parsed_path == "/conversation":
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")

            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                self._send_json(400, {"detail":f"Invalid JSON: {exc}"})
                return

            # Basic validation – make sure the required fields exist
            if not all(k in data for k in ("role", "content")):
                missing = [k for k in ("role","content") if k not in data]
                self._send_json(400, {"detail":f"Missing fields: {missing}"})
                return

            # Append to the log file
            entry = {
                "timestamp": json.dumps({"type":"string"}),  # placeholder – you could add ISO‑8601 timestamp here
                **data
            }
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")

            # Respond back to the client (echo of what we stored)
            self._send_json(200, {"status":"ok","entry": entry})

        elif parsed_path == "/add":
            # ---------- NEW HANDLER ------------------------------------
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")

            try:
                data = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                self._send_json(400, {"detail":f"Invalid JSON: {exc}"})
                return

            # Validate that we received two integers
            if not all(k in data for k in ("a", "b")):
                missing = [k for k in ("a", "b") if k not in data]
                self._send_json(400, {"detail":f"Missing fields: {missing}"})
                return

            try:
                a = int(data["a"])
                b = int(data["b"])
            except (TypeError, ValueError):
                self._send_json(400, {"detail":"Both 'a' and 'b' must be integers"})
                return

            result = a + b
            self._send_json(200, {"result": result})

        else:
            self._send_json(404, {"detail":"Endpoint not found"})

    # --------------------------------------------------------------
    def log_message(self, format: str, *args):
        """Silence the default stdout noise."""
        print(f"[{self.address_string()}] {format % args}")


# ------------------------------------------------------------------
def run_server():
    httpd = HTTPServer((HOST, PORT), MCPHandler)
    print(f"🚀 MCP server listening on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")


if __name__ == "__main__":
    run_server()
