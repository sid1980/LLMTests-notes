"""Подключение к модели: протокол LLMClient + OpenAICompatClient (urllib).

Единственная HTTP-реализация для всех трёх вариантов (внешний провайдер,
llama.cpp, LM Studio) — они говорят по одному OpenAI-протоколу.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import List, Optional

from ..model import ModelReply
from .providers import ProviderConfig
from .reasoning import classify


class LLMError(Exception):
    """Ошибка обращения к серверу модели."""


class LLMClient:
    """Протокол клиента модели."""
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg

    def generate(self, prompt: str, max_tokens: int, sampler: dict,
                 think: bool = False) -> ModelReply:
        raise NotImplementedError

    def model_name(self) -> str:
        raise NotImplementedError

    def endpoint(self) -> str:
        raise NotImplementedError


class OpenAICompatClient(LLMClient):
    def __init__(self, cfg: ProviderConfig):
        super().__init__(cfg)
        self._base = cfg.base_url.rstrip("/")
        if self._base.endswith("/v1"):
            self._base = self._base[:-3]
        self._model = cfg.model
        self._usage = {"prompt": 0, "completion": 0, "secs": 0.0, "req": 0}
        self._last = {}

    def endpoint(self) -> str:
        return f"{self._base}/v1/chat/completions"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            h["Authorization"] = f"Bearer {self.cfg.api_key}"
        return h

    def _post(self, body: dict, timeout: int = 900) -> dict:
        req = urllib.request.Request(
            self.endpoint(), data=json.dumps(body).encode("utf-8"),
            headers=self._headers())
        t0 = time.time()
        try:
            j = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            raise LLMError(f"HTTP {e.code} от {self._base}: {detail}")
        except urllib.error.URLError as e:
            raise LLMError(f"нет соединения с {self._base}: {e.reason}")
        except json.JSONDecodeError as e:
            raise LLMError(f"сервер вернул не-JSON ({self._base}): {e}")
        dt = time.time() - t0
        u = j.get("usage") or {}
        self._usage["req"] += 1
        self._usage["secs"] += dt
        self._usage["prompt"] += u.get("prompt_tokens") or 0
        self._usage["completion"] += u.get("completion_tokens") or 0
        self._last = {"tok": u.get("completion_tokens"), "dt": round(dt, 2),
                      "finish": (j.get("choices") or [{}])[0].get("finish_reason")}
        return j

    def generate(self, prompt: str, max_tokens: int, sampler: dict,
                 think: bool = False) -> ModelReply:
        body = {"model": self.model_name(),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "stream": False, **sampler}
        if self.cfg.enable_thinking_support:
            body["chat_template_kwargs"] = {"enable_thinking": think}
        j = self._post(body)
        try:
            msg = j["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"неожиданный ответ сервера: {e}")
        finish = (j.get("choices") or [{}])[0].get("finish_reason") or ""
        return classify(msg, finish)

    def model_name(self) -> str:
        if self._model:
            return self._model
        self._model = self._auto_model()
        return self._model or "x"

    def _auto_model(self) -> str:
        try:
            req = urllib.request.Request(f"{self._base}/v1/models",
                                         headers=self._headers())
            j = json.loads(urllib.request.urlopen(req, timeout=10).read())
            ids = [m.get("id") for m in j.get("data", []) if m.get("id")]
            return ids[0] if ids else ""
        except Exception:
            return ""

    @property
    def usage(self) -> dict:
        return dict(self._usage)

    @property
    def last(self) -> dict:
        return dict(self._last)
