# Plan: Relay Rotate-Key Take-Home

## Goal and context
Engineers use an AI agent with a shared skill to rotate a service key for Relay, the key may have leaked. Skill retired after timeout and posted request/response to a public support ticket that was visible to customers. A suspected key string managed to bypass the redaction. Inheriting the skill, the incident note, one helper script, and an automated AI review of the skill. Goal is to decide what ships and to make the setup safer.

## Time
Start time ~4:30PM 11/3/2026

## Order of work
1. Planning/Spec
2. Write some test inputs and run redact.py as is, analyze/save results
3. Brainstorm fix to redact.py (if necessary), test fix
4. List findings
5. Brainstorm potential changes to SKILL.md and helper
6. Design guardrail
7. Plan rollout
8. Write out unverified list
9. Double check AI-use note is up to date and complete
10. Final draft of memo
11. Record short video of solution

## Questions to investigate
### Attachment A: the skill
- Step 4: What happens if you retry a call that could have already created a key?
- Step 5: What is in a "full request and response"; what parts have key values
- Step 7: If an action cannot be undone, should it be able to run without any confirmation?
### Attachment B: incident note
- How long was the leaked key both valid and visible?
- Did the timed out call create a key?
### Attachment C: redact.py
- What is the result/output when running redact.py from command line?
### Attachment D: review items 1 to 6
- Is redact.py covering all formats?
- Did the review miss anything?