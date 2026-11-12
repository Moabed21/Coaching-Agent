"""The agent loop: the model proposes, this code decides what really runs.

Rule of the conversation: every tool call the model makes gets exactly ONE tool reply, in the
same turn, before anything else is sent. Break it and the model API refuses the whole history.
"""
import json
from typing import Any, Callable, TypedDict

from . import executor, policy, tools
from .approval import Action
from .prompt import system_prompt
from .schemas import TOOLS

MAX_MODEL_CALLS = 8

Message = dict[str, Any]
# The model, as a plain function: chat(messages, tools) -> the model's message (content and/or tool_calls).
# The real one comes from agent/llm.py; tests pass a FakeModel (tests/helpers.py) instead.
Chat = Callable[[list[Message], list[dict]], Any]


class Outcome(TypedDict, total=False):
    answer: str        # the model is done: this is the text for the user
    proposal: Action   # an action passed the policy checks and now needs a human


def run(messages: list[Message], actor: str, thread: str, chat: Chat) -> Outcome:
    """Handle one user request. `messages` is the saved conversation; it is extended in place."""
    for _ in range(MAX_MODEL_CALLS):
        msg = chat([{"role": "system", "content": system_prompt(actor)}] + messages, TOOLS)
        messages.append(_assistant(msg))
        if not msg.tool_calls:
            return {"answer": msg.content or ""}

        proposal = None
        for call in msg.tool_calls:  # answer EVERY call, even after a proposal
            reply, action = _handle(call, actor, thread, may_propose=proposal is None)
            proposal = proposal or action
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(reply, ensure_ascii=False, default=str)})
        if proposal:
            return {"proposal": proposal}

    return {"answer": "I could not finish this in a reasonable number of steps, so I stopped. "
                      "Nothing was booked or changed."}


def _handle(call: Any, actor: str, thread: str, may_propose: bool) -> tuple[dict, Action | None]:
    """Run or refuse ONE tool call. Returns (reply for the model, action or None)."""
    name = call.function.name
    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError:
        return tools.failed("BAD_ARGUMENTS", "The arguments were not valid JSON."), None

    # Reads: run them freely.
    if name in tools.READS:
        return tools.call(tools.READS[name], args, actor=actor), None

    # Low-risk writes (a draft plan): run now, with a key so the same plan twice is saved once.
    if name in tools.LOW_RISK:
        key = executor.idempotency_key(thread, name, tools.clean(args), 0)
        return tools.call(tools.LOW_RISK[name], args, actor=actor, idempotency_key=key), None

    # Writes that matter: never run here. Check them, and turn them into a request for a human.
    if name in tools.PROPOSALS:
        if not may_propose:
            return tools.failed("ONE_AT_A_TIME", "Only one action can wait for approval at a time; not sent."), None
        try:
            action = policy.plan(name, tools.clean(args), actor)
        except policy.Refused as e:
            return {"ok": False, "refused": str(e)}, None  # the model explains the refusal to the user
        return {"ok": True, "status": "sent_for_approval", "approvers": action["rounds"][0],
                "note": "Nothing is done yet: a human must approve first."}, action

    return tools.failed("UNKNOWN_TOOL", f"There is no tool called {name}."), None


def _assistant(msg: Any) -> Message:
    """The model's message as a plain dict, so it can be saved as JSON and sent again later."""
    out: Message = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [{"id": c.id, "type": "function",
                              "function": {"name": c.function.name, "arguments": c.function.arguments}}
                             for c in msg.tool_calls]
    return out
