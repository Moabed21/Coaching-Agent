"""The approval gate: a small state machine. No model, no PeopleHub, no disk.

    open --approve--> (more rounds?) --yes--> open, next round
      |                                --no---> execute   (every round has a human yes)
      +--reject / wrong person / forbidden edit--> closed (nothing is written)

Pure functions in, plain dicts out: that is what makes this file easy to test and hard to get wrong.
The types below are TypedDicts: labels for the reader and the editor, but still plain dicts at run time,
so a pending request can be saved as JSON (agent/state.py) and loaded back unchanged.
"""
import copy
from typing import Literal, NotRequired, TypedDict


class Action(TypedDict):
    """A checked action, as policy.plan returns it."""
    tool: str                    # "request_enrolment" or "cancel_enrolment"
    args: dict[str, str | int]   # the arguments the write will take
    rounds: list[list[str]]      # who approves each round, e.g. [["E1007"], ["E1068"]]
    summary: str                 # one line for humans: what exactly will happen
    note: str                    # an extra warning (e.g. the budget), or ""


class Pending(Action):
    """An action that is waiting for humans."""
    round: int                          # which round we are waiting on (0 = line manager)
    approved_by: list[str]              # who has said yes so far, in order
    idempotency_key: NotRequired[str]   # added by resume just before the write


class Asking(TypedDict):
    """What the CLI prints in `pending`: who may decide THIS round."""
    tool: str
    args: dict[str, str | int]
    approvers: list[str]
    summary: str


Outcome = Literal["ask", "execute", "closed"]
Decision = tuple[Outcome, Pending | None, str]

# What an approver may change with `modify` (API guide, "Editable by the approver").
EDITABLE: dict[str, set[str]] = {"request_enrolment": {"session_id"}, "cancel_enrolment": set()}


def open_request(action: Action) -> Pending:
    """Turn a checked action into a pending request, waiting on round 0."""
    return {**action, "round": 0, "approved_by": []}


def asking(pending: Pending) -> Asking:
    """Only this round's approvers: the line manager must say yes before the HR head is asked."""
    return {"tool": pending["tool"], "args": pending["args"],
            "approvers": pending["rounds"][pending["round"]], "summary": pending["summary"]}


def _closed(message: str) -> Decision:
    return "closed", None, message


def decide(pending: Pending, decision: str, by: str, edit: dict | None = None) -> Decision:
    """Apply one human decision. Returns (outcome, pending, message):

    "ask"      approved, and another round is needed: pending moves to the next round
    "execute"  every round approved: pending["approved_by"] holds the humans, in order
    "closed"   nothing will be written: pending is None
    """
    p = copy.deepcopy(pending)  # never change the saved request in place
    allowed_people = p["rounds"][p["round"]]

    # 1. Is this person allowed to decide this round? Checked first, for every decision.
    if by not in allowed_people:
        return _closed(f"{by} may not decide this step (it needed {', '.join(allowed_people)}), "
                       "so I did not go ahead. Nothing was booked or changed.")

    # 2. A reject ends everything.
    if decision == "reject":
        return _closed(f"{by} rejected the request to {p['summary']}. Nothing was booked or changed.")

    # 3. A modify may only change fields on the allowlist, and must change something.
    if decision == "modify":
        edit = edit or {}
        allowed_fields = EDITABLE[p["tool"]]
        forbidden_fields = set(edit) - allowed_fields
        if not edit or forbidden_fields:
            return _closed(f"{by} asked to change {sorted(edit)}, but only "
                           f"{sorted(allowed_fields) or 'nothing'} may be changed. Nothing was done.")
        p["args"].update(edit)  # the next round (and the re-check in resume) sees the edited args
    elif decision != "approve":
        return _closed(f"Unknown decision {decision!r}. Nothing was done.")

    # 4. Record the yes and move to the next round.
    p["approved_by"].append(by)
    p["round"] += 1
    if p["round"] < len(p["rounds"]):
        next_people = ", ".join(p["rounds"][p["round"]])
        return "ask", p, f"{by} approved. It also needs {next_people} to approve."
    return "execute", p, ""
