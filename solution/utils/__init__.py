"""utils package — General-purpose helpers, state management, and canonical error codes:

  - error_codes.py: PeopleHub API error codes and policy ineligibility reason codes.
  - state.py: Thread persistence (save_state, load_state, STATE_DIR).
  - helpers.py: SHA-256 idempotency keys, JSON stdout response, OpenAI client builder, import paths.
"""

from .error_codes import (
    ERR_NOT_FOUND,
    ERR_FORBIDDEN,
    ERR_NO_ACTOR,
    ERR_NOT_APPROVED,
    ERR_APPROVER_NOT_ALLOWED,
    ERR_APPROVAL_INCOMPLETE,
    ERR_NOT_ELIGIBLE,
    ERR_HUMAN_ONLY,
    ERR_DUPLICATE,
    ERR_SESSION_FULL,
    ERR_NOT_APPLICABLE,
    ERR_IDEMPOTENCY_CONFLICT,
    ERR_UNAVAILABLE,
    REASON_RETIRED,
    REASON_ALREADY_COMPLETED,
    REASON_ALREADY_BOOKED,
    REASON_PREREQUISITE_MISSING,
    REASON_BELOW_MIN_GRADE,
    REASON_OVER_BUDGET,
    REASON_MANDATORY_OVERDUE,
    REASON_MANDATORY_BOOKED_BY_HR,
    RETRYABLE_ERROR_CODES,
)
from .state import (
    save_state,
    load_state,
    STATE_DIR,
)
from .helpers import (
    setup_import_paths,
    make_idempotency_key,
    respond,
    get_openai_client,
)

__all__ = [
    # Error codes
    "ERR_NOT_FOUND",
    "ERR_FORBIDDEN",
    "ERR_NO_ACTOR",
    "ERR_NOT_APPROVED",
    "ERR_APPROVER_NOT_ALLOWED",
    "ERR_APPROVAL_INCOMPLETE",
    "ERR_NOT_ELIGIBLE",
    "ERR_HUMAN_ONLY",
    "ERR_DUPLICATE",
    "ERR_SESSION_FULL",
    "ERR_NOT_APPLICABLE",
    "ERR_IDEMPOTENCY_CONFLICT",
    "ERR_UNAVAILABLE",
    # Reason codes
    "REASON_RETIRED",
    "REASON_ALREADY_COMPLETED",
    "REASON_ALREADY_BOOKED",
    "REASON_PREREQUISITE_MISSING",
    "REASON_BELOW_MIN_GRADE",
    "REASON_OVER_BUDGET",
    "REASON_MANDATORY_OVERDUE",
    "REASON_MANDATORY_BOOKED_BY_HR",
    "RETRYABLE_ERROR_CODES",
    # State
    "save_state",
    "load_state",
    "STATE_DIR",
    # Helpers
    "setup_import_paths",
    "make_idempotency_key",
    "respond",
    "get_openai_client",
]
