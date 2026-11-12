"""The model's tools, sorted by what they can do to the world.

READS      look things up and change nothing: run them freely.
LOW_RISK   write, but only a draft: run them straight away, ask nobody.
PROPOSALS  writes that matter: NEVER run here. They become a request for a human.
"""
from peoplehub import ApiError, directory, learning

READS = {
    "find_employee": directory.find_employee,
    "get_today": directory.get_today,
    "find_course": learning.find_course,
    "get_learning_profile": learning.get_learning_profile,
    "check_enrolment": learning.check_enrolment,
    "list_sessions": learning.list_sessions,
}
LOW_RISK = {"save_learning_plan": learning.save_learning_plan}
PROPOSALS = {"request_enrolment", "cancel_enrolment"}  # names only: no function to call, on purpose

# Arguments that belong to the system, never to the model: who we act for, who approved, which key.
RESERVED = {"actor", "approved_by", "idempotency_key"}

# hints are what the good agents does in a function failure scenario. They are not the only way to handle errors, but they are a good starting point.
HINTS = {
    "ERR_NOT_FOUND": "Look the id up (find_course, find_employee, get_learning_profile); never guess it.",
    "ERR_FORBIDDEN": "You may not see this record. Tell the user politely; do not try another way.",
    "ERR_UNAVAILABLE": "A temporary failure. You may make this same call once more.",
    "ERR_NOT_APPLICABLE": "The request does not apply as asked. Fix the arguments or explain.",
}

def clean(args):
    """The model's arguments without the ones it must not set."""
    return {k:v for k,v in args.items() if k not in RESERVED}

def failed(code, message, retryable=False):
    """A failure the model can act on: what happened, and whether trying again makes sense."""
    return {"ok": False, "error": code, "message": message, "retryable": retryable, "hint": HINTS.get(code, "")}

def call(fn, args, **system_args):
    """Run one PeopleHub function. Always returns a dict for the model; never raises ApiError."""
    try:
        return {"ok": True, "result": fn(**clean(args), **system_args)}
    except ApiError as e:
        return failed(e.code, e.message, e.retryable)
    except TypeError as e:  # the model sent a missing or unknown argument
        return failed("BAD_ARGUMENTS", str(e))
