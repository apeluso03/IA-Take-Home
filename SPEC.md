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