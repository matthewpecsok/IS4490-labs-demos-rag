#!/usr/bin/env python3
# ────────────────────────────────────────────────────────────────────── #
#  mcp_server.py – a minimal “Model‑Context Protocol” server
#
#  Features:
#      * /capabilities   → list all registered tools
#      * /conversation   → (optional) fetch chat log
#      * POST /chat      → send user turn, run LLM, call tool if needed
#      * POST /add        → simple arithmetic helper
#
#  Dependencies – nothing but the stdlib + requests (install with pip)
#          pip install requests
# ────────────────────────────────────────────────────────────────────── #

import json, os, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

try:
    import requests  # third‑party – very lightweight
except ImportError:          # pragma: no cover
    print("The 'requests' package is required (pip install requests)", file=sys.stderr)
    sys.exit(1)

# ----------------------------------------------------------------------
# Configuration
HOST = "0.0.0.0"
PORT = 8000

# Where we keep the per‑session chat history files.
CHAT_ROOT = "./sessions"

# Path to a JSON file that contains the *capability map* – you can edit it
# or generate it programmatically, but for this demo we embed it in code.
CAP_MAP_FILE = "capabilities.json"

# Ollama/LLM defaults.  Feel free to change to OpenAI / Azure etc.
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gpt-oss:20b"

# ----------------------------------------------------------------------
def load_capabilities() -> dict:
    """Load the capability map from disk (JSON)."""
    if not os.path.exists(CAP_MAP_FILE):
        # Create a tiny default file that contains add_numbers.
        with open(CAP_MAP_FILE, "w", encoding="utf-8") as fh:
            json.dump({
                "add_numbers": {
                    "method": "POST",
                    "uri": "/add",
                    "description": "Return the sum of two integers.",
                    "request_body_schema": {
                        "type": "object",
                        "required": ["a", "b"],
                        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}
                    },
                    "response_body_schema": {
                        "type": "object",
                        "properties": {"result": {"type": "integer"}}
                    }
                }
            }, fh, indent=2)
    with open(CAP_MAP_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------
class MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # --------------------------------------------------------------
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    # --------------------------------------------------------------
    def _send_text(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --------------------------------------------------------------
    def get_session_file(self, session_id: str) -> str:
        return os.path.join(CHAT_ROOT, f"{session_id}.json")

    # --------------------------------------------------------------
    def load_chat_history(self, session_id: str) -> list:
        path = self.get_session_file(session_id)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return []

    # --------------------------------------------------------------
    def save_chat_history(self, session_id: str, history: list) -> None:
        os.makedirs(CHAT_ROOT, exist_ok=True)
        path = self.get_session_file(session_id)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(history, fh, ensure_ascii=False, indent=2)

    # --------------------------------------------------------------
    def do_GET(self) -> None:
        print(f"ran get")
        parsed_path = urlparse(self.path).path

        if parsed_path == "/capabilities":
            caps_map = load_capabilities()
            self._send_json(200, caps_map)

        elif parsed_path == "/conversation":
            q = urlparse(self.path).query
            session_id = dict([pair.split("=") for pair in q.split("&") if "=" in pair]).get("session")
            if not session_id:
                return self._send_json(400, {"detail": "Missing 'session' query param"})
            history = self.load_chat_history(session_id)
            self._send_json(200, {"entries": history})

        else:
            self._send_json(404, {"detail": "Endpoint not found"})

    # --------------------------------------------------------------
    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        print(f"parsed_path={parsed_path}")

        if parsed_path == "/chat":
            return self.handle_chat()

        elif parsed_path == "/add":
            return self.handle_add()

        else:
            self._send_json(404, {"detail": "Endpoint not found"})

    # --------------------------------------------------------------
    def handle_add(self) -> None:
        """Implementation of the add_numbers capability."""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        print(f"called add")

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            return self._send_json(400, {"detail": f"Invalid JSON: {e}"})

        if not all(k in data for k in ("a", "b")):
            return self._send_json(400, {"detail": "Missing 'a' or 'b'"})
        try:
            a = int(data["a"])
            b = int(data["b"])
        except (TypeError, ValueError):
            return self._send_json(400, {"detail": "'a' and 'b' must be integers"})

        result = a + b
        self._send_json(200, {"result": result})

    # --------------------------------------------------------------
    def handle_chat(self) -> None:
        """
        Main /chat endpoint – receives a user turn,
        stores it, calls the LLM, interprets tool invocation, runs the tool,
        returns the assistant reply.
        """
        print("ran handle chat")
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            return self._send_json(400, {"detail": f"Invalid JSON: {e}"})

        # Validate required fields
        if not all(k in data for k in ("session_id", "role", "content")):
            missing = [k for k in ("session_id","role","content") if k not in data]
            return self._send_json(400, {"detail": f"Missing fields: {missing}"})

        session_id   = data["session_id"]
        user_msg     = {"role":"user", "content":data["content"]}

        # 1️⃣ Load history & append the new user turn
        hist = self.load_chat_history(session_id)
        hist.append(user_msg)

        # 2️⃣ Build system prompt that lists all capabilities
        caps_map   = load_capabilities()
        cap_list   = []
        for name, meta in caps_map.items():
            entry = {"name": name}
            if "description" in meta:
                entry["description"] = meta["description"]
            if "parameters" in meta:     # note: our map uses 'request_body_schema'
                entry["parameters"] = meta.get("request_body_schema", {})
            cap_list.append(entry)

        system_prompt = (
            f"You have access to these capabilities:\n{json.dumps(cap_list, indent=2)}\n\n"
            "When a user asks for something, respond *only* with a JSON object like:\n"
            "{ \"name\": \"<capability>\", \"arguments\": { … } }\n\n"
            "If you cannot match the request to any capability, reply with: "
            "\"ERROR: no capability found\"\n"
        )

        # 3️⃣ Call LLM
        llm_reply = ask_llm(system_prompt, data["content"])
        print(f"llm_reply={llm_reply}")

        # 4️⃣ Parse potential tool invocation
        cap_obj, rest_text = extract_capability_from_reply(llm_reply)
        print(f"cap_obj=={cap_obj}")

        if cap_obj:
            # 5️⃣ Resolve the capability
            cname   = cap_obj.get("name")
            args    = cap_obj.get("arguments", {})
            meta    = caps_map.get(cname)
            if not meta:
                assistant_msg = {"role":"assistant",
                                 "content": f"⚠️ Unknown capability '{cname}'."}
            else:
                # For this demo we only know how to run /add directly
                if meta["uri"] == "/add":
                    try:
                        a = int(args.get("a"))
                        b = int(args.get("b"))
                        result = a + b
                        print("hi we added")
                        assistant_msg = {"role":"assistant",
                                         "content": json.dumps({"result": result})}
                    except Exception as exc:
                        assistant_msg = {"role":"assistant",
                                         "content": f"⚠️ Tool error: {exc}"}
                else:
                    # If you had other tools you would call them here
                    assistant_msg = {"role":"assistant",
                                     "content": f"⚠️ Capability '{cname}' has no executor."}

        else:
            # No JSON – treat the raw LLM reply as assistant text
            print("ran normal chat")
            prompt = build_prompt(history=hist)
            llm_reply = ask_llm("", prompt) #data["content"])
            assistant_msg = {"role":"assistant", "content": llm_reply.strip()}

        # 6️⃣ Store assistant turn and persist history
        hist.append(assistant_msg)
        self.save_chat_history(session_id, hist)

        # 7️⃣ Return to client
        self._send_json(200, assistant_msg)

        print("all done!")

    # --------------------------------------------------------------
    def log_message(self, fmt, *args):
        """Suppress the default stdout logging for each request."""
        pass

# ----------------------------------------------------------------------
# ---------------------- Helper functions --------------------------------
def ask_llm(system_prompt: str, user_query: str) -> str:
    """
    Send a prompt to Ollama (or any LLM that follows the same API).
    Returns the assistant's raw text.
    """
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role":"system", "content": system_prompt},
            {"role":"user",   "content": user_query}
        ],
        "stream": False
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=(5,30))
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as exc:
        # In a real service you might log this.
        return f"⚠️ LLM error: {exc}"

