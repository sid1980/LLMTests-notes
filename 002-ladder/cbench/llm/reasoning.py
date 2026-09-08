"""Обработка ответа модели: вырезание reasoning, маркеры аномалий.

Пути, которыми приходит «думанье»: отдельным полем (reasoning_content /
reasoning / thinking), блоками <think>...</think> в content, незакрытым <think>
(обрыв по лимиту), или когда сервер сам подставил открывающий <think>.
"""
from __future__ import annotations

import re
from typing import Tuple

from ..model import ModelReply

_THINK_RE = re.compile(r"<think(?:ing)?>(.*?)</think(?:ing)?>", re.DOTALL)


def split_reasoning(msg: dict, content: str) -> Tuple[str, str]:
    """Вернуть (чистый content, reasoning)."""
    rc = (msg.get("reasoning_content") or msg.get("reasoning")
          or msg.get("thinking") or "")
    think = ""
    closed = _THINK_RE.findall(content)
    if closed:
        think = "\n".join(closed)
        content = _THINK_RE.sub("", content)
    else:
        mopen = re.search(r"<think(?:ing)?>", content)
        mclose = re.search(r"</think(?:ing)?>", content)
        if mclose and not mopen:          # сервер подставил открывающий тег
            think = content[:mclose.start()]
            content = content[mclose.end():]
        elif mopen and not mclose:        # обрыв по лимиту в размышлениях
            think = content[mopen.end():]
            content = content[:mopen.start()]
    reasoning = (str(rc) + ("\n" + think if think else "")).strip()
    return content.strip(), reasoning


def _min_period(s: str) -> int:
    n = len(s)
    f = [0] * n
    k = 0
    for i in range(1, n):
        while k and s[i] != s[k]:
            k = f[k - 1]
        if s[i] == s[k]:
            k += 1
        f[i] = k
    return n - f[-1]


def loopish(text: str) -> bool:
    """Маркер зацикливания: конец ответа периодичен (кусок повторяется 3+ раза)."""
    for w in (600, 240, 120):
        s = text[-w:]
        if len(s) == w and _min_period(s) <= w // 3:
            return True
    return False


def classify(msg: dict, finish_reason: str = "") -> ModelReply:
    """Построить ModelReply с флагами аномалий."""
    content, reasoning = split_reasoning(msg, msg.get("content") or "")
    reply = ModelReply(content=content, reasoning=reasoning)
    if finish_reason == "length":
        reply.flags.append("cut")
        reply.tail = content[-300:]
    if loopish(content):
        reply.flags.append("loop")
        reply.tail = reply.tail or content[-300:]
    if not content:
        reply.flags.append("empty")
    if reasoning:
        reply.flags.append("thought")
        reply.think_chars = len(reasoning)
        reply.think_tail = reasoning[-400:]
    return reply
