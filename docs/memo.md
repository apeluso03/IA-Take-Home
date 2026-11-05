# Decision Memo: relay-rotate-key

## Decision
I have decided to shut down the use of v0.3 and ship a new, changed version. This new version will at first ship only to the immediate platform team to further test on real services before being allowed to go live company wide. This decision has been made to ensure keys no longer leak in a similar fashion to the incident, in that an agent using the skill may not post a full request, or any sensitive material, to a public ticket. The new version uses a helper function along with the skill to make the rotate call through code, ensuring the agent never needs to access or print the key's actual value. In the event of any leaks after rollout, a rollback should occur that would leave the team with no skill until further tweaks are made, since a rollback to v0.3 which is known to have flaws should not be allowed.

### What changed after new rule
The decision remains the same, shut down v0.3 and ship the changed skill, platform team first. What changed is how the skill keeps its record. In the original fix, the agent wrote a redacted summary into an internal ticket. The new rule bars anything from a rotation going into a ticket, so the agent no longer touches the ticket system at all. Instead, the rotate_key.py helper appends an entry to an audit log for every attempt, including rejected and started ones. Each entry holds the time, service, who ran it, the outcome, and an optional ticket ID. Only code writes the log, so the agent can't leak a key into it.

What I gave up:

- The ticket is no longer the record. Someone reading the ticket won't see that a rotation happened or what the outcome was. The ticket ID is just a reference inside the log
- The last 4 characters of the key are no longer noted
- A rotation can be blocked by the log. If the log can't be written, the helper refuses to rotate. That could slow an urgent fix after a leak
- A rotation can still end up unrecorded. If the log write fails after the call has gone through, the key is rotated without a record and an error is logged
- The fixed redact.py isn't used by the skill anymore

## What changed and why

**1. The rotate call moved out of the skill and into a helper (`skill/scripts/rotate_key.py`).**
- **The key is never on the command line.** The helper reads `RELAY_KEY` itself. In v0.3 the shell expanded the key into the curl command, where any process listing could read it (review item 1, confirmed on Windows).
- **It makes exactly one call and never retries.** v0.3 retried up to 5 times after a timeout. The incident note says nobody knows whether the first, timed-out call created a key.
- **Timeouts are reported as `unknown` (exit 3), separately from `failed` (exit 2).** On `unknown`, someone must check Relay before anyone tries again.
- **The new key is saved to a file, and only its last 4 characters are printed.** v0.3 showed the full new key in chat.
- **The service name is checked before any call.** A key file that already exists is never overwritten.
- **It has no force, skip or retry flags.** Redirects are refused so the key can't be forwarded, and the base URL can only be overridden to point at this machine, for tests.

**2. The skill (`skill/SKILL.md`) was rewritten around the helper.**
- **The agent confirms the service and the ticket before rotating, even when the user says it's urgent.** v0.3 said not to ask and offered `--force` for urgent requests.
- **A missing ticket doesn't block rotation.** Getting the key rotated matters most. With no ticket, the agent posts nothing and hands the redacted summary to the user to file. It never guesses a ticket or creates one.
- **The audit comment is a short summary, not the full request and response.** It holds only the service, time, who asked, outcome, and last 4 characters. v0.3's comment contained both the old key (in the header) and the new key (in the response body), which left the redactor as the only defense.
- **Comments go to internal tickets only.** If a ticket is customer-visible (like SUP) or unclear, the agent posts nothing.
- **The summary is redacted from a file, and only redact.py's output is posted.** If redact.py exits non-zero, nothing is posted. Passing the summary on the command line would repeat the process-list problem.
- **The description now limits the skill to Relay (`rly_`) keys.** v0.3's description could trigger on any leaked key (review item 6).

**3. The redactor was fixed (`src/redact.py`, with a copy in `skill/scripts/`).**
- **It catches the formats the original missed:** hyphenated keys, upper- and mixed-case prefixes, keys wrapped across lines (including inside the `rly_` prefix), overlong keys, and `Bearer` in any case (review item 2).
- **It works from the command line.** The original printed nothing and exited 0 when run that way, so "run redact.py over the comment" could silently do nothing.
- **It fails closed.** If anything key-like remains after redacting, it prints nothing and exits non-zero.

**4. Tests and evidence were added.** These are hand-written inputs, unit and command-line tests, and tests that run the helper against a fake local Relay server. `python3 run_all.py` runs everything and writes one report (`evidence/results/test-report.md`). The fixed versions pass every test. The original redactor fails 24 of 40, which shows its gaps.

## What was not changed
- **`original/` was not edited.** The v0.3 skill and redactor stay exactly as given, for comparison.
- **The skill's name, its trigger on leaked or rotating keys, and its audit trail stayed.** The trail is now a redacted summary instead of the full request and response.
- **Nothing on the Relay side changed.**
  - It's still unverified whether rotating revokes the old key; the skill marks this as unverified.
  - Whether the timed-out call in the incident created a key still needs a manual check before rollout.
  - Anyone holding the leaked key can still call rotate themselves.
- **Ticket visibility in SUP was not changed.** The skill avoids customer-visible tickets, but nothing yet stops an agent comment from being public. Whether agent comments can default to internal is an open question.
- **Where `--out` should point is still a placeholder.** In a real setup it would most likely be a Relay secret store.
- **Some risks are not enforced in code.** The skill can ask for these, but code can't guarantee them:
  - asking for confirmation
  - refusing unclear tickets
  - not retrying after `unknown`
  - an agent that never loads the skill
  - a user pasting a key into chat
  - secret formats the redactor doesn't know

  These are listed in `docs/guardrails.md` and `docs/unverified.md`.
- **Not tested:** on Linux or Mac, against a real Relay service, or with a real ticket system.