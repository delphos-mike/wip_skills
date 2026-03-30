"""Integration tests: API key delivery via 1Password CLI.

Tests the full key resolution cascade:
  1. NOTION_API_KEY env var
  2. Cached key in .secrets/notion_api_key
  3. 1Password CLI: op read "op://it-ops-helpers/NOTION_SKILL_INTEGRATION/credential"
"""

import os
import stat

from notion_utils import (
    _OP_DEFAULT_REF,
    _cache_key,
    _fetch_key_from_op,
    _read_cached_key,
    _require_op,
    load_api_key,
)


class TestRequireOp:
    """Verify the 1Password CLI is available."""

    def test_op_binary_found(self):
        op_bin = _require_op()
        assert op_bin is not None
        assert os.path.isfile(op_bin)


class TestOpReference:
    """Verify the default op:// reference points to the shared vault."""

    def test_default_ref_uses_shared_vault(self):
        assert "it-ops-helpers" in _OP_DEFAULT_REF
        assert "NOTION_SKILL_INTEGRATION" in _OP_DEFAULT_REF

    def test_fetch_from_op(self):
        """op read returns a valid Notion API key."""
        key = _fetch_key_from_op()
        assert key.startswith("ntn_")
        assert len(key) > 20


class TestCacheRoundtrip:
    """Test writing and reading the cached key file."""

    def test_cache_write_read(self, tmp_path, monkeypatch):
        """Write a key to cache and read it back."""
        test_secrets = tmp_path / ".secrets"
        test_key_file = test_secrets / "notion_api_key"

        monkeypatch.setattr("notion_utils._SECRETS_DIR", test_secrets)
        monkeypatch.setattr("notion_utils._CACHED_KEY_FILE", test_key_file)

        _cache_key("ntn_test_key_12345")

        assert test_key_file.exists()
        assert _read_cached_key() == "ntn_test_key_12345"

    def test_cache_permissions(self, tmp_path, monkeypatch):
        """Cached key file has 0600, directory has 0700."""
        test_secrets = tmp_path / ".secrets"
        test_key_file = test_secrets / "notion_api_key"

        monkeypatch.setattr("notion_utils._SECRETS_DIR", test_secrets)
        monkeypatch.setattr("notion_utils._CACHED_KEY_FILE", test_key_file)

        _cache_key("ntn_test_key_12345")

        dir_mode = stat.S_IMODE(test_secrets.stat().st_mode)
        file_mode = stat.S_IMODE(test_key_file.stat().st_mode)
        assert dir_mode == 0o700
        assert file_mode == 0o600

    def test_empty_cache_returns_none(self, tmp_path, monkeypatch):
        test_key_file = tmp_path / ".secrets" / "notion_api_key"
        monkeypatch.setattr("notion_utils._CACHED_KEY_FILE", test_key_file)
        assert _read_cached_key() is None


class TestLoadApiKeyCascade:
    """Test the full resolution cascade."""

    def test_env_var_takes_priority(self, monkeypatch):
        monkeypatch.setenv("NOTION_API_KEY", "ntn_from_env")
        assert load_api_key() == "ntn_from_env"

    def test_cache_used_when_no_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NOTION_API_KEY", raising=False)

        test_secrets = tmp_path / ".secrets"
        test_key_file = test_secrets / "notion_api_key"
        monkeypatch.setattr("notion_utils._SECRETS_DIR", test_secrets)
        monkeypatch.setattr("notion_utils._CACHED_KEY_FILE", test_key_file)

        _cache_key("ntn_from_cache")
        assert load_api_key() == "ntn_from_cache"

    def test_op_fallback_when_no_env_or_cache(self, tmp_path, monkeypatch):
        """With no env var and no cache, op read is invoked and result is cached."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)

        test_secrets = tmp_path / ".secrets"
        test_key_file = test_secrets / "notion_api_key"
        monkeypatch.setattr("notion_utils._SECRETS_DIR", test_secrets)
        monkeypatch.setattr("notion_utils._CACHED_KEY_FILE", test_key_file)

        key = load_api_key()
        assert key.startswith("ntn_")

        # Verify it was cached
        cached = _read_cached_key()
        assert cached == key
