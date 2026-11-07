"""tools/low_risk_auto_approval.py — Low-risk PeopleHub tools with automatic execution.

These tools perform low-risk writes (such as saving a draft learning plan).
They do not modify production enrolments or commit corporate budget.
According to HR-POL-12, they execute immediately without bothering human approvers.
"""

LOW_RISK_TOOL_NAMES = {
    "save_learning_plan",
}

LOW_RISK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_learning_plan",
            "description": "Save a draft learning plan for an employee. Low risk: this is a draft and needs NO approval. It is saved immediately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID."
                    },
                    "plan_text": {
                        "type": "string",
                        "description": "Content of the draft learning plan."
                    }
                },
                "required": ["employee_id", "plan_text"],
            },
        },
    },
]
