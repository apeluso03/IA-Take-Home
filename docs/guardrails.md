# Guardrail Design

## Principle

## Enforced
- Key never on the command line (the helper reads the env var)
- Exactly one rotate call, no retries
- Timeout reported as “unknown,” separately from “failed”
- Service name checked before any call
- Only the last 4 characters printed
- Base URL override limited to localhost
- redact.py fails closed: no output and a non-zero exit if anything key-like remains

## Advisory
- Asking for confirmation before rotating
- Refusing public or unclear tickets
- Keeping the summary to the listed fields
- Not retrying after “unknown” until someone checks
- Only triggering on Relay keys
- Never asking the user to paste a key

## Can't Catch Currently
- A user pasting a key into chat themselves
- An agent that never loads the skill and improvises
- Secret formats the redactor doesn’t know
- Someone holding the leaked key rotating it themselves
- A key that may already have been created by a timed-out call
- Copies already sent before a comment was deleted (email notifications, edit history)
- A user who never files the summary when there’s no ticket