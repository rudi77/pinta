"""Bridge Pinta settings into the env-var conventions LiteLLM/pytaskforce expect.

Pinta uses ``AZURE_OPENAI_*`` (Microsoft convention) in .env. LiteLLM under the
hood reads ``AZURE_API_KEY`` / ``AZURE_API_BASE`` / ``AZURE_API_VERSION``. This
module copies the values so the user keeps one .env file and we don't fork
configuration into two places.

Call ``ensure_litellm_env_for_taskforce()`` once before instantiating
``AgentFactory`` (i.e. inside ``factory.warm_factory()``).
"""
from __future__ import annotations

import os

from src.core.settings import settings


class TaskforceConfigError(RuntimeError):
    """Raised when the pytaskforce-required env config is incomplete."""


_LITELLM_ENV_MAP = {
    "AZURE_API_KEY": "azure_openai_api_key",
    "AZURE_API_BASE": "azure_openai_endpoint",
    "AZURE_API_VERSION": "azure_openai_api_version",
}


def ensure_litellm_env_for_taskforce(*, strict: bool = True) -> None:
    """Copy Pinta Azure-OpenAI settings into LiteLLM env vars.

    With ``strict=True`` (default), raises ``TaskforceConfigError`` if any
    required Azure value is missing — fails fast instead of letting LiteLLM
    bury the user under a stack trace.

    Idempotent: respects pre-existing env values (does not overwrite).
    """
    missing = []
    for env_name, settings_attr in _LITELLM_ENV_MAP.items():
        value = getattr(settings, settings_attr, "") or ""
        if not value and strict:
            missing.append((env_name, settings_attr))
            continue
        # Don't clobber an externally-set var (lets ops override per-env)
        os.environ.setdefault(env_name, value)

    if missing and strict:
        details = "\n".join(
            f"  - {env}  (← settings.{attr}  / .env: {attr.upper()})"
            for env, attr in missing
        )
        raise TaskforceConfigError(
            "pytaskforce/LiteLLM braucht Azure-OpenAI-Credentials, aber folgende "
            "Werte sind in deiner backend/.env nicht gesetzt:\n"
            f"{details}\n\n"
            "Fix: trag die Werte in backend/.env nach (Microsoft-Convention):\n"
            "  AZURE_OPENAI_API_KEY=...\n"
            "  AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com\n"
            "  AZURE_OPENAI_API_VERSION=2024-10-21\n"
            f"Aktiver Model-Alias: {settings.agent_llm_model_alias} "
            "(änderbar via AGENT_LLM_MODEL_ALIAS in .env)."
        )
