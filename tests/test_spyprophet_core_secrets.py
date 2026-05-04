from __future__ import annotations

from pathlib import Path

from spyprophet_core import secrets as core_secrets


def test_env_var_takes_precedence(monkeypatch):
    monkeypatch.setenv("SPY_TEST_KEY", "from-env")
    assert core_secrets.read_secret("SPY_TEST_KEY") == "from-env"


def test_blank_when_missing(monkeypatch):
    monkeypatch.delenv("SPY_TEST_KEY", raising=False)
    monkeypatch.setattr(core_secrets, "streamlit_secrets_available", lambda: False)
    assert core_secrets.read_secret("SPY_TEST_KEY") == ""


def test_env_value_is_stripped(monkeypatch):
    monkeypatch.setenv("SPY_TEST_KEY", "  padded  ")
    assert core_secrets.read_secret("SPY_TEST_KEY") == "padded"


def test_streamlit_fallback_only_when_file_present(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SPY_TEST_KEY", raising=False)
    fake_toml = tmp_path / "secrets.toml"
    fake_toml.write_text("SPY_TEST_KEY = 'from-toml'\n")
    monkeypatch.setattr(
        core_secrets,
        "_SECRETS_TOML_CANDIDATES",
        (fake_toml,),
    )
    core_secrets.streamlit_secrets_available.cache_clear()

    class FakeSecrets:
        def get(self, name, default=""):
            return "from-toml" if name == "SPY_TEST_KEY" else default

    class FakeStreamlit:
        secrets = FakeSecrets()

    monkeypatch.setitem(__import__("sys").modules, "streamlit", FakeStreamlit())
    try:
        assert core_secrets.read_secret("SPY_TEST_KEY") == "from-toml"
    finally:
        core_secrets.streamlit_secrets_available.cache_clear()


def test_app_module_reexports_helpers():
    """app.py historically exposed _read_secret / _streamlit_secrets_available;
    other code (and old tests) import those names directly."""
    import app

    assert app._read_secret is core_secrets._read_secret
    assert app._streamlit_secrets_available is core_secrets._streamlit_secrets_available
