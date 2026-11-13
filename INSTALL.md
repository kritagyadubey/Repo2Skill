# INSTALL

Instructions for the AI agent that is installing `repo2skill`. Read all of this
before running anything. The user's request was: "Install the repo2skill skill
from this repository. Follow INSTALL.md."

You are installing a skill folder. You are not running a project, a build, or a
test suite.

## 1. Confirm the source

1. Locate `skills/repo2skill/` in the repository you were given.
2. Read `skills/repo2skill/SKILL.md` and confirm the frontmatter contains
   `name: repo2skill`. If it does not, stop and tell the user what you found.
3. Do not run anything else from this repository during installation.

## 2. Choose the destination for the agent you are running as

Pick the row that matches your own runtime. Do not guess a directory that is not
listed for your agent.

| Agent | Destination | Status of this row |
|---|---|---|
| Claude Code | `~/.claude/skills/repo2skill/` for personal use, or `<project>/.claude/skills/repo2skill/` to scope it to one project. Ask the user which scope before copying. | Published convention; not exercised in the v1.0.0 build |
| Claude.ai / Claude apps (web, desktop, mobile) | The user uploads `repo2skill-skill-only.zip` (folder `repo2skill/` at the archive root) in Settings, using the skills/plugin upload entry. Tell the user the exact file path to upload. | User-side upload flow; not exercised in the v1.0.0 build |
| Any other agent with a documented skills directory | That agent's documented location only. Read its documentation; if you cannot find it, say so instead of inventing a path. | Unverified - the user must confirm the path |
| An agent with no skills mechanism | Copy the folder to a stable path the user chooses, then add one line to that agent's persistent instruction file (for example `AGENTS.md`): when the user says "use repo2skill", read `<path>/SKILL.md` and follow it. | Works by instruction only; no discovery mechanism |

State which row you used and why. Never describe a row as verified if you did
not observe the files on disk afterwards.

## 3. Copy the whole folder

Copy `skills/repo2skill/` - `SKILL.md`, `references/` and `scripts/` - to the
destination. Copy it as a directory, not as merged files.

If the destination already exists, stop and ask the user whether to replace it.
Do not overwrite an existing installation without permission.

## 4. Verify the installed copy

Run both checks against the **installed** copy, not the repository copy:

```bash
python <destination>/scripts/validate_skill.py <destination>
python <destination>/scripts/scan_secrets.py <destination>
```

Expected results:

- `RESULT: PASS` with exactly two warnings - `README.md is missing` and
  `PROVENANCE.json is missing`. These are expected for the engine skill itself:
  it is not a generated package, so it has no provenance file of its own.
- `RESULT: clean, no findings` from the secret scan.

Report the real output. If `validate_skill.py` reports a `FAIL`, or the scan
reports findings, the copy is wrong: say which check failed and give the manual
command the user can run.

## 5. Confirm to the user

Tell the user, in plain language:

1. Where the skill was installed, and which row of the table you used.
2. Whether verification passed, quoting the two `RESULT:` lines.
3. Whether a restart or reload is needed for the agent to pick up the skill.
4. An example prompt to use next:
   `Use repo2skill to convert https://github.com/owner/repo into a usable skill.`

## 6. Failure handling

Never claim success unless the files are in place and step 4 passed.

- If a step fails, name the step, quote the error, and give the exact manual
  command that would complete it.
- If Python is unavailable, the copy in step 3 is still valid; say verification
  could not run and give the command for the user to run later.
- If you cannot determine the destination for your own runtime, stop at step 2
  and ask the user for the path. That is the correct outcome, not a failure.

## Notes

- The engine skill has no `PROVENANCE.json` and therefore cannot be audited with
  `audit_drift.py`; that script is for the skills the engine generates.
- `references/full-spec.txt` is the complete engine specification. It is
  reference material for the skill, not something to execute.
