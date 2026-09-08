"""Извлечение C-кода из ответа модели."""
from __future__ import annotations

import re

_CODE_RE = re.compile(r"```(?:c|C)\n(.*?)```", re.DOTALL)
_ANY_FENCE_RE = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)


def extract_c(text: str) -> str:
    """Извлечь код Си: последний ```c-блок; иначе последний любой code-блок;
    иначе весь текст как есть."""
    blocks = _CODE_RE.findall(text)
    if blocks:
        return blocks[-1].strip()
    any_blocks = _ANY_FENCE_RE.findall(text)
    if any_blocks:
        return any_blocks[-1].strip()
    return text.strip()


def has_code_fence(text: str) -> bool:
    return bool(_CODE_RE.search(text))
