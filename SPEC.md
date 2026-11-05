# Build Spec: Relay Rotate-Key

## Rules for the agent
- Python 3 standard library only
- Never edit anything in `original/`. It must stay exactly as given
- Fake keys only. Test keys should match Relay format (rly_ plus 24 letters and digits) but must be made up. Never use, ask for, or print a real credential.
- No network calls. Never call relay.example.internal or any real endpoint.
- Small changes, one task at a time. Stop after each task so I can review before committing.
- If something in this spec is unclear or seems wrong, say so and ask.

## Do not decide
- Anything in the memo
- Whether to ship as is or change or block
- Which skill problems get fixed and which are left alone
- What goes in the decision log or AI overrides log

## Repo layout
README.md
PLAN.md
SPEC.md
decision-log.md
original/
  redact.py            # unchanged copy
src/
  redact.py            # fixed version
skill/
  SKILL.md             # corrected skill
  <helper>             # if needed
tests/
  test_redact.py
  test_cli.py
run_tests.py
evidence/
  inputs/              # my hand-written test inputs
  results/             # saved output from running them
  review-items.md      # verdict and evidence per review item
docs/
  memo.md
  guardrails.md
  rollout.md
  unverified.md
  ai-use.md
transcripts/

## Test commands
python3 run_tests.py
python3 run_tests.py --target original

### Task 1: Evidence runner
- What to build: A small script that runs a chosen redact.py (original or fixed) over every file in `evidence/inputs/` and saves the output to `evidence/results/`, with input and output side by side.
- Acceptance criteria: Works on both versions. Does not change any input file. Output makes it easy to see what was and wasn't redacted.
- Verify before committing: I run it against the original and read every result myself.

### Task 2: Fixed redact.py
- What to build: `src/redact.py` that fixes the gaps found in Task 1.
- Optional file argument: `python redact.py <path>` reads from the file instead of stdin. Same output and exit code rules. If the file can't be read: nothing to stdout, reason to stderr, non-zero exit.
- test_cli.py: Add test - File argument gives the same result as stdin, for both a clean file and one with a leftover key.
- Required behavior:
  - Same `redact(text)` function name and signature.
  - Catches every format in Task 2's "must be fully redacted" list.
  - Leaves normal text unchanged.
  - Works from the command line: reads text from stdin, prints the redacted text to stdout.
  - If a key-like string still remains after redacting, or input can't be read, exit with an error code instead of 0
    - Print a short reason to stderr, exit with nonzero code
    - Empty input returns empty output with exit 0
  - Check for leftover values
    - 'rly_' follwed by key-like characters
    - 'rly_' follow by a space or punctuation is not leftover
- Acceptance criteria:
  - All tests in test_redact.py and test_cli.py pass with `--target fixed`.
  - Same tests still fail with `--target original`.
  - No changes to `original/`.
  - Standard library only.
- Verify before committing:
  - Run both targets and save output to evidence/results.
  - Try 3 or more inputs NOT in the test files to check it isn't overfit.
  - Read the new regex or logic myself and be able to explain each part.

### Task 3: Corrected skill and helper
- What to build:
  - Part A: `skill/SKILL.md`, corrected version of `original/SKILL.md`
  - Part B: `skill/scripts/rotate_key.py`
  - Part C: `tests/test_rotate_key.py`, tests for the helper.
  - Also copy the fixed `src/redact.py` to `skill/scripts/redact.py` so the skill is self-contained.
- Order: build Part A, then STOP for my review. Then Parts B and C together, then STOP.

- Do not, in this task:
  - Edit anything in `original/`.
  - Add steps, features, flags, or tools not listed below. If something seems missing, list it in your reply instead of adding it.
  - Make any call to a real endpoint. Tests use a local fake server only.
  - Put any real or realistic-looking key in any file. Test keys must start with rly_FAKE.

#### Part A: SKILL.md
- Frontmatter:
  - name: relay-rotate-key (unchanged)
  - description: Relay service keys only (rly_ prefix). Must say it is not for other providers' keys or tokens (AWS, GitHub, etc.).
