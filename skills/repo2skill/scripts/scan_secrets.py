#!/usr/bin/env python3
"""Scan a file or a directory tree for secret-like strings.

Usage:
    python scan_secrets.py <path>

Each finding is printed as:

    <path>:<line>:<type>: <redacted value>

The secret VALUE is always redacted to at most its first two and last two
characters. Key names and type labels are not redacted. The raw value is never
printed, logged, or written anywhere.

Binary files, files larger than MAX_BYTES, and well-known dependency or VCS
directories are skipped.

Exit codes:
    0  clean - no findings
    1  findings were reported
    2  usage or input error
"""

import argparse
import os
import re
import sys

MAX_BYTES = 1000000
BINARY_HEAD = 8192

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "virtualenv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", "site-packages", ".idea", ".vscode",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".zip", ".gz", ".bz2", ".xz",
    ".7z", ".tar", ".pdf", ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".bin", ".jar", ".whl", ".class", ".o", ".a", ".woff", ".woff2", ".ttf",
    ".eot", ".sqlite", ".db",
}

PATTERNS = [
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,255}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("openai-style-key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,255}\b")),
    ("private-key-header", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
]

GENERIC_RE = re.compile(
    r"(?i)\b(api[_-]?key|apikey|secret|client[_-]?secret|password|passwd|"
    r"token|auth[_-]?token|access[_-]?key|private[_-]?key)\b\s*[:=]\s*"
    r"[\"']?([A-Za-z0-9_.\-+=/]{16,})[\"']?"
)

PLACEHOLDER_HINTS = (
    "your", "example", "sample", "placeholder", "replace", "changeme",
    "xxxx", "dummy", "redacted", "todo", "required", "none", "null",
    "***", "...", "env[", "getenv",
)


def redact(value):
    """Return a value that can never be mistaken for the original secret."""
    n = len(value)
    if n == 0:
        return ""
    if n == 1:
        return "*"
    if n == 2:
        return value[0] + "*"
    if n <= 8:
        return value[0] + "*" * (n - 2) + value[-1]
    return value[:2] + "*" * (n - 4) + value[-2:]


def looks_placeholder(value):
    low = value.lower()
    if "{{" in value or "}}" in value:
        return True
    if value[0] in "$<%" or value.startswith("os.environ"):
        return True
    for hint in PLACEHOLDER_HINTS:
        if hint in low:
            return True
    if len(set(low)) <= 2:
        return True
    return False


def iter_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def read_text(path):
    """Return the file's text, or None when the file must be skipped."""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
    except OSError:
        return None
    if os.path.splitext(path)[1].lower() in SKIP_EXTENSIONS:
        return None
    try:
        with open(path, "rb") as handle:
            head = handle.read(BINARY_HEAD)
            if b"\x00" in head:
                return None
            rest = handle.read()
    except OSError:
        return None
    try:
        return (head + rest).decode("utf-8", "replace")
    except Exception:  # pragma: no cover - decode is already lossy
        return None


def scan_text(text, path, findings):
    for lineno, line in enumerate(text.splitlines(), 1):
        specific = False
        for kind, pattern in PATTERNS:
            for match in pattern.finditer(line):
                specific = True
                findings.append((path, lineno, kind, redact(match.group(0))))
        if specific:
            continue
        for match in GENERIC_RE.finditer(line):
            value = match.group(2)
            if looks_placeholder(value):
                continue
            kind = "generic-assignment(%s)" % match.group(1).lower()
            findings.append((path, lineno, kind, redact(value)))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="scan_secrets.py",
        description="Scan a file or directory for secret-like strings (values are redacted).",
    )
    parser.add_argument("path", help="file or directory to scan")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_BYTES,
        help="skip files larger than this many bytes (default: %(default)s)",
    )
    return parser


def main(argv=None):
    global MAX_BYTES
    parser = build_parser()
    args = parser.parse_args(argv)
    MAX_BYTES = args.max_bytes

    if not os.path.exists(args.path):
        sys.stderr.write("error: path does not exist: %s\n" % args.path)
        return 2

    findings = []
    scanned = 0
    skipped = 0
    for path in iter_files(args.path):
        text = read_text(path)
        if text is None:
            skipped += 1
            continue
        scanned += 1
        scan_text(text, path, findings)

    for path, lineno, kind, masked in findings:
        sys.stdout.write("%s:%d:%s: %s\n" % (path, lineno, kind, masked))

    if findings:
        files = len({item[0] for item in findings})
        sys.stdout.write(
            "RESULT: %d finding(s) in %d file(s) (scanned %d, skipped %d)\n"
            % (len(findings), files, scanned, skipped)
        )
        return 1

    sys.stdout.write(
        "RESULT: clean, no findings (scanned %d, skipped %d)\n" % (scanned, skipped)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
