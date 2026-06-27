#!/usr/bin/env python3

import json
import requests
import sys

# --------------------------------------------------------------
# Configuration – change if you run Ollama elsewhere
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "gpt-oss:20b"          # same as your original script
TIMEOUT    = (5, 30)             # connect / read timeout in seconds
# --------------------------------------------------------------

def ask_ollama(messages):
    """
    Send the current conversation to Ollama and return the full response.

    :param messages: List[dict] – a list of role/content pairs as expected by Ollama.
    :return: dict – the JSON body returned by the server.
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        # We’re not using streaming; just get the full answer in one response
        "stream": False
    }

    try:
        resp = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT,      # (connect, read)
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()           # raise for 4xx/5xx
        return resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"\n⚠️  Ollama request failed: {exc} with response {resp.text}", file=sys.stderr)
        sys.exit(1)

def main():
    messages = []          # conversation history

    while True:
        try:
            prompt = input("You: ").strip()
        except EOFError:   # user pressed Ctrl-D / Ctrl-Z
            print("\nBye!")
            break

        if not prompt:
            continue                    # ignore empty lines

        if prompt.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        # Append the user message to history
        messages.append({"role": "user", "content": prompt})

        # Ask Ollama for a reply
        response = ask_ollama(messages)

        # Pull the assistant's text out of the JSON structure
        answer = response.get("message", {}).get("content", "")
        print(f"AI: {answer}")

        # Append the assistant message to history so the model knows context
        messages.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    main()
