"""The loop, tested with a fake model: no network, no key, same result every time."""
from helpers import FakeModel, FreshDB, assert_valid_history, calls, says, tool_call

from agent import loop

BOOK = {"employee_id": "E1012", "course_id": "LD-103", "session_id": "LD-103-S1"}


class TestLoop(FreshDB):
    def run_with(self, model, actor="E1012"):
        messages = [{"role": "user", "content": "hi"}]
        out = loop.run(messages, actor, "T1", model)
        assert_valid_history(self, messages)  # whatever happened, the history must stay valid
        return out, messages

    def test_reads_run_and_the_answer_comes_back(self):
        out, messages = self.run_with(FakeModel(calls(tool_call("c1", "get_today")), says("It is Friday.")))
        self.assertEqual(out, {"answer": "It is Friday."})
        self.assertIn("2026-10-16", messages[2]["content"])

    def test_a_proposal_stops_the_loop_and_writes_nothing(self):
        out, _ = self.run_with(FakeModel(calls(tool_call("c1", "request_enrolment", **BOOK))))
        self.assertEqual(out["proposal"]["rounds"], [["E1008"]])
        self.assertEqual(self.sql("SELECT * FROM enrolments"), [])
        self.assertEqual(self.audit("request_enrolment"), [])

    # Part 18: type test_every_call_is_answered_even_with_two_proposals_in_one_turn here (see the guide).

    def test_a_refused_proposal_goes_back_to_the_model(self):
        retired = {"employee_id": "E1012", "course_id": "LD-105", "session_id": "LD-105-S1"}
        model = FakeModel(calls(tool_call("c1", "request_enrolment", **retired)), says("It is retired."))
        out, messages = self.run_with(model)
        self.assertEqual(out, {"answer": "It is retired."})
        self.assertIn("RETIRED", messages[2]["content"])

    def test_the_model_cannot_choose_who_we_act_for(self):
        # E1012 may not read E1014's record; the model tries to pretend to be E1014
        model = FakeModel(calls(tool_call("c1", "get_learning_profile", employee_id="E1014", actor="E1014")), says("ok"))
        _, messages = self.run_with(model)
        self.assertIn("ERR_FORBIDDEN", messages[2]["content"])

    def test_the_loop_has_an_end(self):
        model = FakeModel(*[calls(tool_call(f"c{i}", "get_today")) for i in range(20)])
        out, _ = self.run_with(model)
        self.assertEqual(len(model.seen), loop.MAX_MODEL_CALLS)
        self.assertIn("Nothing was booked", out["answer"])
