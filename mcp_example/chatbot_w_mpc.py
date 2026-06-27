#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimal MCP client – no helper wrappers.
Dynamic capability discovery + generic dispatcher + LLM‑driven command extraction.

Compatible with Python ≥ 3.6 (no PEP‑604 syntax).
"""

import json
import re
import sys
from typing import Dict, Optional

import requests

# ----------------------------------------------------------------------
# Configuration – adjust for your environment
# ----------------------------------------------------------------------
OLLAMA_URL       = "http://localhost:11434/api/chat"
CAPABILITIES_URL = "http://localhost:8000/capabilities"  # MCP endpoint that returns the capability map
MCP_ROOT         = "http://localhost:8000"              # Base URL for any further calls

MODEL            = "gpt-oss:20b"                       # <-- must be defined
TIMEOUT          = (5, 30)      # connect / read timeout

# ----------------------------------------------------------------------
# Global cache of the discovered capabilities dict & helper set
# ----------------------------------------------------------------------
CAP_MAP: Optional[Dict[str, Dict]] = None            # name → capability details
KNOWN_CAPS_LOWER: Optional[set] = None                # lowercase names for quick lookup


def discover_capabilities() -> None:
    """Fetch and store the capability map for later use."""
    global CAP_MAP, KNOWN_CAPS_LOWER

    try:
        resp = requests.get(CAPABILITIES_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, dict):
            print("\n⚠️  Expected a JSON object but got something else.", file=sys.stderr)
            CAP_MAP = {}
            KNOWN_CAPS_LOWER = set()
            return

        CAP_MAP = data
        KNOWN_CAPS_LOWER = {name.lower() for name in CAP_MAP}
        print("\n✅  Discovered the following capabilities:")
        for name in sorted(CAP_MAP.keys()):
            print(f"   • {name}")
    except Exception as exc:
        print(f"\n❌  Could not discover capabilities: {exc}", file=sys.stderr)
        CAP_MAP = {}
        KNOWN_CAPS_LOWER = set()


def call_capability(name: str, payload: Dict,prompt: str) -> None:
    """
    Generic dispatcher.

    :param name: capability name as returned by the discovery step.
    :param payload: JSON body to send.
    """
    if not CAP_MAP or name not in CAP_MAP:
        print(f"\n❌  Capability '{name}' not known. Run discover_capabilities() first.", file=sys.stderr)
        return

    meta = CAP_MAP[name]
    url   = f"{MCP_ROOT}{meta.get('uri', '/conversation')}"
    method= meta.get("method", "POST").upper()

    print(f"payload:{payload}")

    try:
        resp = requests.request(method, url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        print("\n✅  Server replied:")
        print(ask_llm("Interpret the result for the user", f"the user asked {prompt} and the tool for the capability {CAP_MAP} received the input {payload} returned the result {json.dumps(resp.json(), indent=2)}"))
        try:
            print(json.dumps(resp.json(), indent=2))
        except ValueError:          # not JSON
            print(resp.text)
    except Exception as exc:
        print(f"\n❌  Request failed: {exc}", file=sys.stderr)


# ----------------------------------------------------------------------
# New helpers – LLM integration
# ----------------------------------------------------------------------


def build_system_prompt() -> str:
    """Return a system message that lists every discovered capability."""
    if not CAP_MAP:
        return (
            "You have no capabilities available. "
            "When asked for something, you will be unable to provide a usable answer."
        )

    caps = []
    for name, meta in sorted(CAP_MAP.items()):
        entry: Dict[str, object] = {"name": name}
        if "description" in meta:
            entry["description"] = meta["description"]
        if "parameters" in meta:
            entry["parameters"] = meta["parameters"]
        caps.append(entry)

    system_text = (
        f"You have access to the following capabilities:\n"
        f"{json.dumps(caps, indent=2)}\n\n"
        "When a user asks for something, respond *only* with a JSON object "
        "containing **one** capability invocation in the form:\n"
        "{ \"name\": <capability_name>, \"arguments\": { … } }\n\n"
        "If you cannot match the request to any capability, reply with "
        "\"ERROR, no capability found\".\n\n. In that case you are done. Do not ask the user if they would like to run the capability. "
        "If you found a valid capability then: After providing the JSON, ask: 'Would you like me to run that?'"
    )
    return system_text


def ask_llm(system_msg: str, user_msg: str) -> str:
    """Send a system + user message to Ollama and return the assistant's text."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg}
        ],
        "stream": False
    }
    try:
        resp = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except requests.exceptions.RequestException as exc:
        print(f"\n⚠️  Ollama request failed: {exc}", file=sys.stderr)
        sys.exit(1)


def extract_capability_from_reply(reply_text: str):
    """
    Return the first JSON object found in *reply_text* and everything that follows it.

    If no JSON object can be parsed, returns (None, None).
    """
    try:
        # Find the very first '{' – raw_decode expects a valid JSON fragment.
        start = reply_text.index("{")
    except ValueError:          # no opening brace
        return None, None

    decoder = json.JSONDecoder()
    try:
        cap_obj, end_pos = decoder.raw_decode(reply_text[start:])
    except json.JSONDecodeError:  # the substring isn’t valid JSON
        return None, None

    # end_pos is relative to reply_text[start:], so add start to get the real index.
    rest = reply_text[start + end_pos:].strip()
    return cap_obj, rest


# ----------------------------------------------------------------------
# Main interaction loop
# ----------------------------------------------------------------------


def main():
    discover_capabilities()          # pull the capability map once at start

    chat_history = []                # (optional) keep for future context

    while True:
        try:
            prompt = input("You: ").strip()
        except EOFError:
            print("\nBye!")
            break

        if not prompt:
            continue

        # 1. Show capabilities again if requested
        if prompt.lower() in {"discover", "caps", "capabilities"}:
            discover_capabilities()
            continue

        # 2. Exit commands
        if prompt.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        # 3. Attempt to interpret the first word as a capability name.
        # Removed

        # 4. Anything else is a natural‑language request for Ollama.
        system_msg = build_system_prompt()

        reply_text = ask_llm(system_msg, prompt)

        # Parse the assistant’s answer
        cap_invocation, followup = extract_capability_from_reply(reply_text)

        if cap_invocation:
            print(f"\n> I believe I have a tool that can do that. Would you like me to use the tool: {cap_invocation['name']}")

            # Ask for confirmation
            answer = input("\nWould you like me to run that? (yes/no): ").strip().lower()
            if answer not in ("yes", "y"):
                print("Cancelled.")
                continue

            call_capability(cap_invocation["name"], cap_invocation.get("arguments", {}),prompt)
        else:
            # No JSON found – just show the full assistant reply
            print(f"\nAI: {reply_text}")

        # Keep history (optional)
        chat_history.append({"role": "user", "content": prompt})
        chat_history.append({"role": "assistant", "content": reply_text})


if __name__ == "__main__":
    main()
