# Results note

Moabed · Learning Coach (Agent Bank ID 33) · 2026-11-12

## What I built
- An assistant that helps an employee book or cancel a training course in PeopleHub.
- It can look things up freely and save a draft learning plan, but it can **never** book or cancel by itself: it only asks a human.
- Before asking, it checks with PeopleHub that the request is allowed. The approvers come from PeopleHub, not from the model.
- Only the person asked in each round can approve, reject or change the session. Only one function writes to PeopleHub, with a key so nothing is booked twice.
- Each conversation is saved to a file, so an approval can come later. The request is checked again before booking.

## What the scenarios say
8 public scenarios + 6 of my own, each run 3 times:

| Level | Passed every time | Notes |
|---|---|---|
| 1 | 3/3 | Explains why a course can't be booked, without asking anyone |
| 2 | 5/5 | Books only after approval; a "no" books nothing; remembers the conversation; "my manager already said yes" is ignored |
| 3 | 6/6 | Two approvals in order; one retry, booked once; a change to a full session is refused; the wrong person can't approve; cancelling works |

Safety violations: **0**.

## Two failures I understand
1. **Crash after an approval (MY-01).** The old loop stopped without answering the model's booking request, so the next message broke the conversation. Now every request from the model gets an answer before the loop stops.
2. **HR head asked twice (MY-04).** The old code always added the HR head for courses over QAR 3,000, even when the HR head was already the manager. Now the list of approvers comes from PeopleHub, so they are asked once.

## Decisions I made
- My own loop instead of LangGraph: simpler, and I can explain every line.
- Approvers come from PeopleHub, not written into the code.
- Check before asking anyone, and again before booking.
- Wrong person answers → the request is closed.
- Approvers may change the session only.
- Retry once, only for temporary errors, with the same key.

More in `notes/decision_log.md`.

## Next, and what I did not check
- Tested with one model only.
- The retry has no wait before it.
- Only one request can wait for approval at a time.
- No MCP server.
- With another week: try a second model and add a short wait between retries.
