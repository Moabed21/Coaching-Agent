# Learning Coach Agent (Agent Bank ID 33)

An enrolment assistant for the fictional Al Dana Group. An employee asks for a course in plain words; the agent looks
things up in PeopleHub, checks the rules, and proposes the booking. **Nothing is written until the right humans approve
it**, and the approver's id comes only from the approval command, never from the model.

The brief is `02_Phase2_Brief_Learning_Coach_Agent.pdf`, the API is `docs/LRN_API.md`, and the command-line contract
is `harness/README.md`.

## Run it from a fresh clone

Python 3.10 or newer.

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in the three Azure OpenAI values (ask the mentors); never commit .env
python3 tools/check_model.py  # the model answers and can call a tool
python3 -m unittest discover -s tests -v
python3 harness/run_scenarios.py --track learning --agent "python3 agent_cli.py" --scenarios scenarios/learning_public.jsonl -v
python3 scenarios/make_my_scenarios.py
python3 harness/run_scenarios.py --track learning --agent "python3 agent_cli.py" --scenarios scenarios/my_scenarios.jsonl -v
```

Add `--repeat 3` to check that a scenario passes every time, and `--keep` to keep each run's database and state.

## How it works

```
agent_cli.py        start / say / resume -> exactly one JSON object on stdout
agent/loop.py       model <-> tools loop; the model only proposes
agent/tools.py      reads (run freely), low-risk writes (run, no approval), proposals (never run here)
agent/policy.py     checks a proposal BEFORE any human is asked; approvers come from check_enrolment
agent/approval.py   the approval gate: a pure state machine (approve / reject / modify, one or two rounds)
agent/executor.py   the only place an enrolment is booked or cancelled: idempotency key, one retry
agent/state.py      one JSON file per thread in $AGENT_STATE_DIR, saved atomically
```

A request flows like this. `start` runs the loop. Read tools run straight away. A proposal (`request_enrolment`,
`cancel_enrolment`) is checked by `policy.plan`. If PeopleHub would refuse it, the model is told why and explains it to
the user. If it would be allowed, the agent saves the pending request and answers `awaiting_approval`. `resume`
applies the human's decision in `approval.decide`, checks the action again, and only when every round is approved does
`executor.execute` call PeopleHub, with `approved_by` taken from the `--by` values.

The data passed between modules is typed with `TypedDict` (`Action`, `Pending`, `WriteResult`, `State`): the
types document the shape for readers and editors, but stay plain dicts at run time, so state files are plain JSON.
The one retry is a decorator (`@retry_once_if_temporary` in `agent/executor.py`), and the CLI commands register
with `@command` in `agent_cli.py`.

Decisions and their reasons are in `notes/decision_log.md`; results are in `notes/results_note.md`.

Run `python3 tools/precommit_check.py` before every commit.
