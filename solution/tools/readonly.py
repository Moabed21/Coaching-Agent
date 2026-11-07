"""tools/readonly.py — Read-only PeopleHub query tools.

These tools only query information and perform dry-checks.
They change nothing in the database and require no human approval.
"""
import sys
from pathlib import Path

# Ensure provided package is discoverable
for candidate in [
    Path(__file__).resolve().parent.parent / "provided",
    Path(__file__).resolve().parent.parent.parent / "provided",
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from peoplehub import directory, learning, ApiError

READ_TOOL_NAMES = {
    "find_employee",
    "get_today",
    "find_course",
    "get_learning_profile",
    "check_enrolment",
    "list_sessions",
}

READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_employee",
            "description": "Find an employee by English or Arabic name prefix. Returns at most 10 matches containing employee_id, full_name_en, job_title, department, location. Does not show learning data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name or prefix to search for (minimum 2 characters)."
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today",
            "description": "Get PeopleHub's current system date (always 2026-10-16). Never use host computer time.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_course",
            "description": "Find courses in the catalogue by course_id or title word prefixes. Returns at most 10 courses with course_id, title, status ('Active' or 'Retired'), fee_qar, and mandatory boolean.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Course title keywords or course ID (e.g. 'LD-110' or 'Incident Investigation')."
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_profile",
            "description": "Get employee learning profile: grade, line_manager_id, budget_year, annual_budget_qar, spent_this_year_qar, remaining_budget_qar, completed courses, overdue_mandatory courses, and current enrolments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID (e.g. 'E1014')."
                    }
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_enrolment",
            "description": "Dry check: verifies whether an employee is eligible for a course BEFORE asking for approval or booking. Returns title, eligible (bool), reasons (list of codes), fee_qar, mandatory (bool), and approvals_needed (list of required approver employee IDs). Changes nothing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID (e.g. 'E1055')."
                    },
                    "course_id": {
                        "type": "string",
                        "description": "Course ID (e.g. 'LD-110')."
                    }
                },
                "required": ["employee_id", "course_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sessions",
            "description": "Lists scheduled timetable sessions for a course starting on or after from_date (default today). Returns session_id, start_date, end_date, location, capacity, and seats_left. NOTE: Does not verify course status or eligibility; check seats_left before proposing a session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_id": {
                        "type": "string",
                        "description": "Course ID (e.g. 'LD-110')."
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Optional ISO start date filter (YYYY-MM-DD). Defaults to today."
                    }
                },
                "required": ["course_id"],
            },
        },
    },
]


def execute_read_tool(name: str, args: dict, actor: str) -> dict:
    """Execute a read tool in PeopleHub and return JSON-serializable result."""
    try:
        if name == "find_employee":
            return {"matches": directory.find_employee(args["query"], actor=actor)}
        elif name == "get_today":
            return directory.get_today(actor=actor)
        elif name == "find_course":
            return {"courses": learning.find_course(args["query"], actor=actor)}
        elif name == "get_learning_profile":
            return learning.get_learning_profile(args["employee_id"], actor=actor)
        elif name == "check_enrolment":
            return learning.check_enrolment(args["employee_id"], args["course_id"], actor=actor)
        elif name == "list_sessions":
            from_date = args.get("from_date")
            return {"sessions": learning.list_sessions(args["course_id"], from_date=from_date, actor=actor)}
        else:
            return {"error": f"Unknown read tool: {name}"}
    except ApiError as e:
        return {"error_code": e.code, "message": e.message, "retryable": e.retryable}
    except Exception as exc:
        return {"error": str(exc)}
