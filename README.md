# repo2skill

Turn any repository into an Agent Skill your AI agent can actually operate:
pinned to a commit, backed by evidence, and auditable for drift.

`repo2skill` is itself a skill. You install it once, then point your agent at
any repository.

## Install (30 seconds)

```bash
git clone https://github.com/<owner>/repo2skill
cd repo2skill
```

Then ask your agent, from inside the cloned repository:

> Install the repo2skill skill from this repository. Follow INSTALL.md.

The agent reads `INSTALL.md`, copies `skills/repo2skill/` to the right place for
that agent, validates the copy, and tells you where it landed. If your agent
cannot install skills itself, the manual step for Claude Code is:

```bash
mkdir -p ~/.claude/skills
cp -r skills/repo2skill ~/.claude/skills/
```

## Use

Ask for a skill, pointing at any repository:

> Use repo2skill to convert https://github.com/owner/repo into a usable skill.

Later, once upstream moves:

> Use repo2skill to audit the skill you built for owner/repo.

## What you get from each run

```
out/<skill-name>/
  SKILL.md              the operating contract another agent follows
  README.md             short human-facing summary
  PROVENANCE.json       repo URL, pinned SHA, license, hashes of every file
  LICENSE-NOTICE.md     only when the upstream license requires attribution
  references/           deep knowledge: API, config, workflows, gotchas
  scripts/              deterministic helpers that were actually run
  tests/                fixtures and a validation harness
```

Plus, in the workspace: `Progress.md` (resumable state), a validation matrix, a
risk register and the evidence ledger.

## What makes it different

- **Repository text is data, not instructions.** READMEs, comments, `AGENTS.md`
  and issues are treated as untrusted; injection attempts become findings.
- **Read-only source, pinned commit.** Analysis happens on an exact SHA, and
  builds or tests run in a copy. The audit proves the clone is unchanged.
- **Evidence or `[UNVERIFIED]`.** Every technical claim carries an evidence ID
  (`path:line @ sha`, a command and its exit code, or an explicit inference).
- **Honest statuses.** Including `DONE_UNVERIFIED` and `NO_VIABLE_SKILL`. The
  workflow is allowed to conclude a repository is not worth turning into a skill.
- **License gate.** Permissive licenses allow short attributed snippets;
  copyleft, unlicensed and proprietary repositories are referenced only.
- **Drift audit.** Hash every file, compare the pinned SHA with upstream, and
  list the changed upstream files your skill depends on.

## Requirements

- `git`
- Python 3.9 or newer (standard library only - nothing to install)
- an agent that can read/write files and run commands in your workspace

## Layout

```
repo2skill/
  README.md
  INSTALL.md
  LICENSE
  skills/repo2skill/
    SKILL.md
    references/           full-spec.txt, progress-template.md, skill-template.md
    scripts/              scan_secrets.py, validate_skill.py,
                          provenance.py, audit_drift.py
  tests/test_scripts.py
  .github/workflows/ci.yml
```

The four scripts are validators, not a compiler. They check structure, scan for
secrets, record provenance and detect drift; the analysis and the writing are
the agent's job.

## Limits

- **Quality depends on the agent.** The skill constrains and verifies, it does
  not think for the model.
- **No execution, no proof.** An agent without a shell can only produce
  `DONE_UNVERIFIED`: scripts are written, never run.
- **No fresh sub-agent, no cold-start claim.** Without one, cold-start testing is
  labelled `SELF_SIMULATED`.
- **Repositories needing GPUs, paid APIs or credentials** end with `BLOCKED`
  tests rather than invented successes.
- **Very large or monorepo upstreams** are analysed on the core path only; the
  exclusion is recorded, never hidden.
- **Install flows are documented, not universal.** Only the paths written in
  `INSTALL.md` for Claude Code follow a published convention; other agents must
  be located by the user.

## License

MIT. See [LICENSE](LICENSE).
