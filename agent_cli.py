"""agent_cli.py — Root CLI entry point for PeopleHub Learning Coach Agent.

Maintains the exact command-line contract expected by harness/run_scenarios.py:
    python agent_cli.py start  --thread T --user U --message "text"
    python agent_cli.py say    --thread T --message "text" [--user U]
    python agent_cli.py resume --thread T --decision approve|reject|modify --by EMPLOYEE_ID [--edit '{"key": "value"}']

Delegates execution to the solution package in solution/agent_cli.py.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SOLUTION_DIR = ROOT_DIR / "solution"
PROVIDED_DIR = ROOT_DIR / "provided"

for p in [str(SOLUTION_DIR), str(PROVIDED_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from agent_cli import main

if __name__ == "__main__":
    main()
