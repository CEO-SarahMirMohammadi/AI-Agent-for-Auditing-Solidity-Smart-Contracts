"""Standalone Groq connectivity tester.

This script verifies whether the configured Groq OpenAI-compatible endpoint is
reachable, whether DNS resolves correctly, and whether a simple /chat/completions
request succeeds.

Usage:
    python test_groq_connection.py [--groq-key KEY] [--groq-url URL]

If no `--groq-key` is supplied, the script reads `GROQ_API_KEY` from the
environment or from a local `.env` file.
"""

import argparse
import os
import socket
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"


def parse_args():
    parser = argparse.ArgumentParser(description="Test Groq API connectivity.")
    parser.add_argument("--groq-key", help="Groq API key")
    parser.add_argument("--groq-url", help="Groq API base URL")
    parser.add_argument(
        "--groq-model",
        help="Groq model name (defaults to gpt-4o-mini for OpenAI-compatible endpoint)",
        default=DEFAULT_MODEL,
    )
    return parser.parse_args()


def main():
    args = parse_args()

    groq_key = args.groq_key or os.environ.get("GROQ_API_KEY")
    groq_url = (args.groq_url or os.environ.get("GROQ_API_URL") or DEFAULT_GROQ_URL).rstrip("/")
    groq_model = args.groq_model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    print("Groq connectivity tester")
    print("========================")
    print(f"Groq URL: {groq_url}")
    print(f"Groq model: {groq_model}")
    print(f"Groq API key present: {bool(groq_key)}")
    print(f"requests version: {requests.__version__}")

    host = urlparse(groq_url).hostname
    if not host:
        print("ERROR: Unable to parse hostname from Groq URL")
        return

    try:
        print(f"Resolving DNS for {host} ...")
        addrs = socket.getaddrinfo(host, 443)
        print("  Resolver returned:")
        for addr in addrs[:4]:
            print("   ", addr)
    except Exception as e:
        print(f"DNS resolution failed: {e}")
        return

    headers = {"Content-Type": "application/json"}
    if groq_key:
        headers["Authorization"] = f"Bearer {groq_key}"

    print(f"Sending OPTIONS probe to {groq_url} ...")
    try:
        options_resp = requests.options(groq_url, headers=headers, timeout=10)
        print(f"  OPTIONS status: {options_resp.status_code}")
        print(f"  Allow: {options_resp.headers.get('Allow')}")
    except Exception as e:
        print(f"  OPTIONS request failed: {e}")

    if not groq_key:
        print("No Groq API key provided; skipping authenticated POST test.")
        return

    # Restrict to Groq-supported models for this project
    model_candidates = [groq_model, "llama-3.1-8b-instant", "llama-3.1-70b-versatile"]
    seen = set()
    model_candidates = [m for m in model_candidates if m and not (m in seen or seen.add(m))]

    for model in model_candidates:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            "max_tokens": 50,
        }

        print(f"\nSending POST /chat/completions request with model {model} ...")
        try:
            resp = requests.post(groq_url, json=payload, headers=headers, timeout=20)
            print(f"  POST status: {resp.status_code}")
            try:
                data = resp.json()
                print("  JSON response keys:", list(data.keys()))
                if "error" in data:
                    print("  error:", data["error"])
                elif "choices" in data and data["choices"]:
                    first = data["choices"][0]
                    print("  choices[0] keys:", list(first.keys()) if isinstance(first, dict) else type(first))
                    if isinstance(first, dict) and "message" in first:
                        print("  message content:", first["message"].get("content"))
                    elif isinstance(first, dict) and "text" in first:
                        print("  text:", first.get("text"))
                else:
                    print("  response body:", data)
            except ValueError:
                print("  Response is not JSON:", resp.text)
        except Exception as e:
            print(f"  POST request failed: {e}")


if __name__ == "__main__":
    main()