- Required content, in this order:
  1. Opening rules: rotation can't be undone; follow steps in order; stop and tell the user if anything fails or is unclear; never print or paste any key into chat, a command line, or a ticket.
  2. Confirm before rotating: one question confirming both service name and ticket. Urgency does not skip it. Service name must be lowercase letters, digits, and hyphens, or stop. (Replaces original steps 6 and 7.)
  3. Check key is set: `python scripts/rotate_key.py --check`. Never ask the user to paste the key. (Replaces original step 1.)
  4. Rotate: `python scripts/rotate_key.py --service <name> --out <path>`. Say the helper reads RELAY_KEY itself, makes one call, no retries, saves the new key to the given file, and prints only the last 4 characters. Tell the agent not to call the API directly with curl or anything else. (Replaces original steps 2 and 3.)
  5. Failure or timeout: do not retry. If the helper reports "unknown," tell the user a key may already exist and someone should check Relay before trying again. Only retry after the user confirms that check. (Replaces original step 4.)
  6. Report result: service, time, last 4 characters. Note that anything using the old key needs updating, and mark `[Unverified: whether rotate revokes the old key]`.
  7. Audit comment: internal only. If the project is customer-visible (like SUP) or visibility is unclear, don't post; give the summary to the user. Summary fields only: service, time, who asked, outcome (success/failed/unknown), last 4 characters. Never request or response bodies, headers, or keys. Write the summary to a file. Run `python scripts/redact.py <file>`. If it exits non-zero, don't post. If it exits 0, post exactly what it printed, not the original summary. Never pass the summary text as a command-line argument.(Replaces original step 5.)
  8. A short "Never" list: retry on your own, pass a force or skip flag, print a key, use for non-Relay keys.
- Style: plain, short sentences. Imperative voice. A heading per step. Under about 80 lines.

#### Part B: rotate_key.py
- Python 3, standard library only (urllib, not curl or subprocess).
- `--check`:
  - Confirms RELAY_KEY is set and non-empty. Never prints it, even partly.
  - Exit 0 if set, 1 if not.
- `--service <name> --out <path>`:
  - Service name must match lowercase letters, digits, hyphens. Otherwise exit 1 before any network call.
  - Refuses if `--out` already exists, so it never overwrites a saved key.
  - Reads the key from RELAY_KEY inside the script. The key is never a command-line argument.
  - Makes exactly one POST to `/v1/keys/rotate` with `{"service": "<name>"}`. No retries, ever.
  - Timeout of 10 seconds.
  - On success: writes only the new key to `--out`, prints `ok service=<name> last4=<xxxx>`. Exit 0.
  - On an error response from the server: prints `failed service=<name> status=<code>`. Exit 2.
  - On timeout or connection drop after sending: prints `unknown service=<name>: a key may have been created, check Relay before retrying`. Exit 3.
  - Never prints the old key, the new key (beyond last 4), headers, or the response body, including in error messages and tracebacks.
