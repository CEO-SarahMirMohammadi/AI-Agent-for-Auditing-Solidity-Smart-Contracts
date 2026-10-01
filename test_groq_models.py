"""Groq model discovery and validation script.

This script queries the Groq OpenAI-compatible /models endpoint to discover
all models available to the current API key, validates the configured
GROQ_MODEL, and saves results to models.json.

Usage:
    python test_groq_models.py [--groq-key KEY]

If no --groq-key is supplied, reads from GROQ_API_KEY environment variable
or from .env file (via dotenv).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env before checking environment
load_dotenv()

DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/models"
# Only list currently supported Groq models for validation
KNOWN_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Discover available Groq models.")
    parser.add_argument("--groq-key", help="Groq API key")
    parser.add_argument("--groq-url", help="Groq models API URL", default=DEFAULT_GROQ_URL)
    return parser.parse_args()


def fetch_available_models(groq_url: str, groq_key: str) -> dict:
    """Fetch available models from Groq API.
    
    Returns a dict with keys:
    - success: bool
    - models: list of model dicts or empty list
    - error: error message if failed
    """
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json",
    }

    try:
        print(f"Fetching models from {groq_url} ...")
        resp = requests.get(groq_url, headers=headers, timeout=20)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 401:
            return {
                "success": False,
                "models": [],
                "error": "Unauthorized: API key is invalid or missing",
            }

        if resp.status_code != 200:
            try:
                data = resp.json()
                error_msg = data.get("error", {}).get("message", str(data))
            except Exception:
                error_msg = resp.text
            return {
                "success": False,
                "models": [],
                "error": f"HTTP {resp.status_code}: {error_msg}",
            }

        data = resp.json()
        models = data.get("data", [])

        print(f"  Found {len(models)} models")
        return {
            "success": True,
            "models": models,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "models": [],
            "error": f"Request failed: {e}",
        }


def extract_model_names(models: list) -> list:
    """Extract model IDs from the API response."""
    names = []
    for m in models:
        if isinstance(m, dict) and "id" in m:
            names.append(m["id"])
        elif isinstance(m, str):
            names.append(m)
    return names


def main():
    args = parse_args()

    groq_key = args.groq_key or os.environ.get("GROQ_API_KEY")
    groq_url = args.groq_url
    env_model = os.environ.get("GROQ_MODEL")

    print("Groq Model Discovery")
    print("=" * 60)
    print(f"GROQ_API_KEY present: {bool(groq_key)}")
    print(f"GROQ_MODEL configured: {env_model!r}")
    print(f"GROQ_API_URL: {groq_url}")

    if not groq_key:
        print("\nERROR: No GROQ_API_KEY found in environment or --groq-key argument")
        print("Please set GROQ_API_KEY or run: python test_groq_models.py --groq-key YOUR_KEY")
        return 1

    result = fetch_available_models(groq_url, groq_key)

    if not result["success"]:
        print(f"\nERROR fetching models: {result['error']}")
        return 1

    models = result["models"]
    model_names = extract_model_names(models)

    print(f"\n{'=' * 60}")
    print(f"Available Models ({len(model_names)} total)")
    print("=" * 60)
    for idx, name in enumerate(model_names, start=1):
        marker = ""
        if env_model and name == env_model:
            marker = " <-- GROQ_MODEL"
        elif name in KNOWN_MODELS:
            marker = " <-- Known Groq model"
        print(f"{idx:2}. {name}{marker}")

    print(f"\n{'=' * 60}")
    print("Validation")
    print("=" * 60)

    if env_model:
        if env_model in model_names:
            print(f"✓ GROQ_MODEL '{env_model}' EXISTS in available models")
        else:
            print(f"✗ GROQ_MODEL '{env_model}' DOES NOT EXIST in available models")
            print(f"\n  Available alternatives:")
            for idx, name in enumerate(KNOWN_MODELS[:3], start=1):
                if name in model_names:
                    print(f"    {idx}. {name}")
    else:
        print("⚠ No GROQ_MODEL configured; will use first available")
        if model_names:
            print(f"  Default will be: {model_names[0]}")

    print(f"\n{'=' * 60}")
    print("Saving to models.json")
    print("=" * 60)

    output = {
        "timestamp": str(os.popen('python -c "import datetime; print(datetime.datetime.now())"').read().strip()),
        "groq_api_url": groq_url,
        "groq_model_configured": env_model,
        "total_available_models": len(model_names),
        "available_models": model_names,
        "known_groq_models": KNOWN_MODELS,
        "validation": {
            "groq_model_exists": env_model in model_names if env_model else None,
            "first_available_model": model_names[0] if model_names else None,
        },
    }

    with open("models.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to models.json")

    print(f"\n{'=' * 60}")
    print("Summary")
    print("=" * 60)
    print(f"Total models available: {len(model_names)}")
    if env_model:
        status = "EXISTS" if env_model in model_names else "NOT FOUND"
        print(f"GROQ_MODEL '{env_model}': {status}")
    print(f"Recommended model: {model_names[0] if model_names else 'NONE'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
