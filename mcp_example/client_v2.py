#!/usr/bin/env python3
"""
A tiny, pure‑stdlib HTTP client that talks to an MCP server.
It knows how to fetch `/capabilities` and then uses the discovered
endpoint(s) when posting a conversation entry.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ------------------------------------------------------------------
@dataclass
class Capability:
    """Internal representation of a single tool advertised by the server."""
    method: str                     # e.g. "POST"
    uri: str                        # e.g. "/conversation"
    description: str                # human readable
    request_body_schema: dict       # JSON‑Schema fragment (not validated here)
    response_body_schema: dict      # same


# ------------------------------------------------------------------
class MCPClient:
    """
    Connects to an MCP server and discovers what it can do.
    """

    def __init__(self, host: str = "localhost", port: int = 8000):
        self.base_url = f"http://{host}:{port}"
        self.capabilities: Dict[str, Capability] = {}

    # ------------------------------------------------------------------
    def _make_request(
        self,
        path: str,
        method: str = "GET",
        body: Optional[dict] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> dict:
        """
        Low‑level helper that performs a HTTP request and returns the parsed JSON.
        Raises urllib.error.HTTPError if the server replies with an error status.
        """
        url = urllib.parse.urljoin(self.base_url, path)
        data = json.dumps(body).encode("utf-8") if body else None
        req_headers = headers or {}
        if body:
            req_headers.setdefault("Content-Type", "application/json; charset=utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers=req_headers)

        try:
            with urllib.request.urlopen(req) as resp:
                content_type = resp.headers.get_content_type()
                raw = resp.read().decode("utf-8")
                if "application/json" in content_type:
                    return json.loads(raw)
                else:
                    raise ValueError(f"Unexpected Content-Type: {content_type}")
        except urllib.error.HTTPError as exc:
            # Re‑raise with the body decoded for easier debugging
            try:
                err_body = exc.read().decode("utf-8")
                err_json = json.loads(err_body) if err_body else {}
            except Exception:
                err_json = {"detail": err_body}
            raise RuntimeError(f"HTTP {exc.code} error: {err_json}") from None

    # ------------------------------------------------------------------
    def discover_capabilities(self) -> None:
        """
        Queries `/capabilities` and stores the result in `self.capabilities`.
        """
        raw = self._make_request("/capabilities")
        caps = {}
        for name, details in raw.items():
            cap = Capability(
                method=details["method"],
                uri=details["uri"],
                description=details.get("description", ""),
                request_body_schema=details.get("request_body_schema", {}),
                response_body_schema=details.get("response_body_schema", {}),
            )
            caps[name] = cap
        self.capabilities = caps

    # ------------------------------------------------------------------
    def list_capabilities(self) -> None:
        """
        Pretty‑print the discovered capabilities.
        """
        if not self.capabilities:
            print("[info] No capabilities found – did you run discover_capabilities()?")
            return
        for name, cap in self.capabilities.items():
            print(f"\n• {name}")
            print(f"  Method:      {cap.method.upper()}")
            print(f"  URI:         {cap.uri}")
            print(f"  Description: {cap.description}")
            print(f"  Request schema:")
            print(json.dumps(cap.request_body_schema, indent=4))
            # (Optional) you could also show the response schema.

    # ------------------------------------------------------------------
    def post_conversation(self, role: str, content: str) -> dict:
        """
        Uses the *save_conversation* capability if it exists.
        Falls back to the hard‑coded `/conversation` endpoint otherwise.
        Returns the JSON payload that the server sent back.
        """
        cap = self.capabilities.get("save_conversation")
        path = "/conversation"
        method = "POST"

        if cap:
            # Use whatever URL /method the server advertised
            path = cap.uri
            method = cap.method.upper()

        body = {"role": role, "content": content}
        return self._make_request(path, method=method, body=body)


# ------------------------------------------------------------------
def main(argv: list[str]) -> None:
    """
    Minimal CLI to demo capability discovery.
    Usage:
      python cli.py                # interactive mode
      python cli.py --list         # just list capabilities
    """
    client = MCPClient()
    try:
        client.discover_capabilities()
    except RuntimeError as exc:
        print(f"[error] Could not talk to server: {exc}")
        sys.exit(1)

    if "--list" in argv or "-l" in argv:
        client.list_capabilities()
        return

    # ------------------------------------------------------------------
    # Interactive mode – very simple prompt
    print("Welcome to the MCP CLI!")
    print("Type 'capabilities' to see what tools are available.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_in = input("> ").strip()
        except EOFError:
            break

        if not user_in:
            continue
        if user_in.lower() in ("quit", "exit"):
            break
        if user_in.lower() == "capabilities":
            client.list_capabilities()
            continue

        # Assume the line is a role|content pair (very naïve)
        try:
            role, content = user_in.split("|", 1)
            resp = client.post_conversation(role.strip(), content.strip())
            print(f"[server] {resp.get('status', 'no status')}")
        except ValueError:
            print("[error] Expected format: <role>|<content> (e.g. user|Hello!)")
        except RuntimeError as exc:
            print(f"[error] {exc}")

    print("\nGoodbye!")


# ------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
