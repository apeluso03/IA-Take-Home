# Rollout Plan

## Before Rollout
- Disable the v0.3 skill immediately so no one can use it while rollout of the new skill is underway
- Manually check whether the timed-out call did in fact create a key that's still valid
- Investigate if SUP comments from agents can be made internal

## Stages
- Give to platform team only first to test
    - Run new skill against test service or fake Relay first, and if passes, test against a low risk service first
- Once those pass, allow on-call engineers access for a bit to test it in prod
- If the previous two rollouts are successful, the new skill can now be pushed to use for everyone

## Stop Use If
- A key appears in a ticket, chat, transcript, or any other risky place
- A rotate call is retried automatically against the rules
- A comment gets posted publicly

## Rollback
- Revert commit of new skill
- Do not revert back to v0.3 since we know it has vulnerabilities
    - Rather have no skill than a broken one