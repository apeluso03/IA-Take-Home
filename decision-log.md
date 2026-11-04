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