"""What the model sees: one JSON schema per tool.

A tool description is part of the prompt. Say what the tool does, and just as important,
when NOT to use it. The schema only tells the model what it may ASK for; nothing here runs.
"""


def _tool(name, description, properties=None, required=()):
    return {"type": "function", "function": {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": list(required)},
    }}


_EMP = {"type": "string", "description": "Employee id, for example E1055."}
_COURSE = {"type": "string", "description": "Course id, for example LD-110."}

READ_SCHEMAS = [
    _tool("find_employee",
          "Find people by (part of) their English or Arabic name. Returns ids, job titles and departments. "
          "Use it to turn a name into an employee id. Shows no learning data.",
          {"query": {"type": "string", "description": "Name or part of a name, at least 2 characters."}},
          ["query"]),
    _tool("get_today",
          "PeopleHub's date and working week. Use it for anything relative ('next month', 'in November'). "
          "Never use your own idea of today's date."),
    _tool("find_course",
          "Find courses by course id or by words from the title (each word must start a title word: "
          "'risk assessment' works, 'safety course' may not). Returns id, title, status (Active/Retired), "
          "fee and whether it is mandatory. Retired courses are listed too: they cannot be booked.",
          {"query": {"type": "string", "description": "A course id, or one or more words from the title."}},
          ["query"]),
    _tool("get_learning_profile",
          "An employee's grade, line manager, budget for the year (annual, spent, remaining), completed "
          "courses, overdue mandatory courses and their bookings (with enrolment ids, needed to cancel).",
          {"employee_id": _EMP}, ["employee_id"]),
    _tool("check_enrolment",
          "Dry run: would PeopleHub allow this employee to book this course? Returns eligible, every reason "
          "it is not, the fee, whether it is mandatory, and who must approve. Changes nothing. "
          "Always call it before proposing a booking.",
          {"employee_id": _EMP, "course_id": _COURSE}, ["employee_id", "course_id"]),
    _tool("list_sessions",
          "Upcoming sessions of a course with dates and seats_left. It shows the timetable only: it does NOT "
          "check whether the course is retired or whether anyone is eligible. Pick a session with seats_left > 0.",
          {"course_id": _COURSE,
           "from_date": {"type": "string", "description": "Optional ISO date (YYYY-MM-DD); default today."}},
          ["course_id"]),
]

LOW_RISK_SCHEMAS = [
    _tool("save_learning_plan",
          "Save a DRAFT learning plan (free text) for the employee. Low risk: it books nothing and needs no "
          "approval, so save it directly when asked. Put in it only courses you have checked.",
          {"employee_id": _EMP, "plan_text": {"type": "string", "description": "The plan, in plain text."}},
          ["employee_id", "plan_text"]),
]

PROPOSAL_SCHEMAS = [
    _tool("request_enrolment",
          "PROPOSE booking an employee on one session of a course. This does NOT book anything: it sends the "
          "request to the people who must approve it, and the system works out who they are. Call it once "
          "check_enrolment says eligible and you have picked a session with seats. Never for a mandatory course.",
          {"employee_id": _EMP, "course_id": _COURSE,
           "session_id": {"type": "string", "description": "Session id from list_sessions, for example LD-110-S1."}},
          ["employee_id", "course_id", "session_id"]),
    _tool("cancel_enrolment",
          "PROPOSE cancelling one of the employee's bookings. This does NOT cancel anything: it sends the request "
          "to the line manager. The enrolment id comes from get_learning_profile.",
          {"enrolment_id": {"type": "integer", "description": "Enrolment id from get_learning_profile."}},
          ["enrolment_id"]),
]

TOOLS = READ_SCHEMAS + LOW_RISK_SCHEMAS + PROPOSAL_SCHEMAS
