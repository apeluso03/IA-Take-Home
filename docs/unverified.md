# Unverified

1. Unsure how the agent went about calling redact.py in the incident
    - I assume it was called properly, and therefore missed redacting a hyphenated or line wrapped key, but no way to be sure
2. Unclear if rotating key automatically invalidates all old keys or if there are checks in place to ensure old keys are no longer valid
3. New SKILL.md --out is a placeholder since it would most likely be a relay secret store in real implementation
4. Can SUP comments initiated by agents be made to post internally only be default?
5. Audit log: getpass.getuser() works for now but is weak since any user can change its value - would be grabbed from relay in real build