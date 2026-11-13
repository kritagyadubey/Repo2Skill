"""Tests for the repo2skill engine scripts. Standard library only, offline."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO_ROOT, "skills", "repo2skill", "scripts")

# Assembled at runtime so that this test file never contains a literal key.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPL3"


def write(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def run_script(name, *args):
    command = [sys.executable, os.path.join(SCRIPTS, name)] + [str(a) for a in args]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )


def git(cwd, *args):
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "repo2skill tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "repo2skill tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
        }
    )
    return subprocess.run(
        ["git", "-C", cwd] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="repo2skill-")
        self.addCleanup(shutil.rmtree, self.tmp, True)


class ScanSecretsTests(TempDirTest):
    def test_clean_directory_passes(self):
        write(os.path.join(self.tmp, "notes.txt"), "nothing to see here\n")
        result = run_script("scan_secrets.py", self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: clean", result.stdout)

    def test_planted_key_is_found_and_value_is_redacted(self):
        write(
            os.path.join(self.tmp, "settings.py"),
            'aws_access_key_id = "%s"\n' % FAKE_AWS_KEY,
        )
        result = run_script("scan_secrets.py", self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("aws-access-key-id", result.stdout)
        self.assertIn("settings.py:1:", result.stdout)
        combined = result.stdout + result.stderr
        self.assertNotIn(FAKE_AWS_KEY, combined)

    def test_binary_and_vcs_directories_are_skipped(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        write(os.path.join(self.tmp, ".git", "config.txt"), 'password = "%s"\n' % ("z" * 24))
        write(os.path.join(self.tmp, "blob.bin"), "")
        with open(os.path.join(self.tmp, "blob.bin"), "wb") as handle:
            handle.write(b"\x00\x01\x02password=" + b"q" * 24)
        result = run_script("scan_secrets.py", self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_path_returns_usage_error(self):
        result = run_script("scan_secrets.py", os.path.join(self.tmp, "absent"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


class ValidateSkillTests(TempDirTest):
    def make_skill(self, name="demo-skill", description="A demo skill used by tests.", body=None):
        root = os.path.join(self.tmp, "skill")
        body = "# Demo\n\nOne body line.\n" if body is None else body
        write(
            os.path.join(root, "SKILL.md"),
            "---\nname: %s\ndescription: %s\n---\n\n%s" % (name, description, body),
        )
        return root

    def test_valid_skill_passes_with_warnings(self):
        root = self.make_skill()
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)
        self.assertIn("README.md is missing", result.stdout)
        self.assertIn("PROVENANCE.json is missing", result.stdout)

    def test_invalid_name_fails(self):
        root = self.make_skill(name="Demo_Skill")
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL", result.stdout)
        self.assertIn("must match", result.stdout)

    def test_broken_link_fails(self):
        root = self.make_skill(body="# Demo\n\n[ref](references/missing.md)\n")
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("broken link", result.stdout)

    def test_resolving_link_passes(self):
        root = self.make_skill(body="# Demo\n\n[ref](references/notes.md)\n")
        write(os.path.join(root, "references", "notes.md"), "# Notes\n")
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_description_over_limit_fails(self):
        root = self.make_skill(description="x" * 1100)
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("description", result.stdout)

    def test_missing_frontmatter_fails(self):
        root = os.path.join(self.tmp, "skill")
        write(os.path.join(root, "SKILL.md"), "# no frontmatter\n")
        result = run_script("validate_skill.py", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_missing_directory_returns_usage_error(self):
        result = run_script("validate_skill.py", os.path.join(self.tmp, "absent"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


class ProvenanceTests(TempDirTest):
    def make_package(self):
        root = os.path.join(self.tmp, "skill")
        write(os.path.join(root, "SKILL.md"), "---\nname: demo\ndescription: demo\n---\n")
        write(os.path.join(root, "references", "notes.md"), "# Notes\n")
        return root

    def create(self, root):
        return run_script(
            "provenance.py",
            "create",
            root,
            "--repo-url",
            "https://example.invalid/owner/repo",
            "--sha",
            "0" * 40,
            "--license",
            "MIT",
            "--ref-path",
            "src/core.py",
        )

    def test_create_then_verify_passes(self):
        root = self.make_package()
        created = self.create(root)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        self.assertTrue(os.path.isfile(os.path.join(root, "PROVENANCE.json")))
        with open(os.path.join(root, "PROVENANCE.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["pinned_sha"], "0" * 40)
        self.assertEqual(data["engine_version"], "V3")
        self.assertEqual(data["license"], "MIT")
        self.assertEqual(data["referenced_repo_paths"], ["src/core.py"])
        self.assertIn("created_utc", data)
        self.assertIn("python_version", data)
        self.assertIn("SKILL.md", data["files"])
        self.assertIn("references/notes.md", data["files"])
        self.assertNotIn("PROVENANCE.json", data["files"])

        verified = run_script("provenance.py", "verify", root)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertIn("RESULT: OK", verified.stdout)

    def test_modified_file_is_reported_changed(self):
        root = self.make_package()
        self.assertEqual(self.create(root).returncode, 0)
        write(os.path.join(root, "references", "notes.md"), "# Notes changed\n")
        result = run_script("provenance.py", "verify", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CHANGED: references/notes.md", result.stdout)

    def test_new_file_is_reported(self):
        root = self.make_package()
        self.assertEqual(self.create(root).returncode, 0)
        write(os.path.join(root, "extra.md"), "# Extra\n")
        result = run_script("provenance.py", "verify", root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("NEW: extra.md", result.stdout)

    def test_missing_provenance_returns_usage_error(self):
        root = self.make_package()
        result = run_script("provenance.py", "verify", root)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_create_requires_sha(self):
        root = self.make_package()
        result = run_script(
            "provenance.py", "create", root, "--repo-url", "https://example.invalid/x"
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


class AuditDriftTests(TempDirTest):
    def make_upstream(self):
        repo = os.path.join(self.tmp, "upstream")
        os.makedirs(os.path.join(repo, "src"))
        write(os.path.join(repo, "src", "core.py"), "def core():\n    return 1\n")
        write(os.path.join(repo, "README.md"), "# Upstream\n")
        self.assertEqual(git(repo, "init", "-q").returncode, 0)
        self.assertEqual(git(repo, "add", "-A").returncode, 0)
        commit = git(repo, "commit", "-q", "-m", "initial")
        self.assertEqual(commit.returncode, 0, commit.stderr)
        sha = git(repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(len(sha), 40)
        return repo, sha

    def make_package(self, repo, sha):
        skill = os.path.join(self.tmp, "skill")
        write(os.path.join(skill, "SKILL.md"), "---\nname: demo\ndescription: demo\n---\n")
        write(os.path.join(skill, "references", "notes.md"), "# Notes\n")
        created = run_script(
            "provenance.py",
            "create",
            skill,
            "--repo-url",
            repo,
            "--sha",
            sha,
            "--license",
            "MIT",
            "--ref-path",
            "src/core.py",
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        return skill

    def test_current_when_upstream_is_unchanged(self):
        repo, sha = self.make_upstream()
        skill = self.make_package(repo, sha)
        result = run_script("audit_drift.py", skill, "--repo-path", repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STATUS: CURRENT", result.stdout)

    def test_drift_lists_the_referenced_file(self):
        repo, sha = self.make_upstream()
        skill = self.make_package(repo, sha)
        write(os.path.join(repo, "src", "core.py"), "def core():\n    return 2\n")
        self.assertEqual(git(repo, "add", "-A").returncode, 0)
        commit = git(repo, "commit", "-q", "-m", "change core")
        self.assertEqual(commit.returncode, 0, commit.stderr)

        result = run_script("audit_drift.py", skill, "--repo-path", repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("STATUS: DRIFT", result.stdout)
        self.assertIn("src/core.py", result.stdout)
        self.assertIn("[REFERENCED: src/core.py]", result.stdout)

    def test_tampered_package_is_drift(self):
        repo, sha = self.make_upstream()
        skill = self.make_package(repo, sha)
        write(os.path.join(skill, "references", "notes.md"), "# tampered\n")
        result = run_script("audit_drift.py", skill, "--repo-path", repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CHANGED: references/notes.md", result.stdout)
        self.assertIn("STATUS: DRIFT", result.stdout)

    def test_unreachable_upstream_returns_environment_error(self):
        skill = os.path.join(self.tmp, "skill")
        write(os.path.join(skill, "SKILL.md"), "---\nname: demo\ndescription: demo\n---\n")
        missing = os.path.join(self.tmp, "no-such-repo")
        created = run_script(
            "provenance.py", "create", skill, "--repo-url", missing, "--sha", "1" * 40
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        result = run_script("audit_drift.py", skill)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("STATUS: CURRENT", result.stdout)

    def test_missing_package_returns_usage_error(self):
        result = run_script("audit_drift.py", os.path.join(self.tmp, "absent"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
