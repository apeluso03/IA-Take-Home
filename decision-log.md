# Decision Log

## 11/3/2026
- 430PM: Read through assignment and came up with questions (PLAN.md), scaffolded project
- 442PM: Started drafting SPEC.md, defined rules for Claude Code
- 448PM: Decided to make first task a runner to automate testing redact.py
- 5PM: Looked over redact.py and brainstormed some tests to gather information
- 540PM: Had Claude Code build the evidence runner and ran it against the original redact.py to check the results
    - Discovered redact.py failed in a few key places
        - When hyphenated keys were present
        - When text line wrapped
        - When the key is not lowercase
    - Worked in all other test cases, which must mean redact.py is only checking for the exact lowercase prefix, no hyphens, and no line wrapping pattern
    - Ran redact.py directly from command line, discovered that it returns no output to the command line, meaning the original run in the incident may have been run this way and not caught the unredacted key
        - The packet does not state whether the agent ran redact.py via command line or via call

### Took Break - Time elapsed ~ 80 mins
- 910PM: Wrote and ran a test to simulate running redact.py from the command line
    - Found that redact.py can silently produce no output and throw no errors
- 924PM: Wrote out steps for Task 2 in SPEC.md
    - Decided to have new redact exit with error code and prevent prints to stdout if it detects a key or likely key value still remains
        - Requires a second check
- 950: Redact.py fix commited with checks for line wrapping, case sensitivity, passes all tests

### Took Break - Time elapsed ~ 120 mins
- Plan for tomorrow: 
    - Check SKILL.md and come up with new/corrected version if needed
    - Write out memo and any other writing needed to finish up
    - Record video
    - Try to keep work to around an hour per assignment instructions

## 11/4/2026
- 400PM: Wrote spec task to generate new skill
    - Decided to fold helper task into the same task to ensure the two connected properly
        - Decided to create a helper to rotate the key because having it in code was more reliable than trusting an agent to do it properly
- 427PM: Gap found - skill did not specify how to pass summary to redact.py, and having it be passed on command line would end up being a similar vulnerability to what could have happened in the first place
    - Decided to pass as a file that never touched the command line
- 439PM: Missing ticket should not block rotation because what matters is that key gets rotated in case of a leak
    - If ticket is required, comment could find its way onto a public support ticket via user rushing to find a ticket that may be incorrect
    - Without a ticket, rotation still can occur, but agent posts nothing and gives the redacted summary back to user to file themselves
- 454PM: Had Claude Code build the helper (rotate_key.py) and its tests, all passing
    - Kept the extra safety checks it added beyond the spec: no redirects (urllib would forward the auth header), --out file created before the call so a bad path fails before a key exists, no proxy for the local test URL
    - --out location left as a placeholder, in a real setup it would most likely be a Relay secret store
- 533PM: Began filling out docs (guardrails, rollout, unverified)

## 11/5/2026
- 800AM: Received email with requirement change
    - Could not immediately begin work but began brainstorming what my next steps should be
    - Step 1 and 7 in SKILL.md no longer hold since they involved writing info from rotations to tickets
    - Realized redact.py may no longer be useful if the rotation info is longer being written
- 340PM: Explain the new rule to Claude Code and layout what needs to be changed
    - Decided the helper appends to an audit log on every rotation: time, service, who ran it, outcome (ok, failed, unknown), and the ticket ID if there is one
        - The agent never writes this log on its own, only the code does
    - Decided to keep redact.py even though the new skill may not need it, good to have in case of future changes
    - Had Claude Code write Task 4 in SPEC.md and stop for approval before building
- Answered the open questions in Task 4
    - Ticket ID format: uppercase letters, a hyphen, digits (SUP-5521)
    - Log is a local file written by the helper, location set by an env var. In a real deployment it should be somewhere central like a Relay server side record, but Relay is not being used here
    - Who ran it comes from getpass.getuser(). Weak since it can be edited, a real build would probably pull from Relay
    - Log a started entry before the call, so even if the call does not finish properly there is a record
    - Log bad input too, even if no rotation was attempted it shows intent to rotate for posterity
    - If the audit entry can't be written after the call: don't retry since the key exists even if the record is missing, still print the normal outcome line, warn on stderr, exit with its own code (4)
    - Agent tells the user the rotation is recorded in the audit log under the ticket ID, and that no rotation details may be added to the ticket, including by hand
- Reviewed new SKILL.md and approved
- Gap found - logging bad input could put a pasted key into the log or the transcript
    - Error messages name the field and never repeat the value ("invalid service name (not shown)")
    - Log a reason instead of the value (invalid_service_name), not a length or hash either since both come from what might be a key
    - Ticket ID needs its own format check so there is something to reject
    - Added a test that passes a fake key as the service name and ticket ID and checks it shows up nowhere
    - A failed call keeps exit 2 even if the log write fails, exit 4 only means the call went through
- Exit 4 wording changed to "the call finished" since the outcome could be unknown, not always rotated
- Decided --check should also confirm the log can be written, with a default of ~/.relay/rotation-audit.jsonl (folder created if needed) when no env var is set
- 432PM: Task 4 built and committed, all tests passing
- 442PM: Decided to have a script that starts a fake server and runs every error case the skill describes so I can read each result myself (evidence/try_errors.py)
    - All 13 cases behaved as expected, no key showed up in any output or log
- 446PM: Updated README with everything new and the commands to run each test
