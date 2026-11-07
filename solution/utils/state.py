"""utils/state.py — Thread state persistence across independent CLI invocations.

Each CLI command (start, say, resume) runs as an isolated OS process.
All conversation history and pending action data survive across process restarts
by being serialized to $AGENT_STATE_DIR/{thread}.json.
"""
import json
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("AGENT_STATE_DIR", ".agent_state"))


def save_state(thread: str, state: dict) -> None:
    """Save thread state dictionary to disk under $AGENT_STATE_DIR/{thread}.json."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / f"{thread}.json"
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(thread: str) -> dict:
    """Load thread state dictionary from disk if it exists, otherwise return empty dict."""
    path = STATE_DIR / f"{thread}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
