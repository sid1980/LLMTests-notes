#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка сервера ПЕРЕД прогоном бенча: слушается ли модель параметров запроса.

Проверяем по ЭФФЕКТУ, что сервер реально применяет temperature/top_k/seed/max_tokens,
а не отбрасывает их молча (как LM Studio/Ollama поступают с chat_template_kwargs).

Запуск:
  python probe_sampler.py 1234
  python probe_sampler.py http://192.168.56.1:1234       # LM Studio через Caddy
  python probe_sampler.py 8080                           # llama.cpp
  python probe_sampler.py https://api.openai.com/v1 --provider openai --api-key sk-...

Только стандартная библиотека Python 3.8+.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

PROMPT = ("Invent one unusual name for a coffee shop and explain it in one short "
          "sentence. Be creative.")


def _root() -> str:
    a = sys.argv[1] if len(sys.argv) > 1 else "1234"
    if a.startswith(("http://", "https://")):
        a = a.rstrip("/")
        return a[:-3] if a.endswith("/v1") else a
    return f"http://127.0.0.1:{int(a)}"


def _env_flag(name: str) -> bool:
    return any(name in a for a in sys.argv)


def main() -> int:
    root = _root()
    base = f"{root}/v1/chat/completions"
    api_key = os.environ.get("CBENCH_API_KEY", "")
    model = os.environ.get("CBENCH_MODEL", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if not model:
        try:
            j = json.loads(urllib.request.urlopen(f"{root}/v1/models", timeout=10).read())
            ids = [m.get("id") for m in j.get("data", []) if m.get("id")]
            model = ids[0] if ids else "x"
        except Exception:
            model = "x"

    print(f"[probe] сервер: {base}\n[probe] модель: {model}\n")

    def ask(params: dict, label: str) -> str:
        body = {"model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "stream": False, **params}
        req = urllib.request.Request(base, data=json.dumps(body).encode(), headers=headers)
        try:
            j = json.loads(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            print(f"  ❌ {label}: {e}")
            return ""
        c = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        u = j.get("usage") or {}
        print(f"  → {label}: finish=... tokens={u.get('completion_tokens')} "
              f"ответ={c[:60]!r}")
        return c

    print("1) детерминированность (temperature=0, seed=42) — два одинаковых запроса:")
    a = ask({"temperature": 0.0, "seed": 42, "max_tokens": 200}, "попытка A")
    b = ask({"temperature": 0.0, "seed": 42, "max_tokens": 200}, "попытка B")
    if a and b:
        print(f"   {'✅ детерминировано' if a == b else '⚠️  РАЗНЫЕ ответы — seed/temp=0 игнорируются'}")

    print("\n2) max_tokens действительно ограничивает ответ:")
    short = ask({"temperature": 0.0, "max_tokens": 5}, "max_tokens=5")
    if short and len(short.split()) <= 6:
        print("   ✅ короткий ответ получен")

    print("\n3) temperature влияет (два ответа при temp=1.0):")
    c1 = ask({"temperature": 1.0, "max_tokens": 200}, "temp=1.0 A")
    c2 = ask({"temperature": 1.0, "max_tokens": 200}, "temp=1.0 B")
    if c1 and c2:
        print(f"   {'✅ есть разброс' if c1 != c2 else '⚠️  ответы совпали — temperature может игнорироваться'}")

    print("\n[probe] готово. Если сервер игнорирует параметры — цифры бенча считайте примерными.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
