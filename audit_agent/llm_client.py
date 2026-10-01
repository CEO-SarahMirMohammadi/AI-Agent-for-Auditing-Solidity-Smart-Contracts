"""Simple, robust LLM client focusing on Groq (primary) and OpenAI-compatible fallback.

Changes vs previous implementation:
- Enforces Groq default base URL: https://api.groq.com/openai/v1/chat/completions
- Validates `GROQ_API_KEY` presence and gives clear diagnostics on 403 responses.
- Restricts Groq models to supported options and removes fake/unsupported names.
- Removes deprecated `google.generativeai` Gemini integration.
- Adds simple retry logic for transient failures (429, 5xx).
- Adds structured logging for responses.
"""

from typing import List
import os
import time
import socket
import logging
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

logger = logging.getLogger(__name__)
if not logger.handlers:
    # default to console handler at INFO if user hasn't configured logging
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)


def _build_prompt(snippets: List[str], prompt_extra: str = "") -> str:
    prompt = (
        "You are a Solidity security auditor. For each suspicious snippet below, "
        "explain why it might be risky and give a concise remediation suggestion.\n\n"
        "Snippets:\n"
    )
    for i, s in enumerate(snippets, start=1):
        prompt += f"\n[{i}] {s}\n"
    if prompt_extra:
        prompt += "\nContext: " + prompt_extra
    return prompt


# This function attempts to extract the text response from various LLM response formats, including OpenAI-like and generic structures.
def _parse_response_text(obj) -> str:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        # OpenAI-like
        try:
            return obj["choices"][0]["message"]["content"]
        except Exception:
            pass
        # other common shapes
        if "text" in obj and isinstance(obj["text"], str):
            return obj["text"]
        if "output" in obj and isinstance(obj["output"], dict):
            return obj["output"].get("text") or obj["output"].get("content")
    try:
        return str(obj)
    except Exception:
        return None


def generate_review(snippets: List[str], prompt_extra: str = "") -> str:
    prompt = _build_prompt(snippets, prompt_extra)
    diagnostics = []

    # Primary: Groq OpenAI-compatible endpoint
    groq_key = os.environ.get("GROQ_API_KEY")
    groq_url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").rstrip("/")

    if not groq_key:
        diagnostics.append("GROQ_API_KEY not set; skipping Groq provider.")
    else:
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        # Diagnostic: log presence and masked key (first 6 / last 4 characters only)
        try:
            if isinstance(groq_key, str) and len(groq_key) >= 10:
                masked = f"{groq_key[:6]}...{groq_key[-4:]}"
            else:
                masked = "<short_key>"
        except Exception:
            masked = "<masked>"
        logger.info("GROQ_API_KEY detected=%s masked=%s GROQ_API_URL=%s", True, masked, groq_url)

        # Only allow known Groq models (per requirement)
        allowed_models = ["llama-3.1-8b-instant", "llama-3.1-70b-versatile"]
        env_model = os.environ.get("GROQ_MODEL", "").strip()

        candidates = []
        if env_model and env_model in allowed_models:
            candidates.append(env_model)
        for m in allowed_models:
            if m not in candidates:
                candidates.append(m)

        # Try candidates with retry for transient errors
        for model in candidates:
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800}
            attempt = 0
            while attempt < 3:
                attempt += 1
                try:
                    # best-effort DNS check (not fatal). Verifying DNS reslution before sending request.
                    try:
                        socket.getaddrinfo(urlparse(groq_url).hostname or "api.groq.com", 443)
                    except Exception:
                        pass

                    # Diagnostic prints (masked key, URL, method, model, payload structure)
                    try:
                        print("DIAG: GROQ_API_KEY present:", True)
                        print("DIAG: GROQ_API_KEY masked:", masked)
                    except Exception:
                        print("DIAG: GROQ_API_KEY present: True (masked unavailable)")
                    print("DIAG: Request method:", "POST")
                    print("DIAG: Request URL:", groq_url)
                    print("DIAG: Selected model:", model)
                    try:
                        print("DIAG: Payload keys:", list(payload.keys()))
                    except Exception:
                        print("DIAG: Payload keys: <error>")
                    # Authorization header format (masked)
                    try:
                        auth_format = headers.get("Authorization", "")
                        if auth_format.startswith("Bearer "):
                            print("DIAG: Authorization header format: Bearer <masked>")
                        else:
                            print("DIAG: Authorization header format:", auth_format)
                    except Exception:
                        print("DIAG: Authorization header format: <error>")

                    resp = requests.post(groq_url, json=payload, headers=headers, timeout=20)
                    status = resp.status_code # HTTP response status codes: 200=OK, 403=Forbidden, 429=Too Many Requests, 500-599=Server Errors.
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text

                    # Log model, url, status and truncated body; ensure secrets masked above
                    logger.info("Groq request url=%s model=%s status=%s", groq_url, model, status)
                    logger.info("Groq response body (trunc): %s", str(body)[:500])

                    # Diagnostic prints for response
                    print("DIAG: Response status:", status)
                    if status != 200:
                        print("DIAG: Response body:", body)

                    if status == 200:
                        text = _parse_response_text(body)
                        if text:
                            return text
                        diagnostics.append(f"Groq {model} returned no text.")
                        break
                    if status == 429:
                        diagnostics.append(f"Groq {model} returned 429 (rate limited), retrying (attempt {attempt})")
                        time.sleep(1 + attempt)
                        continue
                    if status == 403:
                        diagnostics.append(f"Groq {model} returned 403 Forbidden; check API key and account access")
                        # 403 likely won't change on retries
                        break
                    if 500 <= status < 600:
                        diagnostics.append(f"Groq {model} returned {status} (server error), retrying (attempt {attempt})")
                        time.sleep(1 + attempt)
                        continue
                    # other 4xx
                    diagnostics.append(f"Groq {model} returned {status}: {body}")
                    break
                except requests.exceptions.RequestException as e:
                    diagnostics.append(f"Groq request error for model {model}: {e} (attempt {attempt})")
                    time.sleep(0.5 * attempt)
                    continue

    # Fallback: OpenAI-compatible HTTP API if configured
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            openai_url = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
            openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o")
            payload = {"model": openai_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800}
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            r = requests.post(openai_url, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            j = r.json()
            text = _parse_response_text(j)
            if text:
                return text
            diagnostics.append(f"OpenAI-compatible response had no text: {j}")
        except Exception as e:
            diagnostics.append(f"OpenAI fallback failed: {e}")

    # No provider succeeded
    if diagnostics:
        header = "LLM providers returned no usable result:\n"
        # return up to first 12 diagnostics for brevity
        diag_text = "\n".join(diagnostics[:12])
        return header + diag_text + "\n\nPrompt:\n" + prompt

    return "No LLM provider configured. Set GROQ_API_KEY or OPENAI_API_KEY in the environment."
