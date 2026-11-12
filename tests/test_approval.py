import unittest

import helpers  # noqa: F401  (sets up the import path)
from agent import approval

ARGS = {"employee_id": "E1011", "course_id": "LD-104", "session_id": "LD-104-S2"}


def pending(rounds, tool="request_enrolment", args=ARGS):
    return approval.open_request({"tool": tool, "args": dict(args), "rounds": rounds, "summary": "s", "note": ""})


class TestApprovalGate(unittest.TestCase):
    def test_one_round_approve_is_ready_to_execute(self):
        outcome, p, _ = approval.decide(pending([["E1008"]]), "approve", "E1008")
        self.assertEqual((outcome, p["approved_by"]), ("execute", ["E1008"]))

    def test_reject_closes_and_keeps_nothing(self):
        outcome, p, msg = approval.decide(pending([["E1008"]]), "reject", "E1008")
        self.assertEqual((outcome, p), ("closed", None))
        self.assertIn("Nothing was booked", msg)

    def test_someone_not_asked_cannot_approve(self):
        outcome, _, _ = approval.decide(pending([["E1008"]]), "approve", "E1068")
        self.assertEqual(outcome, "closed")

    def test_two_rounds_in_order(self):
        p0 = pending([["E1007"], ["E1068"]])
        outcome, p1, _ = approval.decide(p0, "approve", "E1007")
        self.assertEqual((outcome, approval.asking(p1)["approvers"]), ("ask", ["E1068"]))
        outcome, p2, _ = approval.decide(p1, "approve", "E1068")
        self.assertEqual((outcome, p2["approved_by"]), ("execute", ["E1007", "E1068"]))

    def test_hr_head_cannot_jump_the_queue(self):
        outcome, _, _ = approval.decide(pending([["E1007"], ["E1068"]]), "approve", "E1068")
        self.assertEqual(outcome, "closed")

    def test_modify_session_is_carried_into_round_two(self):
        _, p1, _ = approval.decide(pending([["E1007"], ["E1068"]]), "modify", "E1007", {"session_id": "LD-104-S3"})
        self.assertEqual(approval.asking(p1)["args"]["session_id"], "LD-104-S3")

    def test_modify_cannot_change_who_or_which_course(self):
        outcome, _, _ = approval.decide(pending([["E1008"]]), "modify", "E1008", {"employee_id": "E1999"})
        self.assertEqual(outcome, "closed")

    def test_a_cancellation_cannot_be_modified(self):
        p = pending([["E1008"]], tool="cancel_enrolment", args={"enrolment_id": 1})
        self.assertEqual(approval.decide(p, "modify", "E1008", {"enrolment_id": 2})[0], "closed")

    def test_the_saved_request_is_never_changed_in_place(self):
        p0 = pending([["E1007"], ["E1068"]])
        approval.decide(p0, "approve", "E1007")
        self.assertEqual((p0["round"], p0["approved_by"]), (0, []))
