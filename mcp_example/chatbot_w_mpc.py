#!/usr/bin/env python3
import json, sys, requests

HOST = "http://localhost:8000"

def main():
    session_id = input("Session ID (new or existing): ").strip() or "demo"
    print(f"Using session {session_id}. Type your messages; 'exit' to quit.")
    while True:
        msg = input("> ")
        if msg.lower() in {"exit","quit"}: break
        payload = {
            "session_id": session_id,
            "role": "user",
            "content": msg
        }
        try:
            print(f"sent payload:{payload}")
            resp = requests.post(f"{HOST}/chat", json=payload)
            resp.raise_for_status()
            out = resp.json()
            print(out["content"])
        except Exception as exc:
            print(f"Error: {exc}")

if __name__ == "__main__":
    main()
