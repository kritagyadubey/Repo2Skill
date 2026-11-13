#!/usr/bin/env python3
"""Create or verify PROVENANCE.json for a skill package.

PROVENANCE.json records where a generated Skill came from (repository URL,
pinned commit SHA, license, creation time, engine version, Python version, the
repository paths the Skill references) and a sha256 hash for every file in the
package. A later drift audit compares the two.

Usage:
    python provenance.py create <skill_dir> --repo-url URL --sha SHA
                              [--license NAME] [--ref-path PATH ...]
    python provenance.py verify <skill_dir>

Exit codes:
    0  ok / all recorded hashes match
    1  mismatch (CHANGED, MISSING or NEW files reported)
    2  usage or environment error
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import sys

ENGINE_VERSION = "V3"
PROVENANCE_NAME = "PROVENANCE.json"
SKIP_DIRS = {"__pycache__"}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_hashes(skill_dir):
    """Return {relative_path: sha256} for every file in the package."""
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
            except OSError as exc:
                sys.stderr.write("warning: cannot hash %s: %s\n" % (rel, exc))
    return dict(sorted(files.items()))


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, path)


def load_provenance(skill_dir):
    path = os.path.join(skill_dir, PROVENANCE_NAME)
    if not os.path.isfile(path):
        return None, "no %s in %s" % (PROVENANCE_NAME, skill_dir)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except (OSError, ValueError) as exc:
        return None, "cannot read %s: %s" % (PROVENANCE_NAME, exc)


def cmd_create(args):
    if not os.path.isdir(args.skill_dir):
        sys.stderr.write("error: not a directory: %s\n" % args.skill_dir)
        return 2
    data = {
        "engine_version": ENGINE_VERSION,
        "repo_url": args.repo_url,
        "pinned_sha": args.sha,
        "license": args.license or "unknown",
        "created_utc": now_utc(),
        "python_version": platform.python_version(),
        "referenced_repo_paths": sorted(set(args.ref_path or [])),
        "files": collect_hashes(args.skill_dir),
    }
    path = os.path.join(args.skill_dir, PROVENANCE_NAME)
    write_atomic(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    sys.stdout.write("WROTE %s (%d file(s) hashed)\n" % (path, len(data["files"])))
    return 0


def cmd_verify(args):
    if not os.path.isdir(args.skill_dir):
        sys.stderr.write("error: not a directory: %s\n" % args.skill_dir)
        return 2
    data, error = load_provenance(args.skill_dir)
    if error:
        sys.stderr.write("error: %s\n" % error)
        return 2
    recorded = data.get("files") or {}
    actual = collect_hashes(args.skill_dir)

    changed = sorted(p for p in recorded if p in actual and actual[p] != recorded[p])
    missing = sorted(p for p in recorded if p not in actual)
    new = sorted(p for p in actual if p not in recorded)

    sys.stdout.write(
        "INFO: repo_url=%s pinned_sha=%s\n"
        % (data.get("repo_url", "?"), data.get("pinned_sha", "?"))
    )
    for path in changed:
        sys.stdout.write("CHANGED: %s\n" % path)
    for path in missing:
        sys.stdout.write("MISSING: %s\n" % path)
    for path in new:
        sys.stdout.write("NEW: %s\n" % path)

    if changed or missing or new:
        sys.stdout.write(
            "RESULT: MISMATCH (%d changed, %d missing, %d new)\n"
            % (len(changed), len(missing), len(new))
        )
        return 1
    sys.stdout.write("RESULT: OK (%d file(s) match)\n" % len(recorded))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="provenance.py",
        description="Create or verify PROVENANCE.json for a skill package.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="{create,verify}")
    subparsers.required = True

    create = subparsers.add_parser("create", help="write PROVENANCE.json")
    create.add_argument("skill_dir", help="skill package directory")
    create.add_argument("--repo-url", required=True, help="repository URL or local path")
    create.add_argument("--sha", required=True, help="pinned commit SHA")
    create.add_argument("--license", default="unknown", help="license name or class")
    create.add_argument(
        "--ref-path",
        action="append",
        default=[],
        help="repository path referenced by the skill (repeatable)",
    )
    create.set_defaults(func=cmd_create)

    verify = subparsers.add_parser("verify", help="verify recorded hashes")
    verify.add_argument("skill_dir", help="skill package directory")
    verify.set_defaults(func=cmd_verify)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
