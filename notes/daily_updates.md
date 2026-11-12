# Daily updates

Three lines at the end of each working day, newest at the top (template: templates/daily_update.md).

## Thursday 2026-11-12
Done today: finished the refactor. The approval check, saving state, the single place that writes, the main loop, and the command line are all rebuilt. I removed the old code, added six scenarios of my own, updated the README, and made the code easier to read. All 45 unit tests pass, and all 14 scenarios pass three times in a row with no safety problems.
Next: open the pull request, prepare the 10-minute demo, and review the Recruiting team's PR. With another week, I would test with a second model and add a wait between retries.
Blocked on (and who could unblock it): nothing. The shared model hit its rate limit once when two test runs overlapped, so I run them one at a time.

## Wednesday 2026-11-11
Done today: sorted the tools into three groups (look-ups, a safe draft write, and writes that need approval), with small helpers to clean the model's arguments and report errors clearly. Then the policy: every request is checked with PeopleHub before anyone is asked, and the approvers come from PeopleHub.
Next: the approval steps, then saving state to disk.
Blocked on (and who could unblock it): nothing.

## Tuesday 2026-11-10
Done today: started tools.py, sorting the tools into groups, and wrote the first tests for it.
Next: clear error messages for the model, then the policy checks.
Blocked on (and who could unblock it): nothing.

## Sunday 2026-11-08
Done today: added the guide kit (tool list, prompt, model client, tests, notes) on top of the working first version, which passed all 8 public scenarios. Studied why the old agent crashed when the user wrote again after an approval: one of the model's tool calls never got a reply. Decided to write my own loop instead of using LangGraph.
Next: tools, then policy.
Blocked on (and who could unblock it): nothing.
