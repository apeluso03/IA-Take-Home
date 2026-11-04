---
name: relay-rotate-key
description: Rotate a Relay service key (keys that start with rly_). Use only for Relay keys. Not for other providers' keys or tokens (AWS, GitHub, etc.).
---
# Rotate a Relay key

## Rules
- Rotation cannot be undone.
- Follow the steps in order. Do not skip any.
- If anything fails or is unclear, stop and tell the user.
- Never print or paste any key into chat, a command line, or a ticket.

## 1. Confirm before rotating
Ask the user one question that confirms both the service name and the ticket.
Wait for a yes. Ask even if the user says it is urgent.
The service name must use only lowercase letters, digits, and hyphens. If it does not, stop.

## 2. Check the key is set
Run: `python scripts/rotate_key.py --check`
If it fails, stop. Tell the user to set RELAY_KEY themselves.
Never ask the user to paste the key.

## 3. Rotate
Run: `python scripts/rotate_key.py --service <name> --out <path>`
The helper:
- reads RELAY_KEY itself,
- makes one call, with no retries,
- saves the new key to the file at `<path>`,
- prints only the last 4 characters of the new key.

Do not call the Relay API yourself, by any tool or command. Use only the helper.

## 4. If it fails or times out
Do not retry.
- `failed`: tell the user the rotation failed and stop.
- `unknown`: tell the user a new key may already exist. Someone must check Relay before trying again.
Run the helper again only after the user confirms that check was done.

## 5. Report the result
Tell the user:
- the service,
- the time,
- the last 4 characters of the new key.

Say that anything still using the old key needs updating.
[Unverified: whether rotate revokes the old key]

## 6. Audit comment
Post only to an internal ticket.
If the project is customer-visible (like SUP), or you are not sure, do not post. Give the summary to the user instead.

The summary has only these fields:
- service
- time
- who asked
- outcome: success, failed, or unknown
- last 4 characters of the new key

Never include request or response bodies, headers, or keys.

Before posting:
1. Write the summary to a file.
2. Run: `python scripts/redact.py <file>`
3. If it exits non-zero, do not post. Tell the user.
4. If it exits 0, post exactly what it printed. Do not post the original summary.

Never pass the summary text as a command-line argument.

## Never
- Retry on your own.
- Pass a force or skip flag.
- Print a key.
- Use this skill for keys that are not Relay keys.
