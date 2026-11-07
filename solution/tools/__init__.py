"""tools package — Aggregates all PeopleHub tools partitioned by safety & authorization level:

  - readonly.py: Read-only query tools & dry-run checks.
  - approval_required.py: Write actions strictly requiring human approval.
  - low_risk_auto_approval.py: Low-risk write actions executing automatically without approval.
"""

from .readonly import READ_TOOLS, READ_TOOL_NAMES, execute_read_tool
from .approval_required import APPROVAL_REQUIRED_TOOLS, APPROVAL_REQUIRED_TOOL_NAMES
from .low_risk_auto_approval import LOW_RISK_TOOLS, LOW_RISK_TOOL_NAMES

# Complete combined tool schemas list for OpenAI function calling
TOOLS = READ_TOOLS + APPROVAL_REQUIRED_TOOLS + LOW_RISK_TOOLS

# Aliases for backward compatibility
SAFE_WRITE_TOOL_NAMES = LOW_RISK_TOOL_NAMES
RESTRICTED_WRITE_TOOL_NAMES = APPROVAL_REQUIRED_TOOL_NAMES

__all__ = [
    "TOOLS",
    "READ_TOOLS",
    "READ_TOOL_NAMES",
    "execute_read_tool",
    "APPROVAL_REQUIRED_TOOLS",
    "APPROVAL_REQUIRED_TOOL_NAMES",
    "LOW_RISK_TOOLS",
    "LOW_RISK_TOOL_NAMES",
    "SAFE_WRITE_TOOL_NAMES",
    "RESTRICTED_WRITE_TOOL_NAMES",
]
