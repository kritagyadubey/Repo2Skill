#!/usr/bin/env python3
"""Audit a generated skill package for drift against its upstream repository.

The audit does three things:
    1. Verifies the local package against the hashes in PROVENANCE.json.
    2. Compares the pinned commit SHA with the current upstream commit
       (git ls-remote, or the HEAD of the clone given with --repo-path).
    3. With --repo-path, lists the files changed upstream between the pinned
       SHA and upstream HEAD and highlights the ones the Skill references.

Nothing is modified. Upstream is only read.

Usage:
    python audit_drift.py <skill_dir> [--repo-path CLONE] [--ref REF]

Exit codes:
    0  CURRENT  - package intact and upstream unchanged
    1  DRIFT    - upstream moved or the local package was modified
    2  usage or environment error (for example upstream unreachable). Current
       status is never reported when upstream could not be checked.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

PROVENANCE_NAME = "PROVENANCE.json"
SKIP_DIRS = {"__pycache__"}
GIT_TIMEOUT = 120


class EnvironmentProblem(Exception):
    """Raised when the upstream or the local environment cannot be inspected."""


def run_git(args, cwd=None):
    command = ["git"] + list(args)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise EnvironmentProblem("git executable not found on PATH")
    except subprocess.TimeoutExpired:
        raise EnvironmentProblem("git timed out after %d seconds" % GIT_TIMEOUT)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def last_line(text):
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "(no output)"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_hashes(skill_dir):
    files = {}
    root = os.path.abspath(skill_dir)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == PROVENANCE_NAME:
                continue
            try:
                files[rel] = sha256_file(full)
            except OSError:
                continue
    return files


def load_provenance(skill_dir):
    path = os.path.join(skill_dir, PROVENANCE_NAME)
    if not os.path.isfile(path):
        raise EnvironmentProblem("no %s in %s" % (PROVENANCE_NAME, skill_dir))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise EnvironmentProblem("cannot read %s: %s" % (PROVENANCE_NAME, exc))
    if not (data.get("pinned_sha") or "").strip():
        raise EnvironmentProblem("%s has no pinned_sha" % PROVENANCE_NAME)
    return data


def verify_local(skill_dir, data):
    """Print CHANGED/MISSING/NEW lines. Return True when the package drifted."""
    recorded = data.get("files") or {}
    actual = collect_hashes(skill_dir)
    changed = sorted(p for p in recorded if p in actual and actual[p] != recorded[p])
    missing = sorted(p for p in recorded if p not in actual)
    new = sorted(p for p in actual if p not in recorded)
    for path in changed:
        sys.stdout.write("CHANGED: %s\n" % path)
    for path in missing:
        sys.stdout.write("MISSING: %s\n" % path)
    for path in new:
        sys.stdout.write("NEW: %s\n" % path)
    if not (changed or missing or new):
        sys.stdout.write("INFO: local package matches PROVENANCE.json (%d file(s))\n" % len(recorded))
    return bool(changed or missing or new)


def resolve_upstream(args, data):
    """Return (upstream_sha, clone_path_or_None) or raise EnvironmentProblem."""
    if args.repo_path:
        clone = args.repo_path
        if not os.path.isdir(clone):
            raise EnvironmentProblem("--repo-path is not a directory: %s" % clone)
        code, _out, _err = run_git(["-C", clone, "rev-parse", "--git-dir"])
        if code != 0:
            raise EnvironmentProblem("--repo-path is not a git repository: %s" % clone)
        code, out, _err = run_git(["-C", clone, "remote"])
        if "origin" in out.split():
            code, _out, err = run_git(["-C", clone, "fetch", "--quiet", "origin"])
            if code != 0:
                raise EnvironmentProblem(
                    "upstream unreachable: 'git fetch origin' failed in %s: %s"
                    % (clone, last_line(err))
                )
        code, out, err = run_git(["-C", clone, "rev-parse", "HEAD"])
        if code != 0:
            raise EnvironmentProblem("cannot resolve HEAD in %s: %s" % (clone, last_line(err)))
        return out.strip(), clone

    url = (data.get("repo_url") or "").strip()
    if not url:
        raise EnvironmentProblem("%s has no repo_url" % PROVENANCE_NAME)
    ref = args.ref or "HEAD"
    code, out, err = run_git(["ls-remote", url, ref])
    if code != 0:
        raise EnvironmentProblem(
            "upstream unreachable: 'git ls-remote %s %s' failed: %s" % (url, ref, last_line(err))
        )
    tokens = out.split()
    if not tokens:
        raise EnvironmentProblem("upstream has no commit for ref %r" % ref)
    return tokens[0], None


def changed_files(clone, pinned, upstream):
    """Return [(status, path)] between two commits, or None when undiffable."""
    for spec in ("%s..%s" % (pinned, upstream), "%s %s" % (pinned, upstream)):
        code, out, _err = run_git(["-C", clone, "diff", "--name-status", spec])
        if code == 0:
            rows = []
            for line in out.splitlines():
                parts = [part for part in line.split("\t") if part.strip()]
                if len(parts) >= 2:
                    rows.append((parts[0].strip(), parts[-1].strip()))
            return rows
    return None


def matching_reference(references, path):
    if not references:
        return None
    for ref in references:
        cleaned = ref.strip().rstrip("/")
        if not cleaned:
            continue
        if path == cleaned or path.startswith(cleaned + "/"):
            return ref
    return None


def build_parser():
    parser = argparse.ArgumentParser(
        prog="audit_drift.py",
        description="Check a generated skill package for drift against its upstream repository.",
    )
    parser.add_argument("skill_dir", help="skill package directory with PROVENANCE.json")
    parser.add_argument("--repo-path", help="local clone of the upstream repository")
    parser.add_argument("--ref", help="upstream ref to compare against (default: HEAD)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if not os.path.isdir(args.skill_dir):
        sys.stderr.write("error: not a directory: %s\n" % args.skill_dir)
        return 2

    try:
        data = load_provenance(args.skill_dir)
        pinned = data["pinned_sha"].strip()
        sys.stdout.write("INFO: repo_url=%s\n" % data.get("repo_url", "?"))
        sys.stdout.write("INFO: pinned_sha=%s\n" % pinned)
        local_drift = verify_local(args.skill_dir, data)
        upstream, clone = resolve_upstream(args, data)
    except EnvironmentProblem as exc:
        sys.stderr.write("error: %s\n" % exc)
        sys.stdout.write("STATUS: UNKNOWN (upstream not checked - not reported as CURRENT)\n")
        return 2

    sys.stdout.write("INFO: upstream_sha=%s\n" % upstream)
    reasons = []
    if pinned != upstream:
        reasons.append("upstream moved since the pinned commit")
    if local_drift:
        reasons.append("local package does not match PROVENANCE.json")

    if pinned != upstream:
        if clone:
            rows = changed_files(clone, pinned, upstream)
            if rows is None:
                sys.stdout.write(
                    "WARN: could not diff %s..%s in the clone (pinned commit missing?)\n"
                    % (pinned[:12], upstream[:12])
                )
            else:
                references = data.get("referenced_repo_paths") or []
                sys.stdout.write("CHANGED FILES (%d):\n" % len(rows))
                for status, path in rows:
                    ref = matching_reference(references, path)
                    marker = " [REFERENCED: %s]" % ref if ref else ""
                    sys.stdout.write("  %-8s %s%s\n" % (status, path, marker))
                hits = [p for _s, p in rows if matching_reference(references, p)]
                if references and not hits:
                    sys.stdout.write(
                        "INFO: no changed file intersects the referenced paths (%d checked)\n"
                        % len(references)
                    )
        else:
            sys.stdout.write(
                "INFO: pass --repo-path to list changed files; only the SHAs were compared\n"
            )

    if reasons:
        for reason in reasons:
            sys.stdout.write("REASON: %s\n" % reason)
        sys.stdout.write("STATUS: DRIFT\n")
        return 1

    sys.stdout.write("STATUS: CURRENT\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
