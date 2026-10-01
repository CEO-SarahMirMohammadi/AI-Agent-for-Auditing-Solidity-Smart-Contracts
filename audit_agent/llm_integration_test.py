"""LLM integration test runner for local diagnostics.

Tests performed:
- Environment variable loading
- dotenv presence
- DNS resolution for Groq host
- Groq endpoint connectivity (probes candidate URLs)
- Basic API auth header check
- Generate review call and report result
- Fallback checks for Gemini/OpenAI presence

This script is diagnostic and tolerant of network failures; it reports
findings to help debug integration issues.
"""
import os
import socket
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
from . import llm_client


def check_env():
    print("\n== Environment Variables ==")
    keys = ["GROQ_API_KEY", "GROQ_API_URL", "GROQ_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY"]
    for k in keys:
        print(f"{k}: {os.environ.get(k)!r}")


def check_dotenv():
    print("\n== Dotenv ==")
    ok = load_dotenv()
    print(f"load_dotenv() returned: {ok}")
    print(f".env file exists: {os.path.exists('.env')}")


def dns_test():
    print("\n== DNS Resolution ==")
    groq_url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    host = urlparse(groq_url).hostname or "api.groq.com"
    try:
        addrs = socket.getaddrinfo(host, 443)
        print(f"Resolved {host}: {addrs[:2]}")
    except Exception as e:
        print(f"DNS resolution failed for {host}: {e}")


def probe_groq():
    print("\n== Groq Connectivity Probes ==")
    groq_key = os.environ.get("GROQ_API_KEY")
    groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_base = os.environ.get("GROQ_API_URL")
    candidates = []
    if groq_base:
        candidates.append(groq_base.rstrip('/'))
    candidates += [
        "https://api.groq.com/openai/v1/chat/completions",
    ]
    seen = set()
    candidates = [u for u in candidates if not (u in seen or seen.add(u))]
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"} if groq_key else {}
    for url in candidates:
        try:
            print(f"Probing {url} ...")
            r = requests.options(url, headers=headers, timeout=5)
            print(f"  status: {r.status_code}")
        except Exception as e:
            print(f"  probe failed: {e}")


def generate_test():
    print("\n== generate_review() Test ==")
    snippets = ["// test snippet - reentrancy"]
    out = llm_client.generate_review(snippets, prompt_extra="diagnostic test")
    print("Result:\n", out)


def fallback_checks():
    print("\n== Fallback Checks ==")
    print("genai module present:", llm_client.genai is not None)
    print("GEMINI_API_KEY present:", os.environ.get("GEMINI_API_KEY") is not None)
    print("OPENAI_API_KEY present:", os.environ.get("OPENAI_API_KEY") is not None)


if __name__ == '__main__':
    print("LLM integration diagnostics")
    check_dotenv()
    check_env()
    dns_test()
    probe_groq()
    generate_test()
    fallback_checks()
