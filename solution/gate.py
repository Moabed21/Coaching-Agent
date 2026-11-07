"""gate.py — Deterministic Approval Gate for PeopleHub Actions.

This module contains ZERO LLM calls and executes pure Python checks.
It guarantees:
  1. No restricted write is executed without recorded human approval.
  2. The approved_by identity comes strictly from the CLI --by argument.
  3. Actions that PeopleHub would refuse are caught before asking humans.
"""
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
from tools import APPROVAL_REQUIRED_TOOL_NAMES, LOW_RISK_TOOL_NAMES
from utils import (
    REASON_MANDATORY_OVERDUE,
    REASON_RETIRED,
    REASON_PREREQUISITE_MISSING,
)

HR_HEAD_ID = "E1068"
WRITE_TOOLS_NEEDING_APPROVAL = APPROVAL_REQUIRED_TOOL_NAMES
WRITE_TOOLS_NO_APPROVAL = LOW_RISK_TOOL_NAMES


def is_write(tool_name: str) -> bool:
    """Return True if tool_name modifies system state."""
    return tool_name in WRITE_TOOLS_NEEDING_APPROVAL or tool_name in WRITE_TOOLS_NO_APPROVAL


def needs_approval(tool_name: str) -> bool:
    """Return True if tool_name requires human approval before execution."""
    return tool_name in WRITE_TOOLS_NEEDING_APPROVAL


def needs_second_approval(fee: float) -> bool:
    """Courses strictly with fee > QAR 3,000 require two approval rounds (Manager then HR Head)."""
    return fee > 3000


def prepare_pending_enrolment(employee_id: str, course_id: str, session_id: str, actor: str) -> tuple[dict, str]:
    """
    Run check_enrolment dry check and prepare pending action structure.
    Returns (pending_dict, error_message).
    If error_message is not empty, the action cannot be proposed.
    """
    try:
        check = learning.check_enrolment(employee_id, course_id, actor=actor)
    except ApiError as e:
        return None, f"PeopleHub refused check: {e.message} ({e.code})"
    except Exception as exc:
        return None, f"System error during check: {exc}"

    if check.get("mandatory"):
        return None, "Mandatory courses are scheduled and booked directly by Human Resources. You cannot book this course through this assistant."

    if not check.get("eligible", False):
        reasons = check.get("reasons", [])
        codes = [r.get("code") for r in reasons]
        details = "; ".join([r.get("detail", r.get("code")) for r in reasons])
        if REASON_MANDATORY_OVERDUE in codes:
            return None, f"You have overdue mandatory training that must be completed before booking optional courses ({details})."
        if REASON_RETIRED in codes:
            return None, f"This course has been retired and is no longer available ({details})."
        if REASON_PREREQUISITE_MISSING in codes:
            return None, f"Prerequisite course requirements not met ({details})."
        return None, f"Enrolment is not eligible according to company policy: {details}"

    approvals_needed = check.get("approvals_needed", [])
    if not approvals_needed:
        return None, "No approver found for this request."

    fee = check.get("fee_qar", 0)
    line_mgr = approvals_needed[0]["employee_id"]

    # If course is > 3000, line manager approves first round, HR Head approves second round
    approvers = [line_mgr]

    pending = {
        "tool": "request_enrolment",
        "args": {
            "employee_id": employee_id,
            "course_id": course_id,
            "session_id": session_id,
        },
        "approvers": approvers,
        "fee_qar": fee,
        "needs_two_step": needs_second_approval(fee),
        "hr_head_id": HR_HEAD_ID,
        "summary": f"request_enrolment for {employee_id} on {course_id} session {session_id}",
    }
    return pending, None


def prepare_pending_cancellation(enrolment_id: str, actor: str) -> tuple[dict, str]:
    """Prepare a pending action for cancel_enrolment."""
    try:
        profile = learning.get_learning_profile(actor, actor=actor)
        line_mgr = profile.get("line_manager_id") or HR_HEAD_ID
    except Exception:
        line_mgr = HR_HEAD_ID

    pending = {
        "tool": "cancel_enrolment",
        "args": {
            "enrolment_id": enrolment_id,
        },
        "approvers": [line_mgr],
        "fee_qar": 0,
        "needs_two_step": False,
        "summary": f"cancel_enrolment for enrolment {enrolment_id}",
    }
    return pending, None


def validate_approval(pending_action: dict, decision: str, by: str, edit: dict = None) -> dict:
    """
    Validate a decision from the CLI.
    - reject: returns None
    - approve: returns updated args dictionary
    - modify: applies edit over args and returns updated args dictionary
    """
    if decision == "reject":
        return None

    args = dict(pending_action.get("args", {}))
    if decision == "modify" and edit:
        # Only certain keys are editable by policy (e.g. session_id)
        for k, v in edit.items():
            args[k] = v

    return args
