"""test_gate.py — Unit tests for the deterministic approval gate (gate.py).

Verifies that:
  - Write classification and approval needs are strictly enforced
  - Course fee threshold (> QAR 3,000) for two-step approvals is exact
  - Human decisions (approve, reject, modify) behave deterministically
"""
import sys
import unittest
from pathlib import Path

CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))
for candidate in [
    CURR_DIR / "provided",
    CURR_DIR.parent / "provided",
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from gate import is_write, needs_approval, needs_second_approval, validate_approval


class TestGate(unittest.TestCase):

    def test_write_tools_classification(self):
        self.assertTrue(is_write("request_enrolment"))
        self.assertTrue(is_write("cancel_enrolment"))
        self.assertTrue(is_write("save_learning_plan"))
        self.assertFalse(is_write("find_course"))
        self.assertFalse(is_write("get_learning_profile"))
        self.assertFalse(is_write("check_enrolment"))
        self.assertFalse(is_write("list_sessions"))

    def test_approval_requirement(self):
        # request_enrolment and cancel_enrolment MUST require human approval
        self.assertTrue(needs_approval("request_enrolment"))
        self.assertTrue(needs_approval("cancel_enrolment"))

        # save_learning_plan is low-risk draft and MUST NOT require human approval
        self.assertFalse(needs_approval("save_learning_plan"))
        self.assertFalse(needs_approval("find_course"))

    def test_two_step_fee_threshold(self):
        # Policy rule: Fee strictly ABOVE QAR 3,000 requires line manager AND HR Head
        self.assertFalse(needs_second_approval(0))
        self.assertFalse(needs_second_approval(1200))
        self.assertFalse(needs_second_approval(2500))
        self.assertFalse(needs_second_approval(3000))  # Exactly 3,000 is NOT above
        self.assertTrue(needs_second_approval(3001))
        self.assertTrue(needs_second_approval(4200))

    def test_validate_approval_decision(self):
        pending = {
            "tool": "request_enrolment",
            "args": {
                "employee_id": "E1055",
                "course_id": "LD-110",
                "session_id": "LD-110-S1",
            },
        }

        # Approve returns args unchanged
        approved_args = validate_approval(pending, "approve", "E1052")
        self.assertEqual(approved_args["session_id"], "LD-110-S1")
        self.assertEqual(approved_args["employee_id"], "E1055")

        # Reject returns None
        rejected = validate_approval(pending, "reject", "E1052")
        self.assertIsNone(rejected)

        # Modify merges edit onto args
        modified_args = validate_approval(pending, "modify", "E1052", edit={"session_id": "LD-110-S2"})
        self.assertEqual(modified_args["session_id"], "LD-110-S2")
        self.assertEqual(modified_args["employee_id"], "E1055")
        self.assertEqual(modified_args["course_id"], "LD-110")


if __name__ == "__main__":
    unittest.main()
