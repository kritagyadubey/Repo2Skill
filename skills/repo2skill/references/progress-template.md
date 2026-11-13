# Progress - <skill-name>

Copy this file into the workspace as `Progress.md` before step 1 and keep it
current. It is the only state a fresh agent reads to resume.

## 0. Resume header

- Objective:
- Repository URL:
- Repository ref requested:
- Pinned commit (full SHA):
- Branch:
- Fetch timestamp:
- Repository type:
- License class:
- Skill name:
- Target agent:
- Capability level (FULL / STANDARD / STATIC_ONLY):
- Isolation level (L0-L3):
- Status:
- Current phase:
- Last updated:
- Last verified state:
- NEXT ACTION (one atomic step):
- Exact sanity-check command:
- Workspace:
- Source modification policy: READ_ONLY
- Blockers:

## 1. Phase checklist

| Phase | Name | Status | Completed at | Evidence |
|---|---|---|---|---|
| 0 | Intake | | | |
| 1 | Repository intelligence | | | |
| 2 | Capability choice | | | |
| 3 | Design | | | |
| 4 | Build | | | |
| 5 | Validation | | | |
| 6 | Scoring | | | |
| 7 | Hand-off | | | |

## 2. Repository map (summary)

- Identity:
- Architecture:
- Entry points:
- Public interfaces (name | kind | signature | file:line):
- Dependencies (verified versions only):
- Runtime requirements:
- Configuration and precedence:
- External services:
- Side effects:
- Tests and how to run them:
- Complexity hotspots:

## 3. Capability specification

- Name:
- Description (activation text):
- Problem solved:
- Core capability:
- Inputs:
- Outputs:
- Invocation contract:
- Prerequisites:
- When to use:
- When not to use:
- Safety class (S0-S4):
- Side effects:
- Failure modes:
- Human approval points:
- Excluded scope:

## 4. Evidence ledger

| ID | Claim | Evidence type (E1-E6) | Source | Confidence |
|---|---|---|---|---|
| C-001 | | | | |

Evidence types: E1 executed output, E2 test result, E3 source `path:line @ SHA`,
E4 repository docs, E5 external docs with retrieval date, E6 inference.

## 5. Decisions and assumptions

| ID | Decision or assumption | Reason | Evidence | Reversible? |
|---|---|---|---|---|
| A-001 | | | | |

## 6. File manifest

| Path | Purpose | Status | Validation |
|---|---|---|---|
| | | | |

## 7. Validation matrix

| Test | Layer (A-H) | Command or method | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|---|
| | | | | | | |

Statuses: PASS, FAIL, BLOCKED, NOT_APPLICABLE (with a one-line reason).

## 8. Risks and open questions

| Risk or question | Severity | Likelihood | Mitigation or required input | Status |
|---|---|---|---|---|
| | | | | |

## 9. Execution log (append-only)

| Timestamp | Phase | Event | Action | Result | Next atomic action |
|---|---|---|---|---|---|
| | | | | | |

## 10. Resume rule

Trust the workspace over the notes. If Progress.md claims something the
workspace does not show, treat it as not done: re-check the pinned SHA, compare
the file manifest with the files on disk, re-run the recorded sanity check, and
continue from NEXT ACTION without repeating finished phases.
