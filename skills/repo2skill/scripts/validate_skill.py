#!/usr/bin/env python3
"""Validate the structure of an Agent Skill directory.

Checks performed:
    * SKILL.md exists and starts with a parseable YAML frontmatter block.
    * frontmatter 'name' matches ^[a-z0-9]+(-[a-z0-9]+)*$ and is <= 64 chars.
    * frontmatter 'description' is non-empty and <= 1024 chars.
    * the markdown body is <= 500 lines (warning above 400).
    * relative markdown links in the body resolve on disk.
    * README.md and PROVENANCE.json exist (warnings only - a skill that was
      just generated may not have them yet).
    * reports how many [UNVERIFIED] tags the SKILL.md carries.

Usage:
    python validate_skill.py <skill_dir>

Exit codes:
    0  pass (warnings allowed)
    1  one or more failures
    2  usage or input error
"""

import argparse
import os
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
SKIPPED_LINK_PREFIXES = ("#", "http://", "https://", "mailto:", "tel:", "<")
MAX_BODY_LINES = 500
TARGET_BODY_LINES = 400
MAX_DESCRIPTION = 1024
MAX_NAME = 64


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def split_frontmatter(lines):
    """Return (frontmatter_lines or None, body_lines, errors)."""
    if not lines:
        return None, [], ["SKILL.md is empty"]
    if lines[0].strip() != "---":
        return None, lines, ["SKILL.md must start with a '---' frontmatter line"]
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], lines[index + 1:], []
    return None, lines, ["frontmatter was opened with '---' but never closed"]


def parse_meta(frontmatter):
    """Parse the small subset of YAML the frontmatter needs.

    Supports 'key: value', quoted values, simple indented continuation lines and
    the folded/literal block markers '>' and '|'.
    """
    meta = {}
    errors = []
    state = {"key": None, "sep": None, "parts": None}

    def finish():
        key = state["key"]
        if key is not None and state["parts"] is not None:
            joined = state["sep"].join(state["parts"]).strip()
            meta[key] = joined if joined else meta.get(key, "")
        state["key"] = None
        state["sep"] = None
        state["parts"] = None

    for raw in frontmatter:
        if not raw.strip():
            continue
        indented = raw[:1] in (" ", "\t")
        stripped = raw.strip()
        if indented and state["key"] is not None:
            if state["parts"] is not None:
                state["parts"].append(stripped)
            else:
                meta[state["key"]] = (meta.get(state["key"], "") + " " + stripped).strip()
            continue
        finish()
        if ":" not in stripped:
            errors.append("unparsable frontmatter line: %r" % stripped[:80])
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append("frontmatter line with an empty key: %r" % stripped[:80])
            continue
        state["key"] = key
        if value in (">", ">-", ">+", "|", "|-", "|+"):
            state["sep"] = " " if value.startswith(">") else "\n"
            state["parts"] = []
            meta[key] = ""
        else:
            meta[key] = unquote(value)
            state["sep"] = None
            state["parts"] = None
    finish()
    return meta, errors


def check_links(body_lines, skill_dir, failures):
    for lineno, line in enumerate(body_lines, 1):
        for match in LINK_RE.finditer(line):
            target = match.group(1).strip()
            if not target or target.startswith(SKIPPED_LINK_PREFIXES):
                continue
            if "{{" in target or "}}" in target:
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            resolved = os.path.normpath(os.path.join(skill_dir, path))
            if not os.path.exists(resolved):
                failures.append("broken link at body line %d: %s" % (lineno, target))


def validate(skill_dir, out=None):
    """Validate skill_dir and return (exit_code, stats)."""
    out = out or sys.stdout
    failures = []
    warnings = []

    if not os.path.isdir(skill_dir):
        out.write("FAIL: not a directory: %s\n" % skill_dir)
        out.write("RESULT: FAIL (1 failure, 0 warnings)\n")
        return 2, {}

    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        out.write("FAIL: SKILL.md is missing from %s\n" % skill_dir)
        out.write("RESULT: FAIL (1 failure, 0 warnings)\n")
        return 1, {}

    with open(skill_md, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read().lstrip("\ufeff")
    lines = text.splitlines()

    frontmatter, body, errors = split_frontmatter(lines)
    failures.extend(errors)
    meta = {}
    if frontmatter is not None:
        meta, meta_errors = parse_meta(frontmatter)
        failures.extend(meta_errors)

    name = (meta.get("name") or "").strip()
    if not name:
        failures.append("frontmatter 'name' is missing or empty")
    elif not NAME_RE.match(name):
        failures.append("name %r must match ^[a-z0-9]+(-[a-z0-9]+)*$" % name)
    elif len(name) > MAX_NAME:
        failures.append("name is %d chars (max %d)" % (len(name), MAX_NAME))

    description = (meta.get("description") or "").strip()
    if not description:
        failures.append("frontmatter 'description' is missing or empty")
    elif len(description) > MAX_DESCRIPTION:
        failures.append(
            "description is %d chars (max %d)" % (len(description), MAX_DESCRIPTION)
        )

    extra = sorted(set(meta) - {"name", "description"})
    if extra:
        warnings.append("unexpected frontmatter keys: %s" % ", ".join(extra))

    body_lines = len(body)
    if body_lines > MAX_BODY_LINES:
        failures.append("body is %d lines (hard limit %d)" % (body_lines, MAX_BODY_LINES))
    elif body_lines > TARGET_BODY_LINES:
        warnings.append("body is %d lines (target %d)" % (body_lines, TARGET_BODY_LINES))

    check_links(body, skill_dir, failures)

    if not os.path.isfile(os.path.join(skill_dir, "README.md")):
        warnings.append("README.md is missing (warning only; expected for the engine skill itself)")
    if not os.path.isfile(os.path.join(skill_dir, "PROVENANCE.json")):
        warnings.append(
            "PROVENANCE.json is missing (warning only; expected for the engine skill itself)"
        )

    unverified = text.count("[UNVERIFIED]")

    for item in failures:
        out.write("FAIL: %s\n" % item)
    for item in warnings:
        out.write("WARN: %s\n" % item)
    out.write(
        "INFO: body lines=%d, description chars=%d, [UNVERIFIED] tags=%d\n"
        % (body_lines, len(description), unverified)
    )
    out.write(
        "RESULT: %s (%d failure(s), %d warning(s))\n"
        % ("FAIL" if failures else "PASS", len(failures), len(warnings))
    )
    stats = {
        "name": name,
        "body_lines": body_lines,
        "description_chars": len(description),
        "unverified": unverified,
        "failures": len(failures),
        "warnings": len(warnings),
    }
    return (1 if failures else 0), stats


def build_parser():
    parser = argparse.ArgumentParser(
        prog="validate_skill.py",
        description="Validate the structure and frontmatter of an Agent Skill directory.",
    )
    parser.add_argument("skill_dir", help="directory containing SKILL.md")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    code, _stats = validate(args.skill_dir)
    return code


if __name__ == "__main__":
    sys.exit(main())
