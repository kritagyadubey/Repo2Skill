# Skill package template

The package a repo2skill run produces. Create only the files that carry value;
delete every line that does not apply.

```
out/<skill-name>/
  SKILL.md                 required - the operating contract
  README.md                required - short human-facing description
  PROVENANCE.json          required - written by scripts/provenance.py
  LICENSE-NOTICE.md        only when the upstream license imposes obligations
  scripts/                 only for deterministic, error-prone steps
    audit_drift.py         copy from the engine so the skill can audit itself
  references/              deep knowledge, opened on demand
    api-cheatsheet.md
    config-reference.md
    workflows.md
    gotchas.md
    troubleshooting.md
  assets/                  templates, schemas, sample inputs
  tests/                   fixtures and a validation harness
```

## SKILL.md skeleton

```markdown
---
name: <lowercase-hyphenated, <= 64 chars>
description: <what it does and when to use it, in the user's own words; <= 1024 chars>
---

# <skill-name>

## Purpose
## When to use
## When NOT to use
## Prerequisites
## Inputs and outputs
## Operational workflow
1. <step> - expected result: <observable output>
## Decision rules
## Worked example
<input> -> <real observed output>
## Error handling
## Common failures
## Verification
## Safety constraints and confirmation points
## Reference navigation
```

## Content rules

- Every command is either verified in this run or visibly tagged `[UNVERIFIED]`.
- Cite the upstream repository as `path:line @ <short-sha>`; do not paste source.
- Separate what the upstream repository REQUIRES from what you merely recommend.
- Put the workflow in the imperative with an expected result after each step so
  a fresh agent can detect divergence.
- Add a "STOP AND ASK" list: missing credentials, destructive action, ambiguous
  target, version mismatch.

## Pre-delivery checklist

- [ ] `python <engine>/scripts/validate_skill.py out/<skill-name>` exits 0
- [ ] `python <engine>/scripts/scan_secrets.py out/<skill-name>` is clean
- [ ] every command in SKILL.md was run, or is tagged `[UNVERIFIED]`
- [ ] every referenced upstream path exists at the pinned SHA
- [ ] the single worked example shows output you actually observed
- [ ] the activation description distinguishes use from non-use
- [ ] the safety class and its confirmation points match the workflow
- [ ] the license notice exists when the upstream license requires it
- [ ] `PROVENANCE.json` exists and `provenance.py verify` reports OK
- [ ] Progress.md, the validation matrix and the risk register are final
- [ ] the final status is one of DONE / DONE_WITH_LIMITATIONS /
      DONE_UNVERIFIED / NO_VIABLE_SKILL / BLOCKED
