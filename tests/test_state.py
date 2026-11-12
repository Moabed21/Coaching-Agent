import os

from helpers import FreshDB

from agent import state


class TestState(FreshDB):
    def test_what_is_saved_comes_back(self):
        st = state.new("E1012")
        st["messages"].append({"role": "user", "content": "مرحبا"})
        state.save("T1", st)
        self.assertEqual(state.load("T1"), st)

    def test_unknown_thread_is_none(self):
        self.assertIsNone(state.load("never-started"))

    def test_no_temporary_file_is_left_behind(self):
        state.save("T1", state.new("E1012"))
        self.assertEqual(os.listdir(os.environ["AGENT_STATE_DIR"]), ["T1.json"])

    def test_a_thread_id_cannot_escape_the_folder(self):
        for bad in ("../x", "a/b", ".hidden", ""):
            with self.assertRaises(ValueError):
                state.load(bad)
