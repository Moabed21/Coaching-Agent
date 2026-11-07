import json
import os
import sys
from pathlib import Path
from openai import OpenAI

# Ensure solution directory and provided package are discoverable
CURR_DIR = Path(__file__).resolve().parent
if str(CURR_DIR) not in sys.path:
    sys.path.insert(0, str(CURR_DIR))
for candidate in [
    CURR_DIR / "provided",
    CURR_DIR.parent / "provided",
]:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from peoplehub import learning, directory, ApiError
from tools import TOOLS, execute_read_tool
from gate import is_write, needs_approval, prepare_pending_enrolment, prepare_pending_cancellation
from utils import get_openai_client

SYSTEM_PROMPT = """You are the Learning Coach Enrolment Assistant for Al Dana Group (HR System: PeopleHub).
Your job is to help employees look up their learning history, catalogue courses, check eligibility, and prepare enrolments or draft learning plans.

RULES YOU MUST STRICTLY FOLLOW:
1. PeopleHub's date is always obtained via `get_today()`. Never use your computer's clock.
2. Privacy: Every function requires `actor`, which is the employee talking to you. You act on their behalf.
3. Mandatory courses: Mandatory courses (catalogue `mandatory` is True) are booked and scheduled directly by Human Resources. You must NEVER propose or request an enrolment for a mandatory course. Clearly inform the user that HR books mandatory courses.
4. Overdue mandatory training: When an employee has overdue mandatory courses, company policy (HR-POL-12) strictly blocks them from enrolling in any optional courses. Always check their profile or run `check_enrolment`. If mandatory courses are overdue, tell them clearly that they cannot enrol in optional courses until their overdue training is completed.
5. Retired courses: Courses with status 'Retired' cannot be booked even if sessions exist. Clearly inform the user that the course is retired / no longer available.
6. Prerequisites: When proposing a course, check eligibility with `check_enrolment`. If a prerequisite is missing, clearly mention the prerequisite course code (e.g. LD-101) to the employee.
7. Available sessions: Always verify sessions with `list_sessions`. Never choose a session that is full (seats_left == 0). Pick the earliest upcoming session that has seats available (seats_left > 0).
8. Learning plans: `save_learning_plan` is low risk and saves a draft. Call `save_learning_plan` immediately; do not ask anyone for approval.
9. Proposing Enrolments: When an eligible employee asks to enrol or book a course (such as "book me", "as soon as there is a seat", "earliest session", "whichever comes first"), DO NOT just list sessions and ask the user which one they prefer. Immediately call `request_enrolment` for the earliest session with seats_left > 0. The approval gate in code will handle intercepting it and asking the appropriate approver(s).
10. Truthfulness: Never claim that a booking is completed or confirmed before it is executed. If an approval is needed, say that approval has been requested from the appropriate approver."""



def run_agent_loop(messages: list, actor: str) -> tuple[str, str, dict, list]:
    """
    Run the LLM agent loop.
    Returns: (status, message, pending, updated_messages)
      - status: "done" | "awaiting_approval"
      - message: string to display to user
      - pending: dict describing action if awaiting_approval, else None
      - updated_messages: full message list including tool calls/responses
    """
    client = get_openai_client()
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

    # Ensure system prompt is present with actor context
    system_content = f"""{SYSTEM_PROMPT}

CURRENT CONTEXT:
- You are interacting with and acting on behalf of employee ID: {actor}.
- When checking records, budget, completions, or enrolments for the person talking to you, their employee_id is '{actor}'."""

    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_content})
    else:
        messages[0] = {"role": "system", "content": system_content}

    for _ in range(8):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            temperature=0.0,
        )
        choice = response.choices[0]
        msg = choice.message

        # Convert msg to serializable dict for messages list
        msg_dict = {"role": "assistant"}
        if msg.content:
            msg_dict["content"] = msg.content
        if msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(msg_dict)

        if not msg.tool_calls:
            # Model finished turn with plain text
            return "done", msg.content or "", None, messages

        # Process tool calls
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            # Intercept restricted write tools needing approval
            if needs_approval(name):
                if name == "request_enrolment":
                    pending, err = prepare_pending_enrolment(
                        employee_id=args.get("employee_id", actor),
                        course_id=args.get("course_id", ""),
                        session_id=args.get("session_id", ""),
                        actor=actor,
                    )
                    if err:
                        # Feed the refusal back to the model as tool output so it can explain to user
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"status": "refused", "reason": err}),
                        })
                        # Continue model loop to formulate explanation
                        break
                    else:
                        # Propose approval
                        approver_names = ", ".join(pending["approvers"])
                        summary_msg = f"I can enrol you on {pending['args']['course_id']} ({pending['args']['session_id']}). It needs approval from {approver_names}."
                        return "awaiting_approval", summary_msg, pending, messages

                elif name == "cancel_enrolment":
                    pending, err = prepare_pending_cancellation(
                        enrolment_id=args.get("enrolment_id", ""),
                        actor=actor,
                    )
                    if err:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"status": "refused", "reason": err}),
                        })
                        break
                    else:
                        approver_names = ", ".join(pending["approvers"])
                        summary_msg = f"Cancellation request submitted. It needs approval from {approver_names}."
                        return "awaiting_approval", summary_msg, pending, messages

            elif name == "save_learning_plan":
                # Safe write: execute immediately!
                try:
                    result = learning.save_learning_plan(
                        employee_id=args.get("employee_id", actor),
                        plan_text=args.get("plan_text", ""),
                        actor=actor,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
                except ApiError as e:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": e.code, "message": e.message}),
                    })

            else:
                # Read tools
                res = execute_read_tool(name, args, actor=actor)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(res),
                })

    # If exceeded iterations, return last assistant message or generic done
    return "done", messages[-1].get("content", "Processed request."), None, messages
