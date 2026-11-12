"""Learning Coach agent: an enrolment assistant on top of PeopleHub.

Who does what (read top to bottom, this is also the order a request flows):

    agent_cli.py   one command in, ONE JSON object out. Every command is a new process.
    loop.py        the model <-> tools loop. The model only ever *asks*.
    tools.py       which tool may do what: read, low-risk write, or proposal.
    policy.py      the business rules we check BEFORE asking a human.
    approval.py    the approval gate: a small state machine. No model, no disk.
    executor.py    the ONLY place an enrolment is written. Idempotency + one retry.
    state.py       the conversation on disk: the only memory between two commands.

    schemas.py, prompt.py, llm.py   what the model sees, and where the model comes from.
"""
