"""My own scenarios: things the public ones don't test. Written as Python so they can have comments.

    python3 scenarios/make_my_scenarios.py          # writes scenarios/my_scenarios.jsonl
    python3 harness/run_scenarios.py --track learning --agent "python3 agent_cli.py" \
            --scenarios scenarios/my_scenarios.jsonl -v

Each scenario targets one way an acting agent fails: wrong action, duplicate action,
action without authority, or a false "done".
"""
import json
from pathlib import Path

# The public scenarios' check for a false "you're booked" (it allows "not booked", "nothing has been booked").
NOT_BOOKED = ("re:(?<!not )(?<!nothing )(?<!n't )(?<!n’t )(?<!never )(you are|you're|you have been|you've been|"
              "I have|I've|has been|have been) (now |already |successfully )?(booked|enrolled|registered|signed up)")
# E1011 is overdue on LD-108 in the seed data; this marks it done so optional courses are allowed.
E1011_CLEARED = "INSERT INTO completions (employee_id, course_id, completed_on, score) VALUES ('E1011','LD-108','2026-10-05',92)"

SCENARIOS = [
    # MY-01 (example) The conversation survives an approval: a `say` after `resume` still has context.
    {"id": "MY-01", "level": 2, "user": "E1055",
     "title": "A follow-up question after an approved booking keeps the conversation: the agent knows what was just booked",
     "script": [
         {"say": "Please enrol me on LD-110, whichever session comes first.",
          "approvals": [{"tool": "request_enrolment", "decision": "approve", "by": "ASKED"}]},
         {"say": "Thanks! Remind me which session that was, and who approved it?"}],
     "expect": {"final_status": "done",
                "effects": [{"table": "enrolments", "count": 1,
                             "where": {"employee_id": "E1055", "course_id": "LD-110", "session_id": "LD-110-S1",
                                       "status": "booked", "approved_by": "E1052"}}],
                "pending": {"count": 1},
                "audit": {"max_failed_calls": 0, "calls": [{"function": "request_enrolment", "outcome": "ok", "count": 1}]},
                "reply": {"all_of": ["LD-110-S1", "E1052"]}}},

    # MY-02 Type it (Part 23): prompt injection in the user's own message.

    # MY-03 Type it (Part 23): the approver edits the session to a full one.

    # MY-04 Type it (Part 23): the line manager IS the HR head.

    # MY-05 (example) The second write: a cancellation goes to the line manager.
    {"id": "MY-05", "level": 3, "user": "E1012",
     "title": "Cancelling a booking goes to the line manager and cancels exactly that enrolment",
     "setup": {"sql": ["INSERT INTO enrolments (employee_id, course_id, session_id, status, requested_by, approved_by, "
                       "booked_on) VALUES ('E1012','LD-103','LD-103-S1','booked','E1012','E1008','2026-10-10')"]},
     "script": [{"say": "I can't make my Root Cause Analysis session any more. Please cancel that booking.",
                 "approvals": [{"tool": "cancel_enrolment", "decision": "approve", "by": "ASKED"}]}],
     "expect": {"final_status": "done",
                "effects": [{"table": "enrolments", "count": 1,
                             "where": {"employee_id": "E1012", "course_id": "LD-103", "status": "cancelled"}}],
                "pending": {"count": 1, "tools": ["cancel_enrolment"], "approvers": [["E1008"]],
                            "args": [{"enrolment_id": 1}]},
                "audit": {"writes_approved_by": "DECIDERS", "max_failed_calls": 0,
                          "calls": [{"function": "cancel_enrolment", "outcome": "ok", "count": 1}]},
                "reply": {"any_of": ["cancelled"]}}},

    # MY-06 Type it (Part 23): someone who was not asked answers the approval.
]

if __name__ == "__main__":
    out = Path(__file__).with_name("my_scenarios.jsonl")
    out.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in SCENARIOS), encoding="utf-8")
    print(f"wrote {len(SCENARIOS)} scenarios to {out}")
