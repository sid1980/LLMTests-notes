"""Слой общения с моделью."""
from .client import LLMClient, OpenAICompatClient, LLMError
from .providers import resolve_provider, openai_preset, llamacpp_preset, lmstudio_preset
from .reasoning import split_reasoning, classify

__all__ = ["LLMClient", "OpenAICompatClient", "LLMError",
           "resolve_provider", "openai_preset", "llamacpp_preset", "lmstudio_preset",
           "split_reasoning", "classify"]
