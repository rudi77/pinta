"""Bridge Pinta settings into the env-var conventions LiteLLM/pytaskforce expect.

Pinta supports both Azure OpenAI and plain OpenAI for the agent path. The
choice is auto-detected from .env (``settings.llm_provider``) or forced via
``LLM_PROVIDER``. This module copies the right credentials into the env so
the user keeps one .env file and we don't fork configuration into two
places.

Call ``ensure_litellm_env_for_taskforce()`` once before instantiating
``AgentFactory`` (i.e. inside ``factory.warm_factory()``).
"""
from __future__ import annotations

import logging
import os

from src.core.settings import settings


logger = logging.getLogger(__name__)


class TaskforceConfigError(RuntimeError):
    """Raised when the pytaskforce-required env config is incomplete."""


_AZURE_ENV_MAP = {
    "AZURE_API_KEY": "azure_openai_api_key",
    "AZURE_API_BASE": "azure_openai_endpoint",
    "AZURE_API_VERSION": "azure_openai_api_version",
}


def ensure_litellm_env_for_taskforce(*, strict: bool = True) -> str:
    """Bridge env for whichever LLM provider is configured.

    Returns the active provider string (``"azure"`` or ``"openai"``).

    With ``strict=True`` (default), raises ``TaskforceConfigError`` when no
    provider is configured at all — fails fast instead of letting LiteLLM
    bury the user under a stack trace.

    Idempotent: respects pre-existing env values (does not overwrite).
    """
    provider = settings.llm_provider

    if provider == "azure":
        for env_name, settings_attr in _AZURE_ENV_MAP.items():
            value = (getattr(settings, settings_attr, "") or "").strip()
            if value:
                os.environ.setdefault(env_name, value)
        logger.info(
            "litellm_env.bridged provider=azure endpoint=%s",
            settings.azure_openai_endpoint,
        )
        return "azure"

    if provider == "openai":
        key = (settings.openai_api_key or "").strip()
        if key:
            os.environ.setdefault("OPENAI_API_KEY", key)
        logger.info("litellm_env.bridged provider=openai")
        return "openai"

    if not strict:
        logger.warning("litellm_env.no_provider_configured (strict=False)")
        return "none"

    raise TaskforceConfigError(
        "Kein LLM-Provider konfiguriert. Setze in deiner .env entweder\n\n"
        "  Azure OpenAI:\n"
        "    AZURE_OPENAI_API_KEY=...\n"
        "    AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/\n"
        "    AZURE_OPENAI_API_VERSION=2024-10-21\n\n"
        "  oder plain OpenAI:\n"
        "    OPENAI_API_KEY=sk-...\n\n"
        "Pinta wählt den Provider automatisch (Azure hat Vorrang). "
        "Erzwinge einen mit LLM_PROVIDER=azure|openai.\n"
        f"Aktiver Model-Alias: {settings.agent_llm_model_alias} "
        "(änderbar via AGENT_LLM_MODEL_ALIAS in .env)."
    )
