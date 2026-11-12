"""The rules we check BEFORE we ask a human. No model calls in this file.

PeopleHub checks everything again when we write. This file exists so we never ask a
person to approve something the system will refuse, and never make a call it has to refuse.
"""
from peoplehub import ApiError, directory, learning

from .approval import Action

REQUIRED = {
    "request_enrolment": ["employee_id", "course_id", "session_id"],
    "cancel_enrolment": ["enrolment_id",]
}


class Refused(Exception):
    """The action is not allowed. str(error) is an honest explanation for the user."""


def _cancellation(enrolment_id, actor):
    try:
        enrolment_id = int(enrolment_id)
    except (TypeError, ValueError):
        raise Refused(f"{enrolment_id!r} is not an enrolment id; they are numbers from get_learning_profile.")
    profile = learning.get_learning_profile(actor, actor=actor)
    booking = next((e for e in profile["enrolments"] if e["enrolment_id"] == enrolment_id), None)
    if booking is None:
        raise Refused(f"Enrolment {enrolment_id} is not one of your bookings.")
    if booking["status"] != "booked":
        raise Refused(f"Enrolment {enrolment_id} is already {booking['status']}.")
    if booking["start_date"] <= directory.get_today(actor=actor)["today"]:
        raise Refused(f"Session {booking['session_id']} has already started, so it can no longer be cancelled.")
    # The cancel approver is the line manager (or the HR head if there is none): exactly the first
    # approver PeopleHub names for this course. We ask the system of record instead of hard-coding an id.
    first = learning.check_enrolment(actor, booking["course_id"], actor=actor)["approvals_needed"][0]
    return {"tool": "cancel_enrolment", "rounds": [[first["employee_id"]]], "note": "",
            "args": {"enrolment_id": enrolment_id},
            "summary": f"cancel enrolment {enrolment_id} ({booking['course_id']} {booking['title']}, "
                       f"session {booking['session_id']})"}


def _budget_note(employee_id, fee, actor):
    """PeopleHub only counts COMPLETED courses against the budget, so it accepts two bookings that
    together go over it. The system will not warn about that; a careful agent does."""
    profile = learning.get_learning_profile(employee_id, actor=actor)
    booked = [e["course_id"] for e in profile["enrolments"] if e["status"] == "booked"]
    held = sum(learning.find_course(c, actor=actor)["courses"][0]["fee_qar"] for c in booked)
    if held and held + fee > profile["remaining_budget_qar"]:
        return (f"Note: with your other bookings (QAR {held:,}) this would go over your remaining "
                f"budget of QAR {profile['remaining_budget_qar']:,}.")
    return ""


def _enrolment(employee_id, course_id, session_id, actor):
    check = learning.check_enrolment(employee_id, course_id, actor=actor)
    if check["mandatory"]:
        raise Refused(f"{course_id} is a mandatory course. HR books mandatory courses; I cannot book it.")
    if not check["eligible"]:
        raise Refused("Not eligible: " + "; ".join(f"{r['code']} ({r['detail']})" for r in check["reasons"]))

    sessions = learning.list_sessions(course_id, actor=actor)["sessions"]
    with_seats = [s["session_id"] for s in sessions if s["seats_left"] > 0]
    chosen = next((s for s in sessions if s["session_id"] == session_id), None)
    if chosen is None:
        raise Refused(f"{session_id} is not an upcoming session of {course_id}. Sessions with seats: {with_seats or 'none'}.")
    if chosen["seats_left"] <= 0:
        raise Refused(f"{session_id} is full. Sessions of {course_id} with seats: {with_seats or 'none'}.")

    rounds = [[a["employee_id"]] for a in check["approvals_needed"]]  # line manager first, then HR head
    summary = (f"book {employee_id} on {course_id} {check['title']}, session {session_id} "
               f"starting {chosen['start_date']}, fee QAR {check['fee_qar']:,}")
    return {"tool": "request_enrolment", "rounds": rounds, "summary": summary,
            "args": {"employee_id": employee_id, "course_id": course_id, "session_id": session_id},
            "note": _budget_note(employee_id, check["fee_qar"], actor)}


def plan(tool: str, args: dict, actor: str) -> Action:
    """Check a proposed action and work out who must approve it.

    Returns the action as a dict: tool, args, rounds (one list of approver ids per round), summary.
    Raises Refused when the action must not go to a human at all.
    """
    if tool not in REQUIRED:
        raise Refused(f"{tool} is not an action this assistant can propose.")
    missing = [k for k in REQUIRED[tool] if args.get(k) in (None, "")]
    if missing:
        raise Refused(f"{tool} needs {', '.join(missing)}.")
    args = {k: args[k] for k in REQUIRED[tool]}  # keep only the arguments the write takes
    try:
        if tool == "request_enrolment":
            return _enrolment(actor=actor, **args)
        return _cancellation(actor=actor, **args)
    except ApiError as e:
        raise Refused(f"PeopleHub could not check this ({e.code}): {e.message}")
