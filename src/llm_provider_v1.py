"""Shared LLM provider configuration for Metis capabilities.

Audit, semantic pre-Review and future compiled-knowledge execution use the same
provider credential and model selection. Capability-specific prompts, schemas,
permissions and fail-closed rules remain in their owning modules.

This module stores no secret and creates no modelcall by itself.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


LLM_API_KEY_ENV = "METIS_LLM_API_KEY"
LLM_MODEL_ENV = "METIS_LLM_MODEL"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class LLMProviderConfig:
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)


def load_llm_provider_config(
    environ: Mapping[str, str] | None = None,
) -> LLMProviderConfig:
    env = environ if environ is not None else os.environ
    return LLMProviderConfig(
        api_key=str(env.get(LLM_API_KEY_ENV, "") or "").strip(),
        model=str(env.get(LLM_MODEL_ENV, "") or "").strip(),
    )
