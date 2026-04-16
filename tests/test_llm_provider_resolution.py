from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import yaml

from sz.interfaces import llm
from sz.interfaces.llm_providers import claude_code, codex


def _make_repo(config: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="s0-llm-provider-test-"))
    (root / ".sz").mkdir()
    (root / ".sz.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return root


class ProviderResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def test_auto_prefers_codex_before_api_keys(self) -> None:
        with mock.patch.object(
            llm,
            "_probe_provider",
            side_effect=lambda name: {
                "provider": name,
                "available": name in {"codex", "openai", "mock"},
                "reason": f"{name} probe",
                "source": "test",
            },
        ):
            resolved = llm.resolve_provider()
        self.assertEqual(resolved.provider, "codex")
        self.assertEqual(resolved.source, "auto")

    def test_repo_config_provider_is_respected(self) -> None:
        repo = _make_repo(
            {
                "sz_version": "0.1.0",
                "host": "generic",
                "host_mode": "install",
                "modules": {},
                "providers": {"llm": "claude_code"},
            }
        )
        with mock.patch.object(
            llm,
            "_probe_provider",
            side_effect=lambda name: {
                "provider": name,
                "available": name == "claude_code",
                "reason": f"{name} probe",
                "source": "test",
            },
        ):
            resolved = llm.resolve_provider(repo)
        self.assertEqual(resolved.provider, "claude_code")
        self.assertEqual(resolved.source, "repo_config")

    def test_repo_priority_overrides_default_order(self) -> None:
        repo = _make_repo(
            {
                "sz_version": "0.1.0",
                "host": "generic",
                "host_mode": "install",
                "modules": {},
                "providers": {"llm": "auto", "llm_priority": ["anthropic", "openai", "mock"]},
            }
        )
        with mock.patch.object(
            llm,
            "_probe_provider",
            side_effect=lambda name: {
                "provider": name,
                "available": name in {"anthropic", "openai", "mock"},
                "reason": f"{name} probe",
                "source": "test",
            },
        ):
            resolved = llm.resolve_provider(repo)
        self.assertEqual(resolved.provider, "anthropic")
        self.assertEqual(resolved.priority[:3], ["anthropic", "openai", "mock"])

    def test_env_override_wins(self) -> None:
        os.environ["SZ_LLM_PROVIDER"] = "mock"
        with mock.patch.object(
            llm,
            "_probe_provider",
            side_effect=lambda name: {
                "provider": name,
                "available": True,
                "reason": f"{name} probe",
                "source": "test",
            },
        ):
            resolved = llm.resolve_provider()
        self.assertEqual(resolved.provider, "mock")
        self.assertEqual(resolved.source, "env")


class SubscriptionCliProbeTests(unittest.TestCase):
    def test_codex_probe_detects_chatgpt_login(self) -> None:
        completed = mock.Mock(returncode=0, stdout="Logged in using ChatGPT\n", stderr="")
        with mock.patch.object(codex, "_codex_bin", return_value="codex"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            result = codex.probe()
        self.assertTrue(result["available"])
        self.assertEqual(result["source"], "subscription_cli")

    def test_claude_probe_detects_logged_out(self) -> None:
        completed = mock.Mock(returncode=1, stdout='{"loggedIn": false, "authMethod": "none"}', stderr="")
        with mock.patch.object(claude_code, "_claude_bin", return_value="claude"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            result = claude_code.probe()
        self.assertFalse(result["available"])
        self.assertEqual(result["source"], "subscription_cli")


if __name__ == "__main__":
    unittest.main()
