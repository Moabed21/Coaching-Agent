"""tools/approval_required.py — PeopleHub tools that strictly require human approval.

The model is NEVER allowed to execute these directly.
Calls to these tools are intercepted by gate.py and turned into pending approval requests.
"""

APPROVAL_REQUIRED_TOOL_NAMES = {
    "request_enrolment",
    "cancel_enrolment",
}

APPROVAL_REQUIRED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "request_enrolment",
            "description": "Propose booking an employee onto a course session. DO NOT call this directly for mandatory courses (HR books those). Requires human approval before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID to enrol."
                    },
                    "course_id": {
                        "type": "string",
                        "description": "Course ID."
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID (must have seats_left > 0)."
                    }
                },
                "required": ["employee_id", "course_id", "session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_enrolment",
            "description": "Propose cancelling an existing booking. Requires line manager approval. Enrolment ID must come from get_learning_profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enrolment_id": {
                        "type": "string",
                        "description": "Enrolment ID to cancel."
                    }
                },
                "required": ["enrolment_id"],
            },
        },
    },
]
