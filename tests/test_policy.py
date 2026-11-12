from helpers import FreshDB

from agent import policy

CLEARED = "INSERT INTO completions VALUES ('E1011', 'LD-108', '2026-10-05', 92)"  # E1011's overdue course, done


class TestPolicy(FreshDB):
    def refused(self, tool, args, actor):
        with self.assertRaises(policy.Refused) as ctx:
            policy.plan(tool, args, actor)
        return str(ctx.exception)

    # -- things that must never reach a human
    def test_mandatory_course_is_refused(self):
        msg = self.refused("request_enrolment", {"employee_id": "E1014", "course_id": "LD-106", "session_id": "LD-106-S1"}, "E1014")
        self.assertIn("HR books", msg)

    def test_overdue_mandatory_blocks_optional(self):
        msg = self.refused("request_enrolment", {"employee_id": "E1014", "course_id": "LD-109", "session_id": "LD-109-S1"}, "E1014")
        self.assertIn("MANDATORY_OVERDUE", msg)

    def test_retired_course_is_refused_even_with_a_session(self):
        msg = self.refused("request_enrolment", {"employee_id": "E1012", "course_id": "LD-105", "session_id": "LD-105-S1"}, "E1012")
        self.assertIn("RETIRED", msg)

    def test_missing_prerequisite_is_named(self):
        msg = self.refused("request_enrolment", {"employee_id": "E1012", "course_id": "LD-104", "session_id": "LD-104-S2"}, "E1012")
        self.assertIn("LD-101", msg)

    def test_full_session_is_refused_and_alternatives_offered(self):
        self.sql(CLEARED)
        msg = self.refused("request_enrolment", {"employee_id": "E1011", "course_id": "LD-104", "session_id": "LD-104-S1"}, "E1011")
        self.assertIn("full", msg)
        self.assertIn("LD-104-S2", msg)

    def test_session_of_another_course_is_refused(self):
        msg = self.refused("request_enrolment", {"employee_id": "E1012", "course_id": "LD-103", "session_id": "LD-110-S1"}, "E1012")
        self.assertIn("not an upcoming session", msg)

    def test_missing_argument_is_refused(self):
        self.assertIn("session_id", self.refused("request_enrolment", {"employee_id": "E1012", "course_id": "LD-103"}, "E1012"))

    # -- who must approve: always from PeopleHub, never invented
    def test_cheap_course_needs_the_line_manager_only(self):
        action = policy.plan("request_enrolment", {"employee_id": "E1012", "course_id": "LD-103", "session_id": "LD-103-S1"}, "E1012")
        self.assertEqual(action["rounds"], [["E1008"]])

    def test_expensive_course_needs_manager_then_hr_head(self):
        self.sql(CLEARED)
        action = policy.plan("request_enrolment", {"employee_id": "E1011", "course_id": "LD-104", "session_id": "LD-104-S2"}, "E1011")
        self.assertEqual(action["rounds"], [["E1007"], ["E1068"]])

    def test_when_the_manager_is_the_hr_head_one_round_is_enough(self):
        self.sql(CLEARED)
        self.sql("UPDATE employees SET manager_id='E1068' WHERE employee_id='E1011'")
        action = policy.plan("request_enrolment", {"employee_id": "E1011", "course_id": "LD-104", "session_id": "LD-104-S2"}, "E1011")
        self.assertEqual(action["rounds"], [["E1068"]])

    def test_extra_arguments_from_the_model_are_dropped(self):
        action = policy.plan("request_enrolment", {"employee_id": "E1012", "course_id": "LD-103",
                                                   "session_id": "LD-103-S1", "approved_by": "E1008"}, "E1012")
        self.assertEqual(set(action["args"]), {"employee_id", "course_id", "session_id"})

    # -- cancellations
    def test_cannot_cancel_a_booking_that_is_not_yours(self):
        self.assertIn("not one of your bookings", self.refused("cancel_enrolment", {"enrolment_id": 99}, "E1012"))

    def test_cancellation_goes_to_the_line_manager(self):
        self.sql("INSERT INTO enrolments (employee_id, course_id, session_id, status, approved_by, booked_on) "
                 "VALUES ('E1012', 'LD-103', 'LD-103-S1', 'booked', 'E1008', '2026-10-16')")
        action = policy.plan("cancel_enrolment", {"enrolment_id": "1"}, "E1012")
        self.assertEqual((action["args"], action["rounds"]), ({"enrolment_id": 1}, [["E1008"]]))
