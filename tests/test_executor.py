from helpers import FreshDB

from agent import executor
from peoplehub import core


def approved(by=("E1008",), rounds=(["E1008"],), key="k1"):
    return {"tool": "request_enrolment", "rounds": list(rounds), "approved_by": list(by), "round": len(rounds),
            "args": {"employee_id": "E1012", "course_id": "LD-103", "session_id": "LD-103-S1"},
            "idempotency_key": key}


class TestExecutor(FreshDB):
    def bookings(self):
        return self.sql("SELECT approved_by FROM enrolments WHERE status='booked'")

    def test_no_approval_no_call(self):
        with self.assertRaises(RuntimeError):
            executor.execute(approved(by=()), "E1012")
        self.assertEqual(self.audit("request_enrolment"), [])  # PeopleHub never even saw it

    def test_approval_from_the_wrong_round_is_not_enough(self):
        with self.assertRaises(RuntimeError):
            executor.execute(approved(by=("E1068", "E1007"), rounds=(["E1007"], ["E1068"])), "E1011")

    def test_books_once_with_the_human_in_approved_by(self):
        result = executor.execute(approved(), "E1012")
        self.assertTrue(result["ok"])
        self.assertEqual(self.bookings(), [{"approved_by": "E1008"}])

    # Part 16: type test_one_retry_with_the_same_key_after_a_temporary_failure here (see the guide).

    def test_gives_up_after_one_retry(self):
        core.add_fault("request_enrolment", times=5, path=self.db)
        result = executor.execute(approved(), "E1012")
        self.assertEqual((result["ok"], result["error"], result["attempts"]), (False, "ERR_UNAVAILABLE", 2))
        self.assertEqual(len(self.audit("request_enrolment")), 2)  # not 3, not 5
        self.assertEqual(self.bookings(), [])

    def test_a_refusal_is_not_retried(self):
        self.sql("UPDATE course_sessions SET held=capacity WHERE session_id='LD-103-S1'")  # now full
        result = executor.execute(approved(), "E1012")
        self.assertEqual((result["error"], result["attempts"]), ("ERR_SESSION_FULL", 1))

    def test_the_same_key_twice_books_once(self):
        executor.execute(approved(), "E1012")
        second = executor.execute(approved(), "E1012")
        self.assertTrue(second["result"].get("duplicate"))
        self.assertEqual(len(self.bookings()), 1)

    def test_keys_are_stable_and_distinct(self):
        args = {"employee_id": "E1012", "course_id": "LD-103", "session_id": "LD-103-S1"}
        k = executor.idempotency_key("T1", "request_enrolment", args, 0)
        self.assertEqual(k, executor.idempotency_key("T1", "request_enrolment", dict(reversed(args.items())), 0))
        self.assertNotEqual(k, executor.idempotency_key("T1", "request_enrolment", args, 1))
        self.assertNotEqual(k, executor.idempotency_key("T2", "request_enrolment", args, 0))
