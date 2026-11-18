"""LLM factory. Returns None in mock mode so no LLM call can happen in tests or CI."""

from __future__ import annotations

import os

from foresight.settings import Settings


class LLMConfigurationError(RuntimeError):
    pass


def check_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise LLMConfigurationError(
            "OPENAI_API_KEY is not set. Add it to .env (local) or Railway variables, "
            "or set MOCK_LLM=true to run without an LLM."
        )


def get_llm(settings: Settings):
    if settings.mock_llm:
        return None
    check_api_key()
    from crewai import LLM

    return LLM(model=settings.llm.model, temperature=settings.llm.temperature)
