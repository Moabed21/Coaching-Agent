"""The ONLY place in the agent that books or cancels an enrolment."""
import functools
import hashlib
import json
from typing import Any, Callable, NotRequired, TypedDict

from peoplehub import ApiError, learning
from agent.approval import Pending

WRITES = {"request_enrolment": learning.request_enrolment, "cancel_enrolment": learning.cancel_enrolment}
MAX_ATTEMPTS = 2  # the first try, plus ONE retry for a temporary failure


class WriteResult(TypedDict):
    ok: bool
    attempts: int
    result: NotRequired[dict]   # when ok
    error: NotRequired[str]     # when not ok, e.g. "ERR_SESSION_FULL"
    message: NotRequired[str]


def idempotency_key(thread: str, tool: str, args: dict, n: int) -> str:
    """Same thread + tool + args + write counter -> same key. A retry reuses it; a new action gets a new one."""
    raw = json.dumps([thread, tool, args, n], sort_keys=True)  # sort_keys: argument order must not matter
    return "lc-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def fully_approved(pending: Pending) -> bool:
    """One human per round, each one of the people allowed for that round."""
    given = pending.get("approved_by", [])
    rounds = pending["rounds"]
    if not rounds:                       # no approvers at all (e.g. a mandatory course): never write
        return False
    if len(given) != len(rounds):        # a round is missing
        return False
    for person, allowed in zip(given, rounds):
        if person not in allowed:        # someone approved a round that wasn't theirs
            return False
    return True


def retry_once_if_temporary(write: Callable[..., dict]) -> Callable[..., WriteResult]:
    """Decorator: call `write`; if PeopleHub says the failure is temporary, try once more
    with the SAME arguments (so the same idempotency key). Never raises ApiError."""
    @functools.wraps(write)
    def wrapper(*args: Any, **kwargs: Any) -> WriteResult:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return {"ok": True, "result": write(*args, **kwargs), "attempts": attempt}
            except ApiError as e:
                try_again = e.retryable and attempt < MAX_ATTEMPTS
                if not try_again:
                    return {"ok": False, "error": e.code, "message": e.message, "attempts": attempt}
        raise AssertionError("unreachable: the last attempt always returns")
    return wrapper


@retry_once_if_temporary
def _write(pending: Pending, actor: str) -> dict:
    write = WRITES[pending["tool"]]
    return write(**pending["args"], actor=actor,
                 approved_by=",".join(pending["approved_by"]),
                 idempotency_key=pending["idempotency_key"])


def execute(pending: Pending, actor: str) -> WriteResult:
    """Carry out a fully approved action."""
    if not fully_approved(pending):  # the last line of the gate: no approvals, no write
        raise RuntimeError("refusing to write: the approvals are not complete")
    return _write(pending, actor)
