"""The approval gate: a small state machine. No model, no PeopleHub, no disk."""
import copy
from typing import Literal, TypedDict


class Action(TypedDict):
    """A checked action, as policy.plan returns it."""
    tool: str                    # "request_enrolment" or "cancel_enrolment"
    args: dict[str, str | int]
    rounds: list[list[str]]      # who approves each round, e.g. [["E1007"], ["E1068"]]
    summary: str
    note: str


class Pending(Action):
    """An action that is waiting for humans."""
    round: int                   # which round we are waiting on (0 = line manager)
    approved_by: list[str]       # who has said yes so far, in order


Outcome = Literal["ask", "execute", "closed"]
Decision = tuple[Outcome, Pending | None, str]

# What an approver may change with `modify` (API guide, "Editable by the approver").
EDITABLE: dict[str, set[str]] = {"request_enrolment": {"session_id"}, "cancel_enrolment": set()}


def open_request(action: Action) -> Pending:
    return {**action, "round": 0, "approved_by": []}


def asking(pending: Pending) -> dict:
    """Who may decide THIS round only (manager first, then HR head)."""
    return {"tool": pending["tool"], "args": pending["args"],
            "approvers": pending["rounds"][pending["round"]], "summary": pending["summary"]}


def _closed(message: str) -> Decision:
    return "closed", None, message


def decide(pending: Pending, decision: str, by: str, edit: dict | None = None) -> Decision:
    p = copy.deepcopy(pending)              # never change the saved request in place
    allowed_people = p["rounds"][p["round"]]

    # 1. Is this person allowed to decide this round?
    if by not in allowed_people:
        return _closed(f"{by} may not decide this step (it needed {', '.join(allowed_people)}). "
                       "Nothing was booked or changed.")

    # 2. Reject ends everything.
    if decision == "reject":
        return _closed(f"{by} rejected the request to {p['summary']}. Nothing was booked or changed.")

    # 3. Modify: only fields on the allowlist, and the edit must not be empty.
    if decision == "modify":
        edit = edit or {}
        allowed_fields = EDITABLE[p["tool"]]
        forbidden_fields = set(edit) - allowed_fields
        if not edit or forbidden_fields:
            return _closed(f"{by} asked to change {sorted(edit)}, but only "
                           f"{sorted(allowed_fields) or 'nothing'} may be changed. Nothing was done.")
        p["args"].update(edit)
    elif decision != "approve":
        return _closed(f"Unknown decision {decision!r}. Nothing was done.")

    # 4. Record the yes and move to the next round.
    p["approved_by"].append(by)
    p["round"] += 1
    if p["round"] < len(p["rounds"]):
        next_people = ", ".join(p["rounds"][p["round"]])
        return "ask", p, f"{by} approved. It also needs {next_people} to approve."
    return "execute", p, ""
