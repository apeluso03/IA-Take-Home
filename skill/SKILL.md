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
- Never write to any ticket or the ticket system, for any reason.

## 1. Confirm before rotating
Ask the user one question that confirms the service name.
Wait for a yes. Ask even if the user says it is urgent.
The service name must use only lowercase letters, digits, and hyphens. If it does not, stop.

In the same question, ask if there is a ticket ID to record in the audit log.
- It is optional. No ticket does not block rotation.
- It must look like `SUP-5521`: uppercase letters, a hyphen, digits. If not, ask again or leave it out.
- Never guess a ticket ID. Never create a ticket.

## 2. Check the key is set
Run: `python scripts/rotate_key.py --check`
It confirms RELAY_KEY is set and the audit log can be written.
The log is at RELAY_AUDIT_LOG, or `~/.relay/rotation-audit.jsonl` if that is not set. The helper creates the folder.
If it fails, stop. Tell the user which one failed. They must set RELAY_KEY or fix the log themselves.
Never ask the user to paste the key.

## 3. Rotate
Run: `python scripts/rotate_key.py --service <name> --out <path> [--ticket <id>]`
Leave out `--ticket` if there is no ticket ID.
The helper:
- reads RELAY_KEY itself,
- makes one call, with no retries,
- saves the new key to the file at `<path>`,
- prints only the last 4 characters of the new key,
- writes the audit log itself.

Do not call the Relay API yourself, by any tool or command. Use only the helper.

## 4. If it fails or times out
Do not retry.
- `failed`: tell the user the rotation failed and stop.
- `unknown`: tell the user a new key may already exist. Someone must check Relay before trying again.
  Run the helper again only after the user confirms that check was done.
- Exit 4: the call finished, but the audit entry could not be written.
  Do not retry. Tell the user the audit record is missing.
  Check the outcome line: `ok` means the key was rotated; `unknown` means treat it as above.

## 5. Report the result
Tell the user, in chat only:
- the service,
- the time,
- the last 4 characters of the new key.

Say that anything still using the old key needs updating.
[Unverified: whether rotate revokes the old key]

## 6. Audit log
The helper records every rotation in the audit log.
Do not write, edit, move, or delete the log.

Do not put anything in any ticket. That includes the result, the last 4 characters, and any key ID.

Tell the user the rotation is recorded in the audit log under the ticket ID, and that no rotation details may be added to the ticket, including by hand.
If there is no ticket ID, tell the user the rotation is recorded in the audit log.

## Never
- Retry on your own.
- Pass a force or skip flag.
- Print a key.
- Write to a ticket.
- Write to the audit log.
- Use this skill for keys that are not Relay keys.
