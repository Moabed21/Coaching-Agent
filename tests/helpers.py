"""Shared test plumbing: a fresh PeopleHub database for every test, and a fake model.

Run every test from the repository root:   python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # agent/ and peoplehub/ live in the repository root

from peoplehub import core, learning  # noqa: E402


class FreshDB(unittest.TestCase):
    """Each test gets its own PeopleHub database and its own empty state folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "peoplehub.db")
        core.build_db(self.db, learning)
        os.environ["PEOPLEHUB_DB"] = self.db
        os.environ["AGENT_STATE_DIR"] = os.path.join(self.tmp.name, "state")

    def tearDown(self):
        self.tmp.cleanup()

    def sql(self, statement, params=()):
        conn = core.connect(self.db)
        rows = [dict(r) for r in conn.execute(statement, params).fetchall()]
        conn.commit()
        conn.close()
        return rows

    def audit(self, function=None):
        rows = self.sql("SELECT function, outcome, error_code, approved_by FROM audit_log ORDER BY seq")
        return [r for r in rows if function is None or r["function"] == function]


# ------------------------------------------------------------------ a fake model for the loop tests
def tool_call(call_id, name, **args):
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def says(text):
    """A model message with an answer and no tool calls."""
    return SimpleNamespace(content=text, tool_calls=None)


def calls(*tool_calls):
    """A model message that asks for one or more tools."""
    return SimpleNamespace(content=None, tool_calls=list(tool_calls))


class FakeModel:
    """Plays a script of model messages and records every conversation it was sent."""

    def __init__(self, *script):
        self.script, self.seen = list(script), []

    def __call__(self, messages, tools):
        self.seen.append(json.loads(json.dumps(messages)))
        return self.script.pop(0) if self.script else says("(script finished)")


def assert_valid_history(test, messages):
    """The rule the real model API enforces: every tool call is answered by exactly one tool reply,
    right after the assistant message that made it."""
    i = 0
    while i < len(messages):
        m = messages[i]
        ids = [c["id"] for c in m.get("tool_calls") or []]
        if ids:
            replies = [r["tool_call_id"] for r in messages[i + 1:i + 1 + len(ids)] if r.get("role") == "tool"]
            test.assertEqual(sorted(replies), sorted(ids), f"tool calls without a reply after message {i}")
            i += len(ids)
        i += 1
