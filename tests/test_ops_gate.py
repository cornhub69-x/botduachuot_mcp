"""Tests for the OPSEC gate and platform adapter."""

from __future__ import annotations

import pytest

import app.config
from app.ops.gate import (
    OpsGateError,
    gate_command,
    gate_remote_request,
    redact_secrets,
    suggest_jitter_seconds,
)
from app.platform import probe_platform, tool_supported, windows_path_to_wsl, wsl_path_to_windows


class TestOpsGate:
    def test_remote_block_telemetry_host(self):
        verdict = gate_remote_request("http://ip-api.com/json", mode="investigation")
        assert verdict["allowed"] is False
        assert verdict["rule"] == "telemetry_host"

    def test_remote_block_forbidden_scope_tool(self):
        verdict = gate_remote_request("sqlmap -u http://target/", mode="investigation")
        assert verdict["allowed"] is False
        assert verdict["rule"] == "forbidden_scope_tool"

    def test_remote_block_discovery_in_ctf_live(self):
        verdict = gate_remote_request("sherlock username", mode="ctf-live")
        assert verdict["allowed"] is False
        assert verdict["rule"] == "public_discovery_ctf_live"

    def test_remote_allowed_in_investigation(self):
        verdict = gate_remote_request("http://example.test/artifact", mode="investigation")
        assert verdict["allowed"] is True

    def test_empty_target_raises(self):
        with pytest.raises(OpsGateError):
            gate_remote_request("", mode="investigation")

    def test_command_block_flag_marker(self):
        verdict = gate_command("echo FLAG{abc123xyz}")
        assert verdict["allowed"] is False
        assert verdict["rule"] == "flag_in_command"

    def test_command_block_telemetry(self):
        verdict = gate_command("curl api.ipify.org", mode="investigation")
        assert verdict["allowed"] is False
        assert verdict["rule"] == "telemetry_host"

    def test_command_allowed_safe(self):
        verdict = gate_command("ls -la /evidence")
        assert verdict["allowed"] is True

    def test_mode_defaults_from_config(self):
        previous = app.config.OSINT_MODE
        app.config.OSINT_MODE = True
        try:
            verdict = gate_command("whois example.com", mode=None)
            assert verdict["allowed"] is True  # investigation mode permits OSINT lookups
            assert verdict["mode"] == "investigation"
        finally:
            app.config.OSINT_MODE = previous


class TestRedact:
    def test_redact_flag(self):
        assert redact_secrets("the flag is FLAG{a1b2c3d4e5f6}") == "the flag is [FLAG_REDACTED]"

    def test_redact_bearer(self):
        assert "TOKEN_REDACTED" in redact_secrets("Authorization: Bearer abcdef1234567890abcdef")

    def test_redact_apikey(self):
        assert "REDACTED" in redact_secrets("api_key=supersecretvalue123456")

    def test_plain_text_untouched(self):
        text = "nothing sensitive here"
        assert redact_secrets(text) == text


class TestJitter:
    def test_jitter_within_config_bounds(self):
        for _ in range(50):
            delay = suggest_jitter_seconds()
            assert app.config.OPSEC_JITTER_MIN_MS / 1000 <= delay <= app.config.OPSEC_JITTER_MAX_MS / 1000


class TestPlatform:
    def test_probe_platform_shape(self):
        probe = probe_platform()
        assert probe["os"] in {"linux", "darwin", "windows"}
        assert probe["arch"]
        assert isinstance(probe["windows"], bool)

    def test_tool_supported_shape(self):
        report = tool_supported("definitely_not_a_real_tool_xyz")
        assert report["available"] is False
        assert report["method"] == "missing"

    def test_wsl_path_conversion(self):
        assert windows_path_to_wsl(r"C:\Users\foo\bar.txt") == "/mnt/c/Users/foo/bar.txt"
        assert wsl_path_to_windows("/mnt/c/Users") == "\\mnt\\c\\Users"