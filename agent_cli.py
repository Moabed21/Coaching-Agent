"""Command-line adapter: one command in, ONE JSON object out. Every command is a new process.

    python3 agent_cli.py start  --thread T --user U --message "text"
    python3 agent_cli.py say    --thread T --message "text" [--user U]
    python3 agent_cli.py resume --thread T --decision approve|reject|modify --by EMPLOYEE_ID [--edit '{"k": "v"}']

Logs go to standard error; standard output carries only the JSON answer (see harness/README.md).
This file holds no business rule: it calls the modules in agent/ in the right order.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Literal

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # agent/ and peoplehub/ live next to this file

from agent import approval, executor, policy, state as store  # noqa: E402
from agent.approval import Asking, Pending  # noqa: E402
from agent.executor import WriteResult  # noqa: E402
from agent.llm import make_llm  # noqa: E402
from agent.loop import run  # noqa: E402
from agent.state import State  # noqa: E402

Status = Literal["done", "awaiting_approval", "error"]

# The three commands, registered by the @command decorator below: {"start": start, ...}
COMMANDS: dict[str, Callable[[argparse.Namespace], None]] = {}


def command(name: str):
    """Decorator: register a function as the handler of one CLI command."""
    def register(handler: Callable[[argparse.Namespace], None]):
        COMMANDS[name] = handler
        return handler
    return register


def respond(status: Status, message: str, pending: Asking | None = None) -> None:
    """Print the one JSON object the runner expects."""
    print(json.dumps({"status": status, "message": message, "pending": pending}, ensure_ascii=False))


def finish(thread: str, st: State, status: Status, text: str, pending: Asking | None = None) -> None:
    """Remember what we told the user, save, answer. Every command ends here."""
    st["messages"].append({"role": "assistant", "content": text})
    store.save(thread, st)
    respond(status, text, pending)


# ------------------------------------------------------------------ start and say: the model's turn
@command("start")
def start(a: argparse.Namespace) -> None:
    if not a.user:
        return respond("error", "start needs --user.")
    if store.load(a.thread) is not None:
        return respond("error", f"Conversation {a.thread} already exists; use say.")
    take_turn(a.thread, store.new(a.user), a.message)


@command("say")
def say(a: argparse.Namespace) -> None:
    st = store.load(a.thread)
    if st is None:
        return respond("error", f"No conversation {a.thread}; use start first.")
    if a.user and a.user != st["user"]:  # the actor is fixed per thread
        return respond("error", "This conversation belongs to someone else.")
    if st["pending"]:  # one waiting action at a time
        return respond("error", "A request in this conversation is still waiting for approval.")
    take_turn(a.thread, st, a.message)


def take_turn(thread: str, st: State, message: str) -> None:
    st["messages"].append({"role": "user", "content": message})
    out = run(st["messages"], st["user"], thread, make_llm())
    if "answer" in out:
        return finish(thread, st, "done", out["answer"])

    # A proposal: the text is written by code, not the model, because it is a claim (who was asked, for what).
    st["pending"] = approval.open_request(out["proposal"])
    ask = approval.asking(st["pending"])
    text = (f"I have asked {', '.join(ask['approvers'])} to approve this: {ask['summary']}. "
            f"Nothing happens until they approve. {st['pending']['note']}").strip()
    finish(thread, st, "awaiting_approval", text, ask)


# ------------------------------------------------------------------ resume: the human's turn
@command("resume")
def resume(a: argparse.Namespace) -> None:
    thread, by = a.thread, a.by
    edit = json.loads(a.edit) if a.edit else {}

    # 1. Load.
    st = store.load(thread)
    if not st or not st["pending"]:
        return respond("error", "Nothing is waiting for approval in this conversation.")

    # 2. Apply the human's decision (pure: approval.py).
    outcome, pending, text = approval.decide(st["pending"], a.decision, by, edit)

    # 3. Check again: time has passed and the args may have been edited.
    if pending is not None:
        try:
            pending["summary"] = policy.plan(pending["tool"], pending["args"], st["user"])["summary"]
        except policy.Refused as e:
            outcome, pending = "closed", None
            text = f"I checked again before going ahead, and it is not possible now: {e} Nothing was booked or changed."

    # 4. Closed or another round: save and say so.
    if outcome == "closed" or pending is None:
        st["pending"] = None
        return finish(thread, st, "done", text)
    if outcome == "ask":
        st["pending"] = pending
        return finish(thread, st, "awaiting_approval", text, approval.asking(pending))

    # 5. Execute. Save the key BEFORE the call, so a re-run after a crash reuses it.
    pending["idempotency_key"] = executor.idempotency_key(thread, pending["tool"], pending["args"], st["writes"])
    st["pending"] = pending
    store.save(thread, st)
    result = executor.execute(pending, st["user"])
    st["pending"] = None
    if result["ok"]:
        st["writes"] += 1  # only a write that happened moves the counter
    finish(thread, st, "done", report(pending, result))


def report(pending: Pending, result: WriteResult) -> str:
    """Tell the truth: what was done, by whose approval, or exactly what went wrong."""
    who = ", ".join(pending["approved_by"])
    if result["ok"]:
        r = result["result"]
        retried = " (the first try hit a temporary error, so I tried once more)" if result["attempts"] > 1 else ""
        if pending["tool"] == "cancel_enrolment":
            return f"Done{retried}: enrolment {r['enrolment_id']} is cancelled, approved by {who}."
        return (f"Done{retried}: you are booked on {r['course_id']}, session {r['session_id']} "
                f"(enrolment {r['enrolment_id']}), approved by {who}.")
    tries = "twice" if result["attempts"] > 1 else "once"
    return (f"{who} approved, but PeopleHub refused when I tried ({tries}): {result['error']}: "
            f"{result['message']} Nothing was booked or changed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--thread", required=True)
    parser.add_argument("--user")
    parser.add_argument("--message")
    parser.add_argument("--decision", choices=["approve", "reject", "modify"])
    parser.add_argument("--by")
    parser.add_argument("--edit")
    a = parser.parse_args()
    try:
        COMMANDS[a.command](a)
    except Exception as exc:  # a crash must still print valid JSON
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        respond("error", "Something went wrong on my side, and nothing was changed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
