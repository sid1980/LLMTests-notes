"""Извлечение кода из ответа модели."""
from .extract import extract_c, has_code_fence

__all__ = ["extract_c", "has_code_fence"]
