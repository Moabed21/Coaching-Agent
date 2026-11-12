"""The conversation on disk: the only memory shared between two commands.

One JSON file per thread in $AGENT_STATE_DIR. It holds who we act for, the whole conversation
(so `say` has context), the pending request (so `resume` can finish it), and a write counter.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, TypedDict

from .approval import Pending

THREAD_ID = re.compile(r"[A-Za-z0-9_.-]{1,100}")


class State(TypedDict):
    version: int
    user: str                      # who we act for: fixed for the whole thread
    messages: list[dict[str, Any]]  # the whole conversation, without the system prompt
    pending: Pending | None        # the request waiting for humans, if any
    writes: int                    # writes done so far: part of the idempotency key


def _path(thread: str) -> Path:
    if not THREAD_ID.fullmatch(thread) or thread.startswith("."):
        raise ValueError(f"bad thread id {thread!r}")  # a thread id becomes a file name: no '../'
    return Path(os.environ.get("AGENT_STATE_DIR", ".agent_state")) / f"{thread}.json"


def new(user: str) -> State:
    return {"version": 1, "user": user, "messages": [], "pending": None, "writes": 0}


def load(thread: str) -> State | None:
    """The saved state of a thread, or None if the thread does not exist."""
    path = _path(thread)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save(thread: str, state: State) -> None:
    """Write to a temporary file, then rename it over the old one.

    os.replace is atomic: a crash leaves the old file or the new one, never half of each.
    """
    path = _path(thread)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
