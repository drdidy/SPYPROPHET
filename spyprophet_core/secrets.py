from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Same Streamlit lookup paths the original helper checked, but resolved from
# the repo root (the parent of this package) so the FastAPI process and the
# Streamlit process see identical results regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent

_SECRETS_TOML_CANDIDATES: tuple[Path, ...] = (
    Path.home() / ".streamlit" / "secrets.toml",
    Path("/app/.streamlit/secrets.toml"),
    _REPO_ROOT / ".streamlit" / "secrets.toml",
)


@lru_cache(maxsize=1)
def streamlit_secrets_available() -> bool:
    """True only if a real secrets.toml exists at one of the standard
    Streamlit lookup paths. Cached so we hit the filesystem once per process
    instead of on every secret read."""
    return any(p.exists() for p in _SECRETS_TOML_CANDIDATES)


def read_secret(name: str) -> str:
    """Read a secret from environment first, Streamlit secrets second.

    Env-vars take precedence so Docker / Render / k8s deployments work
    cleanly. ``st.secrets`` is consulted only as a fallback for local dev,
    and only when a populated ``secrets.toml`` actually exists — otherwise
    we never import streamlit, which keeps the FastAPI process lean.
    """
    env_val = (os.getenv(name) or "").strip()
    if env_val:
        return env_val
    if not streamlit_secrets_available():
        return ""
    try:
        import streamlit as st  # imported lazily; never reached in non-Streamlit envs
    except ImportError:
        return ""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        return ""
    return str(value or "").strip()


# Backwards-compatible aliases — app.py historically used the underscored names.
_read_secret = read_secret
_streamlit_secrets_available = streamlit_secrets_available