def extract_capability_from_reply(reply_text: str):
    """
    Look for the *first* JSON object in `reply_text` and parse it.
    Returns (obj, rest_of_string).  If no JSON found -> (None,None)
    """
    try:
        start = reply_text.index("{")
    except ValueError:
        return None, None

    decoder = json.JSONDecoder()
    try:
        cap_obj, end_pos = decoder.raw_decode(reply_text[start:])
    except json.JSONDecodeError:
        return None, None

    rest = reply_text[start + end_pos:].strip()
    return cap_obj, rest

from typing import List, Dict, Optional, Any

def build_prompt(
    history:      List[Dict],
    system_msg:   Optional[str] = None,
    max_tokens:   Optional[int] = None,
    tokenizer:    Any          = None,
) -> str:
    """
    Convert a conversation history into the string format the LLM expects.

    Parameters
    ----------
    history:
        List of dicts: [{"role":"user","content":"…"}, {"role":"assistant","content":"…"}]
    system_msg:
        Optional system message that should appear *first*.
    max_tokens, tokenizer:
        If you have a tokeniser (e.g. tiktoken), you can truncate
        the prompt so it never exceeds `max_tokens`.
    """
    # 1️⃣ Build a plain‑text block
    lines = []

    if system_msg is not None:
        lines.append(system_msg.rstrip() + "\n")

    for entry in history:
        role = "Human:" if entry["role"] == "user" else "Assistant:"
        lines.append(f"{role} {entry['content'].strip()}")

    prompt = "\n".join(lines)

    # 2️⃣ Optional token‑budget trimming
    if tokenizer and max_tokens is not None:
        toks = tokenizer.encode(prompt)
        while len(toks) > max_tokens:
            # Drop the *oldest* user–assistant pair (two lines)
            history.pop(0)   # remove first dict
            history.pop(0)   # remove second dict

            # Re‑build prompt & tokens
            lines = []
            if system_msg is not None:
                lines.append(system_msg.rstrip() + "\n")
            for entry in history:
                role = "Human:" if entry["role"] == "user" else "Assistant:"
                lines.append(f"{role} {entry['content'].strip()}")
            prompt = "\n".join(lines)
            toks = tokenizer.encode(prompt)

    return prompt


# ----------------------------------------------------------------------
def run_server() -> None:
    httpd = HTTPServer((HOST, PORT), MCPHandler)
    print(f"🚀 MCP server listening on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == "__main__":
    run_server()
