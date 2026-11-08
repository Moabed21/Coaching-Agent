"""Where the model comes from. The rest of the agent only sees a function: chat(messages, tools) -> message.

That one seam is what lets tests swap in a fake model (tests/test_loop.py) without touching the loop.
Settings come from .env in the repository root (never commit it) or from the environment.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_llm():
    """Return chat(messages, tools) -> the model's message (content and/or tool_calls)."""
    from openai import OpenAI  # imported here so the tests that use a fake model don't need it

    _load_env()
    client = OpenAI(base_url=os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/") + "/openai/v1/",
                    api_key=os.environ["AZURE_OPENAI_API_KEY"], timeout=60, max_retries=2)
    model = os.environ["AZURE_OPENAI_DEPLOYMENT"]

    def chat(messages, tools):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools, temperature=0)
        return response.choices[0].message

    return chat
