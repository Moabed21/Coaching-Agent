# Phase 2: Learning Coach Agent (Agent Bank ID 33)

**Start with `02_Phase2_Brief_Learning_Coach_Agent.pdf`.** It explains the task, the levels and how it will be judged.

1. `docs/LRN_API.md`: the API guide for your track (read it second).
2. `harness/README.md`: the command-line contract your agent must follow (read it third, before you code).
3. `peoplehub/`: the mock HR system. `scenarios/`: the public scenarios. `templates/`: starting points.

Quick start, from this folder (Python 3.10 or newer):

```
cp templates/agent_cli_template.py agent_cli.py
python3 harness/run_scenarios.py --track learning --agent "python3 agent_cli.py" --scenarios scenarios/learning_public.jsonl
```

At first everything fails with a message telling you what is missing: that is the starting line.

**Model access.** Ask your mentors for the three values in `.env.example` (an Azure OpenAI endpoint, a key, and the name of a deployment that supports tool calling). Copy it to `.env`, fill it in, run `pip install openai` and `python3 tools/check_model.py`. Never commit `.env`.

**Before every commit** run `python3 tools/precommit_check.py` (inside a git repository: `git init` first if you have not).

To try the API by hand: `python3 -m peoplehub.build_db learning peoplehub.db` then `export PEOPLEHUB_DB=peoplehub.db`. All people, records and numbers are fictional.
