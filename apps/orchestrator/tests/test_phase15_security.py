import os
import pytest

from orchestrator.security import scan_for_secrets, enforce_policy
from orchestrator.integrations.github import upsert_pr_summary_comment_for_run, open_pr_for_run


def test_secret_scanner_detects_and_ignores(tmp_path):
    # Unsafe content
    (tmp_path / "unsafe.txt").write_text(
        """
        token = ghp_abcdefghijklmnopqrstuvwxyz1234567890
        AWS_SECRET_ACCESS_KEY=A""" + "A" * 39 + "\n"
        "-----BEGIN PRIVATE KEY-----\n"
        "password=supersecretvalue\n"
    )

    # Safe content
    (tmp_path / "README.md").write_text("This is a readme with no secrets.")

    # Binary content should be ignored
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03\x00\x10\xff")

    # dev.db should be excluded explicitly even if it contains markers
    (tmp_path / "dev.db").write_text("ghp_FAKE_TOKEN_SHOULD_NOT_BE_SCANNED")

    findings = scan_for_secrets(str(tmp_path))
    assert isinstance(findings, list) and len(findings) >= 2
    paths = {f.get("file") for f in findings}
    # Ensure exclusions
    assert not any(str(p).endswith("dev.db") for p in paths)
    assert not any(str(p).endswith("binary.bin") for p in paths)


def test_policy_gate_returns_findings_and_clean_is_empty(tmp_path):
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "leak.txt").write_text("AWS_SECRET_ACCESS_KEY = " + ("B" * 40))

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "notes.txt").write_text("no secrets here")

    bad = enforce_policy(str(dirty))
    good = enforce_policy(str(clean))
    assert isinstance(bad, list) and len(bad) >= 1
    assert good == []


def test_github_writes_gated_by_env(monkeypatch):
    monkeypatch.setenv("GITHUB_WRITE_ENABLED", "0")
    # Should fail fast (skip) without using DB or network
    res1 = upsert_pr_summary_comment_for_run(None, "run-irrelevant")
    assert isinstance(res1, dict) and res1.get("skipped") == "GITHUB_WRITE_ENABLED=0"

    res2 = open_pr_for_run(None, "run-irrelevant")
    assert isinstance(res2, dict) and res2.get("skipped") == "GITHUB_WRITE_ENABLED=0"


