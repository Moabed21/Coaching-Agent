from helpers import FreshDB

from agent import tools


class TestTools(FreshDB):
    def test_every_tool_is_in_exactly_one_class(self):
        reads, low, props = set(tools.READS), set(tools.LOW_RISK), tools.PROPOSALS
        self.assertFalse(reads & low or reads & props or low & props)

    def test_proposals_have_no_function_to_call(self):
        self.assertIsInstance(tools.PROPOSALS, set)  # names only: nothing here can write

    def test_model_cannot_set_who_we_act_for(self):
        self.assertEqual(tools.clean({"employee_id": "E1012", "actor": "E1068", "approved_by": "E1068"}),
                         {"employee_id": "E1012"})

    def test_a_refusal_becomes_a_message_not_a_crash(self):
        # E1012 may not see E1014's learning record
        reply = tools.call(tools.READS["get_learning_profile"], {"employee_id": "E1014"}, actor="E1012")
        self.assertEqual((reply["ok"], reply["error"], reply["retryable"]), (False, "ERR_FORBIDDEN", False))

    def test_bad_arguments_become_a_message(self):
        reply = tools.call(tools.READS["find_course"], {"title": "risk"}, actor="E1012")
        self.assertEqual(reply["error"], "BAD_ARGUMENTS")
