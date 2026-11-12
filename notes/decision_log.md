# Decision log

Add a line whenever you choose between two ways of doing something. Future you, and the person reviewing your work, will thank you.

| Date | Decision | Why | What I rejected |
|---|---|---|---|
| 2026-11-07 | Put the folders back where the brief has them (peoplehub/, harness/, scenarios/ at the top) | The README, the test runner and a fresh clone all expect this layout | Keeping everything inside provided/ |
| 2026-11-08 | Write my own small loop and save state as JSON, instead of using LangGraph | LangGraph is too much for this task. With my own loop I can point at the approval check and the saved state and explain every line | LangGraph's `interrupt()` with a SQLite checkpointer |
| 2026-11-10 | The two important writes (book, cancel) are only names in tools.py, with no function behind them | The loop can't run a booking by accident, because there is nothing to run | One list of all functions with an `if needs_approval` check |
| 2026-11-10 | Remove `actor`, `approved_by` and `idempotency_key` from whatever the model sends | Who we act for, who approved and the request key are set by the system, never by the model | Trusting the model to leave them out |
| 2026-11-11 | Check every booking with PeopleHub before asking anyone to approve it | Nobody should be asked to approve something the system will refuse anyway | Sending the booking and waiting for PeopleHub to say no |
| 2026-11-11 | Take the list of approvers from PeopleHub (`check_enrolment`) | One source of truth. It also handles the case where the manager is the HR head | "Fee over 3,000 means also ask E1068", written into the code |
| 2026-11-11 | Warn, but don't block, when open bookings together go over the remaining budget | PeopleHub only counts finished courses, so it allows this. The user and the approver should still know | Blocking it, or saying nothing |
| 2026-11-12 | If someone who wasn't asked answers the approval, close the request | A "yes" only counts from the right person, and every resume must end with one clear answer | Waiting for the right person; letting PeopleHub refuse it |
| 2026-11-12 | An approver can only change the session, and the changed request is checked again | A change makes it a new request, and the new one may not be allowed | Accepting any change; picking another session ourselves |
| 2026-11-12 | Save each conversation as one JSON file, written to a temp file and then renamed | Easy to open and read, needs no extra library, and a crash never leaves a half-written file | A SQLite checkpointer; writing the file directly |
| 2026-11-12 | Retry only once, only for temporary errors, and with the same request key | Retrying with the same key can't book twice. A real refusal needs an explanation, not another try | Retrying every error; a new key for each try |
| 2026-11-12 | The request key is made from the conversation, the action, its details and a count of past writes, and is saved before the booking | The same action always gets the same key, even after a crash. Booking, cancelling and booking again get three different keys | A random key per call; a key without the count |
| 2026-11-12 | The loop gets the model as a plain function, so tests can use a fake model | The loop's rules can be tested without the internet, without a key, with the same result every time | Testing only with the real model |
| 2026-11-12 | Check the request again every time an approver answers | Things change while we wait: an edit, or the last seat being taken | Trusting the first check |
| 2026-11-12 | Use `TypedDict` to describe the data passed between files | Easier to read, and the editor can help, but the data is still plain dicts, so saving to JSON doesn't change | `@dataclass`, which would need converting to and from JSON everywhere |
| 2026-11-12 | Use two small decorators: one for the retry, one to register the CLI commands | Each piece reads on its own: what to call, and how often to try | A retry loop inside `execute`; a long if/elif in `main` |
| 2026-11-12 | Leave the prompt as it is when the model was over-careful in a follow-up answer | It was about wording, not safety, and the rule "never say approved without proof" stops false claims | Loosening that rule |
