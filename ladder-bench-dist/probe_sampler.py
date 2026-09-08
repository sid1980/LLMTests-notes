#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка сервера ПЕРЕД прогоном бенча: слушается ли модель параметров запроса?
Server sanity-check BEFORE benchmarking: does the model actually obey request params?

Зачем / Why: OpenAI-совместимые серверы принимают JSON с temperature/top_k/seed/
max_tokens, но НЕ гарантируют, что применят их — незнакомое поле может быть молча
отброшено (так LM Studio/Ollama поступают с chat_template_kwargs). Спросить «ты
применил температуру?» нельзя — сервер не отвечает. Поэтому проверяем по ЭФФЕКТУ:
ставим значение, при котором ответ ОБЯЗАН стать (не)детерминированным, и смотрим.
We can't ask the server "did you apply temperature?" — so we probe by effect:
set a value that MUST make the output (non)deterministic and check the outcome.

Запуск / Run (порт любого OpenAI-совместимого сервера ИЛИ полный URL):
  python probe_sampler.py <port>            # vLLM 8000 · LM Studio 1234 · llama.cpp 8080 · Ollama 11434
  python probe_sampler.py 1234
  python probe_sampler.py http://192.168.1.5:1234
  LADDER_MODEL=имя python probe_sampler.py 1234   # если на сервере несколько моделей

Только стандартная библиотека Python 3.8+ / stdlib only.
"""
from __future__ import annotations
import io, json, os, sys, urllib.request

# utf-8 в консоль на любой ОС (Windows cp1251 бьёт кириллицу/эмодзи).
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

_ARG1 = sys.argv[1] if len(sys.argv) > 1 else "1234"
if _ARG1.startswith(("http://", "https://")):
    _ROOT = _ARG1.rstrip("/")
    _ROOT = _ROOT[:-3] if _ROOT.endswith("/v1") else _ROOT
else:
    _ROOT = f"http://127.0.0.1:{int(_ARG1)}"
BASE = f"{_ROOT}/v1/chat/completions"

# Нейтральный творческий промпт — чтобы при высокой температуре реально был разброс.
PROMPT = ("Invent one unusual name for a coffee shop and explain it in one short "
          "sentence. Be creative.")


def _model() -> str:
    m = os.environ.get("LADDER_MODEL", "")
    if m:
        return m
    try:
        j = json.loads(urllib.request.urlopen(f"{_ROOT}/v1/models", timeout=10).read())
        ids = [d.get("id") for d in j.get("data", []) if d.get("id")]
        if ids:
            if len(ids) > 1:
                print(f"[probe] сервер отдаёт {len(ids)} моделей — беру первую: {ids[0]} "
                      f"(другую: env LADDER_MODEL=имя)")
            return ids[0]
    except Exception:
        pass
    return "x"  # одномодельные серверы имя игнорируют


MODEL = _model()


def ask(**params) -> str:
    body = {"model": MODEL, "stream": False,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": params.pop("max_tokens", 160)}
    body.update(params)
    req = urllib.request.Request(BASE, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    msg = j["choices"][0]["message"]
    # сравниваем ВЕСЬ сэмплированный поток: reasoning (если есть) + content
    text = ((msg.get("reasoning_content") or msg.get("reasoning") or msg.get("thinking") or "")
            + "|" + (msg.get("content") or ""))
    fin = j["choices"][0].get("finish_reason")
    ctok = (j.get("usage") or {}).get("completion_tokens")
    return text, fin, ctok


RESULTS = []  # (ok, name, note)


def check(name, ok, note):
    RESULTS.append((ok, name, note))
    print(("  ✅ " if ok else "  ❌ ") + name + " — " + note, flush=True)


def main() -> int:
    print(f"[probe] сервер: {BASE} | модель: {MODEL}")
    print(f"[probe] проверяю, применяет ли сервер параметры сэмплера из запроса…\n")
    try:
        # 1) детерминизм по сиду: одинаковый seed -> байт-в-байт одинаково
        a1, _, _ = ask(temperature=1.0, top_p=0.95, top_k=20, seed=42)
        a2, _, _ = ask(temperature=1.0, top_p=0.95, top_k=20, seed=42)
        check("seed фиксирует вывод (два запроса с seed=42 совпали)", a1 == a2,
              "детерминизм по сиду работает" if a1 == a2
              else "seed НЕ применяется (ответы разошлись) — воспроизводимость под вопросом")

        # 2) разный seed -> разный вывод (иначе сервер вообще не сэмплирует / кэширует)
        b1, _, _ = ask(temperature=1.0, top_p=0.95, top_k=20, seed=43)
        check("другой seed меняет вывод (seed=43 ≠ seed=42)", b1 != a1,
              "сид реально влияет" if b1 != a1
              else "разные сиды дали ОДно и то же — возможен кэш ответов или temp=0 принудительно")

        # 3) temperature=0 -> жадный режим, сид не важен, два запроса совпадают
        c1, _, _ = ask(temperature=0, seed=1)
        c2, _, _ = ask(temperature=0, seed=2)
        check("temperature=0 = жадный режим (сид не важен, совпало)", c1 == c2,
              "temp=0 применяется" if c1 == c2
              else "при temp=0 ответы разные — temperature игнорируется сервером!")

        # 4) высокая temperature -> при разных сидах ответы обязаны различаться
        d1, _, _ = ask(temperature=1.8, top_p=1.0, top_k=0, seed=7)
        d2, _, _ = ask(temperature=1.8, top_p=1.0, top_k=0, seed=8)
        check("высокая temperature=1.8 даёт разброс (seed 7≠8)", d1 != d2,
              "temperature реально включает случайность" if d1 != d2
              else "разброса нет — temperature, похоже, не применяется")

        # 5) top_k=1 давит любую температуру -> снова детерминизм
        e1, _, _ = ask(temperature=1.8, top_k=1, seed=7)
        e2, _, _ = ask(temperature=1.8, top_k=1, seed=8)
        ok5 = e1 == e2
        check("top_k=1 = жадный даже при temp=1.8 (совпало)", ok5,
              "top_k применяется" if ok5
              else "top_k=1 не сделал вывод детерминированным — top_k игнорируется (частый случай Ollama)")

        # 6) max_tokens реально режет ответ
        _, fin, ctok = ask(max_tokens=8, temperature=0, seed=1)
        ok6 = (fin == "length") or (ctok is not None and ctok <= 12)
        check("max_tokens=8 обрезает ответ", ok6,
              f"finish={fin}, completion_tokens={ctok}")
    except urllib.error.URLError as e:
        print(f"\n❌ Не достучался до сервера {BASE}: {e}\n"
              f"   Проверь, что сервер запущен и порт верный.")
        return 2
    except Exception as e:
        print(f"\n❌ Ошибка запроса: {e!r}")
        return 2

    passed = sum(1 for ok, _, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n[probe] пройдено {passed}/{total}.")
    if passed == total:
        print("✅ Сервер честно применяет сэмплер из запроса — цифры бенча по этим "
              "параметрам достоверны.")
        print("   (Даже если в интерфейсе сервера выставлены другие значения — параметры "
              "запроса их перекрывают, это только что доказано.)")
        return 0
    fails = [name for ok, name, _ in RESULTS if not ok]
    print("⚠️  ВНИМАНИЕ: сервер игнорирует часть параметров:")
    for f in fails:
        print(f"     • {f}")
    print("   → цифры бенча по этим параметрам считай ПРИМЕРНЫМИ; для точного сравнения "
          "используй бэкенд, который слушается (vLLM надёжнее всего).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
