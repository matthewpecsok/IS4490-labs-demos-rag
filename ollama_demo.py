# Uncomment to try streaming (requires an updated Ollama server that supports it)

from typing import List,Dict
import requests
import json

OLLAMA_URL = "http://localhost:11434"

def chat_stream(messages: List[Dict[str, str]], model: str = "gpt-oss:20b"):
    payload = {"model": model, "messages": messages}

    stream_resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        stream=True
    )
    if stream_resp.status_code != 200:
        raise RuntimeError(
            f"Unexpected status {stream_resp.status_code} for {OLLAMA_URL}/api/chat"
            f"{stream_resp.text[:120]}…"   # truncate the body for brevity
        )

    print(f"Streaming response status code: {stream_resp.status_code}")
    

    for chunk in stream_resp.iter_lines():
        if chunk:
            part = json.loads(chunk)
            # Ollama streams lines like {"message":{"role":"assistant","content":"..."}}
            yield part["message"]["content"]

# Example usage
conversation_stream: List[Dict[str, str]] = [
    {"role": "user", "content": "Tell me a very long joke about cats."}
]
for token in chat_stream(conversation_stream):
    print(token, end='', flush=True)
