# Review items: verdicts and evidence

| # | Claim | Verdict | Confidence |
|---|---|---|---|
| 1 | Key on command line visible in process list. Medium. | | |
| 2 | redact.py covers all formats. No change. | | |
| 3 | Retry loop is good. Keep it. | | |
| 4 | Jira comments are access controlled. No change. | | |
| 5 | --force is documented in the helper. Fine on user's say-so. | | |
| 6 | Description is clear and triggers correctly. No change. | | |

## Item 1: key visible in the process list
- Verdict: Yes
- Why: After running a test in my own command line it was confirmed; setting a fake key variable and running a curl command like what happened in the incident with a timeout resulted in being able to find the key in a separate window by getting the process
- Evidence:
  - Ran step 2 of the original skill on Windows 11 with a fake key in $env:RELAY_KEY:
    `curl.exe -s -H "Authorization: Bearer $env:RELAY_KEY" http://10.255.255.1 --connect-timeout 60`
  - While it was running, from a second window:
    `Get-CimInstance Win32_Process -Filter "Name='curl.exe'" | Select-Object -ExpandProperty CommandLine`
  - Output (evidence/results/item1_process_list.txt):
    `"C:\windows\system32\curl.exe" -s -H "Authorization: Bearer rly_FAKEa1b2c3d4e5f6g7h8i9j0" http://10.255.255.1 --connect-timeout 60`
  - The shell replaces $env:RELAY_KEY with its value before curl starts, so the full key is in the process's command line. Reading the key from an env var doesn't protect it.
  - Fix: the new helper reads RELAY_KEY inside the script and never puts it in its arguments (tests/test_rotate_key.py).
- Tested? Partly.
  - Confirmed: the key is in the process command line, readable from the same user's session.
  - Not tested: whether a *different* user can read it. On Windows this usually needs admin rights; on Linux and Mac, other users can often see command lines by default. Not tested on Linux or Mac, or as a second user.
  - Tested on one machine only (Windows, my own account).

## Item 2: redact.py covers all formats
- Verdict: redact.py does not cover all formats
- Why: After testing, I found formats such as hyphenated, line-wrapped, case sensitive, comments, and extra appended text keys do not get caught by the original redact.py
- Evidence:
  - Packet, Attachment C: "It is also sometimes shown with hyphens, or line-wrapped by chat tools."
  - Ran original redact.py over 10 hand-written inputs (evidence/inputs/, results in evidence/results/ and SUMMARY.md):
    - 02_hyphenated: unchanged, key leaked
    - 03_wrapped: unchanged, both halves leaked
    - 05_uppercase: unchanged, key leaked
    - 07_long: redacted but left a tail ("MORETEXT")
    - 10_comment: old key caught by the Bearer pattern, new hyphenated key in the response leaked
  - Ran `python original/redact.py` from the command line: no output, exit code 0.
  - tests/test_redact.py and tests/test_cli.py fail against the original, pass against the fix (`python run_tests.py --target original` / `--target fixed`).
- Tested? Yes.

## Item 3: retry loop is a good pattern
- Verdict: No
- Why: Retries that go unchecked and don't produce any output are bad practice, there is no way to check whether a key was made without going in manually
- Evidence:
  - Attachment B: "The first rotate call timed out. The skill retried. The second call worked." and "We do not yet know whether the first (timed out) call also created a key."
  - Fix: helper makes one call and reports a timeout as "unknown" (exit 3). tests/test_rotate_key.py confirms exactly one request on timeout.
- Tested? Partly. Can't test Relay's behavior (whether a timed-out call creates a key). Tested only that the new helper doesn't retry.

## Item 4: Jira comments are access controlled
- Verdict: N/A
- Why:
- Evidence:
  - Attachment B: "Ticket project SUP is the support project. Customers with portal access can see public comments on it. The comment was public."
- Tested? No. No access to Jira. Based on attachment text only.

## Item 5: --force is documented in the helper
- Verdict: No
- Why: redact.py does not have any mention of a --force flag that I could find
- Evidence:
  - Packet: the only script provided is redact.py. It has no --force flag and no help text (Attachment C; running it from the command line produces nothing).
  - No other helper appears anywhere in the assignment, so the help text the review describes can't be checked.
- Tested? Partly. Checked the assignment contents and redact.py. Can't rule out a helper that exists outside the scope.

## Item 6: description is clear and triggers correctly
- Verdict: No
- Why: Users should have to be explicit with what they are asking of an agent, so the description not mentioning explicitly which key needs to be rotated could be a problem
- Evidence:
  - Attachment A: "Use when someone says a key leaked or needs rotating." It doesn't mention Relay or the rly_ key format.
  - Corrected description in skill/SKILL.md scopes it to Relay keys only.
- Tested? No. Reasoning from the wording only. Could test by giving an agent prompts like "my AWS key leaked" and "rotate the billing-sync Relay key" and seeing whether the skill loads.

## What the review missed
<!-- Your call what goes here. Candidates: full request/response contains keys (step 5), new key shown in chat (step 3), no confirmation (step 7), nothing about revoking the old key, curl -s hiding errors. -->