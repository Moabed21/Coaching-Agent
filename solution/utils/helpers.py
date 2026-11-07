"""utils/helpers.py — Shared general-purpose utility functions.

Contains:
  - make_idempotency_key: Deterministic SHA-256 idempotency key generation.
  - respond: Standard JSON output serialization to stdout.
  - get_openai_client: Robust client setup for Azure OpenAI v1 gateway.
  - setup_import_paths: Dynamic discovery for provided PeopleHub package.
"""
import hashlib
import json
import os
import sys
from pathlib import Path
from openai import OpenAI


def setup_import_paths(current_file: str) -> None:
    """Ensure provided package and project root are discoverable in sys.path."""
    curr = Path(current_file).resolve()
    # Add provided directory candidates
    for candidate in [
        curr.parent / "provided",
        curr.parent.parent / "provided",
    ]:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.append(str(candidate))
    # Ensure current directory is in sys.path
    if str(curr.parent) not in sys.path:
        sys.path.insert(0, str(curr.parent))


def make_idempotency_key(thread: str, tool_name: str, args: dict) -> str:
    """Generate a deterministic 32-character SHA-256 idempotency key."""
    raw = f"{thread}:{tool_name}:{json.dumps(args, sort_keys=True)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def respond(status: str, message: str, pending: dict = None) -> None:
    """Print the single JSON object the runner contract expects to stdout."""
    output = {"status": status, "message": message, "pending": pending}
    print(json.dumps(output, ensure_ascii=False))


def get_openai_client() -> OpenAI:
    """Load environment variables cleanly and initialize OpenAI client."""
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    base_url = endpoint + "/openai/v1/"

    return OpenAI(base_url=base_url, api_key=api_key, timeout=60, max_retries=0)
