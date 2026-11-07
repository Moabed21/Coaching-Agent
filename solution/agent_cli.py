"""Your agent's command-line interface.

The runner (harness/run_scenarios.py) starts this program once per command, as a NEW process each time:
    python agent_cli.py start  --thread T --user U --message "text"
    python agent_cli.py say    --thread T --message "text" [--user U]
    python agent_cli.py resume --thread T --decision approve|reject|modify --by EMPLOYEE_ID [--edit '{"key": "value"}']

Every command prints exactly ONE JSON object on standard output (logs go to standard error).
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Ensure solution directory and provided package are discoverable
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))
for candidate in [
    CURR_DIR / "provided",
    CURR_DIR.parent / "provided",
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from peoplehub import learning, directory, ApiError
from agent_loop import run_agent_loop
from gate import validate_approval
from utils import respond, save_state, load_state, make_idempotency_key, STATE_DIR


def start(thread: str, user: str, message: str):
    """Start a new conversation thread."""
    messages = [{"role": "user", "content": message}]
    status, reply_msg, pending, updated_messages = run_agent_loop(messages, actor=user)

    state = {
        "user": user,
        "messages": updated_messages,
        "pending_action": pending,
        "first_approval": None,
    }
    save_state(thread, state)
    respond(status, reply_msg, pending=pending)


def say(thread: str, user: str, message: str):
    """Continue an existing conversation thread whose last request finished."""
    state = load_state(thread)
    actor = user or state.get("user")
    messages = state.get("messages", [])
    messages.append({"role": "user", "content": message})

    status, reply_msg, pending, updated_messages = run_agent_loop(messages, actor=actor)

    state["messages"] = updated_messages
    state["pending_action"] = pending
    save_state(thread, state)
    respond(status, reply_msg, pending=pending)


def resume(thread: str, decision: str, by: str, edit: dict):
    """Deliver a human approval decision on a pending action."""
    state = load_state(thread)
    actor = state.get("user")
    pending = state.get("pending_action")

    if not pending:
        respond("error", "No pending action found for this conversation.")
        return

    if decision == "reject":
        state["pending_action"] = None
        save_state(thread, state)
        respond("done", f"Your request was rejected by {by}. Nothing was booked or changed.")
        return

    # decision in ("approve", "modify")
    final_args = validate_approval(pending, decision, by, edit)

    # Check two-step approval requirement (> QAR 3,000)
    needs_two_step = pending.get("needs_two_step", False)
    first_approval = state.get("first_approval")

    if needs_two_step and not first_approval:
        # Step 1: Line manager approved. Now ask Head of HR (E1068).
        state["first_approval"] = by
        pending["args"] = final_args
        pending["approvers"] = [pending.get("hr_head_id", "E1068")]
        state["pending_action"] = pending
        save_state(thread, state)
        respond(
            "awaiting_approval",
            f"Line manager {by} approved the enrolment. Awaiting second-round approval from Head of HR ({pending['approvers'][0]}).",
            pending=pending,
        )
        return

    # Final execution
    if first_approval:
        approved_by_str = f"{first_approval},{by}"
    else:
        approved_by_str = by

    tool_name = pending["tool"]
    key = make_idempotency_key(thread, tool_name, final_args)

    try:
        if tool_name == "request_enrolment":
            try:
                res = learning.request_enrolment(
                    **final_args,
                    actor=actor,
                    approved_by=approved_by_str,
                    idempotency_key=key,
                )
            except ApiError as err:
                if err.retryable:
                    # Retry once with identical idempotency key
                    res = learning.request_enrolment(
                        **final_args,
                        actor=actor,
                        approved_by=approved_by_str,
                        idempotency_key=key,
                    )
                else:
                    raise

            state["pending_action"] = None
            save_state(thread, state)
            respond(
                "done",
                f"You have been successfully booked onto course {final_args['course_id']} session {final_args['session_id']} (Approved by {approved_by_str}).",
            )

        elif tool_name == "cancel_enrolment":
            try:
                res = learning.cancel_enrolment(
                    **final_args,
                    actor=actor,
                    approved_by=approved_by_str,
                    idempotency_key=key,
                )
            except ApiError as err:
                if err.retryable:
                    res = learning.cancel_enrolment(
                        **final_args,
                        actor=actor,
                        approved_by=approved_by_str,
                        idempotency_key=key,
                    )
                else:
                    raise

            state["pending_action"] = None
            save_state(thread, state)
            respond("done", f"Enrolment {final_args['enrolment_id']} has been successfully cancelled.")

        else:
            respond("error", f"Unknown tool to execute: {tool_name}")

    except ApiError as e:
        print(f"ApiError during write: {e.code}: {e.message}", file=sys.stderr)
        respond("error", f"PeopleHub refused the action: {e.message} ({e.code})")
    except Exception as exc:
        print(f"Exception during write: {exc}", file=sys.stderr)
        respond("error", f"An error occurred while executing the action: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "say", "resume"])
    parser.add_argument("--thread", required=True)
    parser.add_argument("--user")
    parser.add_argument("--message")
    parser.add_argument("--decision", choices=["approve", "reject", "modify"])
    parser.add_argument("--by")
    parser.add_argument("--edit")
    a = parser.parse_args()

    try:
        if a.command == "start":
            start(a.thread, a.user, a.message)
        elif a.command == "say":
            say(a.thread, a.user, a.message)
        else:
            resume(a.thread, a.decision, a.by, json.loads(a.edit) if a.edit else {})
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        respond("error", "Something went wrong on my side, and nothing was changed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
