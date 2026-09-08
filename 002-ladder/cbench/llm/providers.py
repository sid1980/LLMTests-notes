"""Конфигурация провайдеров: пресеты openai / llamacpp / lmstudio.

Все три — OpenAI-совместимые; различие только в ProviderConfig (base_url,
api_key, правила имени модели, поддержка enable_thinking).
"""
from __future__ import annotations

import os
from typing import Optional

from ..model import ProviderConfig


def resolve_provider(name: Optional[str] = None,
                     base_url: Optional[str] = None,
                     api_key: Optional[str] = None,
                     model: Optional[str] = None) -> ProviderConfig:
    """Собрать ProviderConfig из аргументов/env (приоритет: аргументы > env)."""
    name = (name or os.environ.get("CBENCH_PROVIDER") or "").strip().lower()
    base_url = base_url or os.environ.get("CBENCH_BASE_URL") or ""
    api_key = api_key or os.environ.get("CBENCH_API_KEY") or ""
    model = model or os.environ.get("CBENCH_MODEL") or ""

    if name == "openai":
        cfg = openai_preset()
    elif name == "llamacpp":
        cfg = llamacpp_preset()
    elif name == "lmstudio":
        cfg = lmstudio_preset()
    else:
        # не указан — угадываем по URL/порту.
        cfg = _guess(base_url)

    if base_url:
        cfg.base_url = base_url
    if api_key:
        cfg.api_key = api_key
    if model:
        cfg.model = model
    return cfg


def openai_preset() -> ProviderConfig:
    return ProviderConfig(name="openai", base_url=os.environ.get("CBENCH_BASE_URL", ""),
                          api_key=os.environ.get("CBENCH_API_KEY", ""),
                          model=os.environ.get("CBENCH_MODEL", ""),
                          enable_thinking_support=False)


def llamacpp_preset() -> ProviderConfig:
    return ProviderConfig(name="llamacpp",
                          base_url=os.environ.get("CBENCH_BASE_URL", "http://127.0.0.1:8080"),
                          model=os.environ.get("CBENCH_MODEL", ""),
                          enable_thinking_support=True)


def lmstudio_preset() -> ProviderConfig:
    return ProviderConfig(name="lmstudio",
                          base_url=os.environ.get("CBENCH_BASE_URL", "http://127.0.0.1:1234"),
                          model=os.environ.get("CBENCH_MODEL", ""),
                          enable_thinking_support=False)


def _guess(base_url: str) -> ProviderConfig:
    b = (base_url or "").lower()
    if "8080" in b or "llamacpp" in b:
        return llamacpp_preset()
    if "1234" in b or "lmstudio" in b or "lm-studio" in b:
        return lmstudio_preset()
    if "11434" in b or "ollama" in b:
        return ProviderConfig(name="ollama", base_url=base_url or "http://127.0.0.1:11434",
                              model="", enable_thinking_support=False)
    return openai_preset()