- Base URL:
  - Default `https://relay.example.internal`.
  - `RELAY_BASE_URL` may override it for tests, but only to `http://127.0.0.1` or `http://localhost`. Any other override: exit 1. (So the override can't be used to send the key somewhere else.)
- No `--force`, skip, or retry flags.

#### Part C: test_rotate_key.py
- Uses a local fake server (http.server in a thread) on 127.0.0.1. No real network.
- Must cover:
  - --check with RELAY_KEY set, unset, and empty. Output never contains the key.
  - Bad service name: exit 1, and the fake server gets zero requests.
  - Success: exit 0, --out holds the new key, stdout shows only last 4, stdout never contains the full old or new key.
  - Server error (500): exit 2, exactly one request, no key in output.
  - Timeout (server sleeps past the timeout): exit 3, exactly one request.
  - --out already exists: refuses, zero requests.
  - RELAY_BASE_URL pointing at a non-local host: exit 1, zero requests.
  - The key is sent in the Authorization header and never appears in the helper's command-line arguments.
- `run_tests.py` picks these up with the rest. Timeout test should finish in under about 15 seconds total.

- Acceptance criteria:
  - Every original step (1 to 7) is replaced by an item in Part A or clearly removed.
  - Searching SKILL.md finds no `curl`, no `--force`, no `Bearer`, no "retry up to", and no `rly_` followed by key-like characters.
  - Every claim SKILL.md makes about the helper is backed by a test in Part C.
  - All tests pass with `python run_tests.py`, on Windows and Mac/Linux, with no installs.
  - SKILL.md says how the summary is passed to redact.py, and that the posted text is redact.py's output.

- Verify before committing:
  - Part A: I read it side by side with `original/SKILL.md`, tick off each original step, and run the banned-strings search.
  - Part B/C: I read the helper myself and can explain every line. I check that no code path prints the key, including error handling.

### Task 4: No ticket writes, audit log instead
- Why: New requirement. Nothing that comes from a key rotation may be written to any ticket. That includes the response, a masked key (last 4), and a key ID. For this skill, the agent may not write to the ticket system at all. An audit trail must still exist.
- What to build:
  - Part A: update `skill/SKILL.md` to the new rule.
  - Part B: the helper (`skill/scripts/rotate_key.py`) appends one entry to an audit log on every rotation attempt.
  - Part C: tests for the log in `tests/test_rotate_key.py`.
- Order: build Part A, then STOP for my review. Then Parts B and C together, then STOP.

- Do not, in this task:
  - Edit anything in `original/`.
  - Delete `src/redact.py` or its tests. It stays built and tested even though the skill no longer uses it.
  - Add steps, features, flags, or tools not listed below. If something seems missing, list it in your reply instead of adding it.
  - Make any call to a real endpoint or a real ticket system.
  - Put any real or realistic-looking key in any file. Test keys must start with rly_FAKE.

#### Part A: SKILL.md changes
- Rules: add "Never write to any ticket or the ticket system, for any reason."
- Step 1 (Confirm before rotating):
  - Confirm the service name only. Urgency still does not skip it. Name rules unchanged.
  - Ask whether there is a ticket ID to record in the audit log. Optional: no ticket does not block rotation. Never guess or create one.
  - Ticket ID format: uppercase letters, a hyphen, digits, e.g. `SUP-5521`. Anything else: ask again or leave it out.
- Step 3 (Rotate): command becomes `python scripts/rotate_key.py --service <name> --out <path> [--ticket <id>]`. Say the helper writes the audit log itself.
- Step 2 (Check): `--check` now also confirms the audit log can be written (`RELAY_AUDIT_LOG`, or the default path below). If it fails, stop.
- Step 4 (Failure): add exit 4: the call finished but the audit entry could not be written. Do not retry. Tell the user the call finished and the audit record is missing, and to check the outcome line (`ok` or `unknown`) for what happened to the key.
- Step 6 (Audit comment): remove. Replace with "Audit log":
  - The helper records every rotation in the audit log. Do not write, edit, move, or delete the log.
  - Do not post anything to any ticket. That includes the result, the last 4 characters, and any key ID.
  - Tell the user the rotation is recorded in the audit log under the ticket ID, and that no rotation details may be added to the ticket, including by hand.
- Step 5 (Report result) is unchanged: service, time, last 4 characters go to the user in chat only.
- Remove every mention of `redact.py` and the summary file from SKILL.md.
- "Never" list: add "write to a ticket" and "write to the audit log".
- Style unchanged: plain, short, imperative, a heading per step, under about 80 lines.

#### Part B: audit log in rotate_key.py
- New optional flag `--ticket <id>`. Validated with the Part A format before any network call; invalid: exit 1, zero requests, no log entry. The helper never contacts the ticket system.
- Log location: a local file written by the helper. Path from the `RELAY_AUDIT_LOG` env var; if unset or empty, the default `~/.relay/rotation-audit.jsonl`, creating `~/.relay/` (owner-only) if needed. Only the default's folder is created; a set `RELAY_AUDIT_LOG` must point into an existing folder. (In a real deployment this would be a central, server-side record such as Relay's; Relay isn't used here.)
- Format: JSON Lines, one object per line, append only. Never truncate or rewrite existing lines.
- Fields, exactly these:
  - `time`: UTC, ISO 8601
  - `service`
  - `user`: who ran it, from `getpass.getuser()`. Weak (it can be spoofed); a real build would get this from Relay.
  - `outcome`: `started`, `ok`, `failed`, `unknown`, or `rejected`
  - `reason`: only on `rejected` entries (see below)
  - `ticket`: the ID, or `null` if none
- Never in the log: the old key, the new key, any part of either (including last 4), headers, or the response body.
- When it's written:
  - A `started` entry just before the request, so a crash or kill mid-call still leaves a trace.
  - A final entry after the outcome is known (ok, failed, unknown).
  - Bad input that exits 1 before any request is also logged, as intent to rotate, with outcome `rejected`.
  - A rejected entry never records the raw bad value, since a bad value could be a pasted key. An invalid service name or ticket ID is logged as `null`, and a `reason` field says what was wrong (e.g. `"reason": "invalid_service_name"`). Never log a length or hash of the bad value either.
  - Error messages name the field, never repeat the value: e.g. "invalid service name (not shown)". This includes argument-parsing errors.
- `--check`: exit 0 only if RELAY_KEY is set and the log can be opened for append; otherwise exit 1. Writes no entry (it isn't a rotation).
- If the log can't be opened for append (or the default folder can't be created): exit 1, zero requests (nothing can be logged).
- If writing the `started` entry fails: exit 1, zero requests.
- If writing the final entry fails after a request was sent:
  - Don't retry the rotate call. The key exists even if the record is missing.
  - Still print the normal outcome line.
  - Print a clear warning to stderr: the rotation finished, but the audit entry couldn't be written.
  - Exit 4, meaning "rotated, audit incomplete".
  - If the outcome was `failed` (no rotation), keep exit 2 and still print the warning, since exit 4 means "rotated".
- New log file created with owner-only permissions where the OS supports it.

#### Part C: tests
- Must cover:
  - ok, failed (500), and unknown (timeout) each append exactly one entry with the right `outcome`.
  - Entry has exactly the five fields (plus `reason` on rejected entries), `time` parses as UTC ISO 8601.
  - `--ticket SUP-1234` is recorded; no `--ticket` records `null`.
  - Every request is preceded by a `started` entry.
  - Invalid ticket ID: exit 1, zero requests, one `rejected` entry.
  - Bad service name: exit 1, zero requests, one `rejected` entry, raw value not in the log.
  - A fake key passed as the service name, and as the ticket ID: it appears nowhere in the log, stdout, or stderr, and the fake server gets zero requests.
  - Final entry can't be written after a successful call: normal outcome line, stderr warning, exit 4, exactly one request.
  - `RELAY_AUDIT_LOG` unset: entries go to `~/.relay/rotation-audit.jsonl`, folder created (tests use a temporary home folder, never the real one).
  - Log not writable: exit 1, zero requests.
  - `--check`: exit 1 when the log isn't writable, no entry written.
  - Two runs append two lines; earlier lines unchanged.
  - The log never contains the old key, the new key, or the new key's last 4.
- Existing helper tests still pass.

- Acceptance criteria:
  - Searching SKILL.md finds no `redact.py`, no "comment", no "post", plus everything in Task 3's banned-strings search.
  - Every claim SKILL.md makes about the audit log is backed by a Part C test.
  - `src/redact.py` and its tests are unchanged and still pass.
  - All tests pass with `python run_tests.py` and `python run_all.py`.

- Follow-ups outside this task (list only, I decide):
  - `skill/scripts/redact.py` and `src/redact.py` are kept for possible future use (decided).
  - Docs that describe ticket comments: `docs/memo.md`, `docs/guardrails.md`, `docs/rollout.md`, `README.md`.
  - Where the audit log lives in a real setup, and who can read it.

- Verify before committing:
  - Part A: I read it against the new requirement and run the banned-strings search.
  - Part B/C: I read the helper's log code and check no code path writes key material to the log.
