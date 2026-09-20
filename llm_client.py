"""
Thin wrapper around Groq's free-tier chat completion API (OpenAI-compatible),
using only the standard library (urllib) — no `requests` install needed.

Get a free API key at https://console.groq.com/keys and set it as an
environment variable before running the app:

    Windows (PowerShell):  $env:GROQ_API_KEY = "your-key-here"
    Mac/Linux:             export GROQ_API_KEY="your-key-here"
"""
import json
import os
import urllib.request
import urllib.error

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"


def chat_completion(messages, temperature: float = 0.2) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at "
            "https://console.groq.com/keys and set it as an environment variable."
        )

    payload = json.dumps(
        {"model": MODEL, "messages": messages, "temperature": temperature}
    ).encode("utf-8")

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API error {e.code}: {detail}") from e

    return body["choices"][0]["message"]["content"]
