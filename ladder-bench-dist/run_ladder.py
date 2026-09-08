"""Coding ladder benchmark for local LLMs (OpenAI-compatible server by port).
Два трека / Two tracks:
  - code : ступени сложности easy/medium/hard; код исполняется на РЕАЛЬНЫХ тестах.
           difficulty ladder; generated code is actually executed against tests.
  - tools: function-calling — модель зовёт инструмент, сверяем имя+аргументы.
           the model must call the right tool with correct arguments.

Работает с любым OpenAI-совместимым /v1/chat/completions (vLLM, LM Studio, llama.cpp server, ...).
Works with any OpenAI-compatible endpoint.

🛡️ Код модели исполняется в песочнице (sandbox_runner.py, audit-хуки PEP 578):
   без сети, без запуска процессов, запись/удаление только во временной папке теста,
   чистое окружение (ключи/токены не видны), таймаут. Все заблокированные попытки
   логируются в консоль и в итоговый json. Самопроверка: python run_ladder.py selftest
🛡️ Model code runs sandboxed (sandbox_runner.py, PEP 578 audit hooks): no network,
   no process spawning, writes/deletes only inside the test temp dir, scrubbed env,
   timeout. Every blocked attempt is logged to console and the results json.
   Self-check: python run_ladder.py selftest

Запуск / Run:
  python run_ladder.py <port> <label> [code|tools|all]
  # порт любого OpenAI-совместимого сервера / any OpenAI-compatible server port:
  #   vLLM 8000 · LM Studio 1234 · llama.cpp 8080 · Ollama 11434
  # пример: python run_ladder.py 8000 my-model all
  # вместо порта можно полный URL / a full URL also works:
  #   python run_ladder.py http://192.168.1.5:1234 my-model
  python run_ladder.py selftest   # проверить песочницу / verify the sandbox

Только стандартная библиотека Python 3.8+ — никаких зависимостей.
Python 3.8+ stdlib only — no dependencies.
See README for env knobs (THINK, LADDER_LEVELS, LADDER_MAX_TOKENS) and valid sampler.
"""
from __future__ import annotations
import json, re, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
SELFTEST = len(sys.argv) > 1 and sys.argv[1] == "selftest"
# Первый аргумент — порт локального сервера ИЛИ полный URL (http://host:port).
# First arg — local server port OR a full URL. vLLM 8000, LM Studio 1234,
# llama.cpp 8080, Ollama 11434 — любой OpenAI-совместимый / any OpenAI-compatible.
_ARG1 = sys.argv[1] if len(sys.argv) > 1 and not SELFTEST else "5001"
if _ARG1.startswith(("http://", "https://")):
    _ROOT = _ARG1.rstrip("/")
    _ROOT = _ROOT[:-3] if _ROOT.endswith("/v1") else _ROOT
    PORT = _ROOT
else:
    PORT = int(_ARG1)
    _ROOT = f"http://127.0.0.1:{PORT}"
LABEL = sys.argv[2] if len(sys.argv) > 2 else "model"
TRACK = sys.argv[3] if len(sys.argv) > 3 else "all"
THINK = __import__("os").environ.get("THINK", "0") == "1"
# MAX_TOKENS: думающим моделям нужен запас (reasoning + ответ), иначе content пустой при
# finish=length. Дефолт 16384 (non-think). Для THINK ставить 32000+ через env LADDER_MAX_TOKENS.
_MAX_TOKENS = int(__import__("os").environ.get("LADDER_MAX_TOKENS", "16384"))
BASE = f"{_ROOT}/v1/chat/completions"
EXEC_TIMEOUT = 20

# --- Песочница / Sandbox ---------------------------------------------------
# Код модели запускается через sandbox_runner.py (audit-хуки): без сети, без
# запуска процессов, запись только во временной папке. На цифры не влияет:
# блокируются только операции, которые честному решению не нужны; каждая
# заблокированная попытка видна в консоли и в json ("sandbox" у задачи).
# LADDER_UNSAFE=1 — аварийное отключение (старое поведение, НЕ рекомендуется).
RUNNER = HERE / "sandbox_runner.py"
SANDBOX = __import__("os").environ.get("LADDER_UNSAFE", "0") != "1"
# Чистое окружение для кода модели: ключи/токены из env пользователя не видны.
_KEEP_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
             "HOME", "LANG", "LC_ALL", "TMPDIR")


def _child_cmd(f) -> list:
    if SANDBOX:
        # -I: изолированный режим; -X utf8: utf-8 на любой машине (эталонные
        # прогоны шли с PYTHONIOENCODING=utf-8 — фиксируем то же поведение).
        return [sys.executable, "-I", "-X", "utf8", str(RUNNER), str(f)]
    return [sys.executable, str(f)]


def _child_env(td=None):
    if not SANDBOX:
        return None  # unsafe-режим: наследуем окружение как раньше
    env = __import__("os").environ
    out = {k: env[k] for k in _KEEP_ENV if k in env}
    if td is not None:
        # tempfile модуля ребёнка пишет ВНУТРЬ временной папки теста — иначе
        # системный TEMP вне песочницы, и честный код с tempfile падает под
        # песочницей, хотя до неё работал (ломает сравнимость цифр).
        # Redirect temp into the sandbox: otherwise honest tempfile-using code
        # fails under the sandbox while it passed pre-sandbox.
        out["TEMP"] = out["TMP"] = out["TMPDIR"] = str(td)
    return out


def _sandbox_events(stderr) -> list:
    """Строки [SANDBOX] из stderr ребёнка — что пыталась сделать модель."""
    return [ln.strip() for ln in (stderr or "").splitlines()
            if ln.strip().startswith("[SANDBOX]")]
# ---------------------------------------------------------------------------
LEVELS = ["easy", "medium", "hard"]
# env LADDER_LEVELS=hard (или "easy,hard") — прогнать только эти уровни кода (быстрее: medium=60 задач).
# По умолчанию все три. tools-трек не зависит от этого фильтра.
CODE_LEVELS = [x.strip() for x in __import__("os").environ.get("LADDER_LEVELS", "easy,medium,hard").split(",") if x.strip()]


# Статистика прогона: токены/время/маркеры проблемных ответов. / Run stats:
# tokens, timing, and markers of suspicious answers (limit-cut, loops, empty).
USAGE = {"prompt": 0, "completion": 0, "secs": 0.0, "req": 0,
         "cut": 0, "loop": 0, "empty": 0, "thought": 0, "code_from_think": 0}
LAST = {}  # метаданные последнего запроса — до-записываются в результат задачи


_CODE_RE = re.compile(r"```(?:python|py)?\n")


def _split_reasoning(msg: dict, content: str):
    """Достать 'размышления' модели и вернуть (чистый_content, reasoning).
    Reasoning приходит несколькими путями: (1) отдельным полем reasoning_content
    / reasoning / thinking (vLLM, новые LM Studio, нативный Ollama); (2) блоком
    <think>...</think> (или <thinking>) прямо в content — llama.cpp/LM Studio,
    таких блоков может быть несколько; (3) когда сервер сам подставил ОТКРЫВАЮЩИЙ
    <think> в промпт — тогда content начинается сразу с размышлений и содержит
    лишь ЗАКРЫВАЮЩИЙ </think> (кейс DeepSeek-R1/Qwen на llama.cpp); (4) обрыв по
    лимиту прямо в размышлениях — открытый <think> без закрытия. Всё это вырезаем
    из content, чтобы extract_code не спотыкался о код внутри размышлений."""
    rc = (msg.get("reasoning_content") or msg.get("reasoning")
          or msg.get("thinking") or "")
    think = ""
    closed = re.findall(r"<think(?:ing)?>(.*?)</think(?:ing)?>", content, flags=re.DOTALL)
    if closed:
        think = "\n".join(closed)
        content = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", content, flags=re.DOTALL)
    else:
        mopen = re.search(r"<think(?:ing)?>", content)
        mclose = re.search(r"</think(?:ing)?>", content)
        # сервер подставил открывающий тег в промпт: есть только закрывающий
        if mclose and not mopen:
            think = content[:mclose.start()]
            content = content[mclose.end():]
        # незакрытый <think> (обрыв по лимиту прямо в размышлениях)
        elif mopen and not mclose:
            think = content[mopen.end():]
            content = content[:mopen.start()]
    reasoning = (str(rc) + ("\n" + think if think else "")).strip()
    return content.strip(), reasoning


def _min_period(s: str) -> int:
    """Минимальный период строки через префикс-функцию КМП: p = n - f[n-1]."""
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


def _loopish(text: str) -> bool:
    """Маркер зацикливания: конец ответа периодичен — один кусок (любой длины)
    повторяется 3+ раза подряд, даже если обрезан посередине. Проверяем окна
    разного размера, чтобы ловить и длинные, и короткие циклы. / Tail periodicity."""
    for w in (600, 240, 120):
        s = text[-w:]
        if len(s) == w and _min_period(s) <= w // 3:
            return True
    return False


def _post(body: dict) -> dict:
    req = urllib.request.Request(BASE, data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    t0 = time.time()
    j = json.loads(urllib.request.urlopen(req, timeout=900).read())
    dt = time.time() - t0
    u = j.get("usage") or {}
    USAGE["req"] += 1; USAGE["secs"] += dt
    USAGE["prompt"] += u.get("prompt_tokens") or 0
    USAGE["completion"] += u.get("completion_tokens") or 0
    LAST.update({"tok": u.get("completion_tokens"), "dt": round(dt, 2),
                 "finish": (j.get("choices") or [{}])[0].get("finish_reason")})
    return j


def _check_answer(content: str, reasoning: str = ""):
    """Пометить подозрительный ответ (обрыв по лимиту / цикл / пусто / думала)."""
    LAST["cut"] = LAST.get("finish") == "length"
    LAST["loop"] = _loopish(content)
    LAST["empty"] = not content
    LAST["thought"] = bool(reasoning)
    for k in ("cut", "loop", "empty", "thought"):
        USAGE[k] += bool(LAST[k])
    if LAST["cut"] or LAST["loop"]:
        LAST["tail"] = content[-300:]  # кусочек хвоста — поглядеть глазами в отчёте
    if reasoning:
        # сколько думала (грубо ~4 символа/токен) + хвост размышлений — в отчёт
        LAST["think_chars"] = len(reasoning)
        LAST["think_tail"] = reasoning[-400:]


# --- Сэмплер / Sampler -------------------------------------------------------
# Режимы (env LADDER_SAMPLER):
#   reference (дефолт) — официальный Qwen non-think сэмплер, фикс. ЕДИНСТВЕННЫЙ режим,
#                        чьи цифры сравнимы с эталонными. / the only comparable mode.
#   native             — сэмплер-параметры НЕ шлём: работают дефолты сервера/модели
#                        (vLLM и LM Studio сами берут их из generation_config модели —
#                        это и есть рекомендованные автором параметры с HF).
#   recommended        — параметры из справочника sampler_presets.json по имени модели
#                        (Qwen3.5/3.6, Coder-Next, GLM, Gemma...; источник — unsloth-доки).
#                        Не нашлась в справочнике → ведём себя как native.
#   custom             — эталон + переопределения из env: LADDER_TEMP, LADDER_TOP_P,
#                        LADDER_TOP_K, LADDER_MIN_P, LADDER_PRESENCE, LADDER_SEED.
# ⚠️ Всё кроме reference помечается в json и отчёте как несравнимое с эталоном.
_REF_SAMP = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "seed": 42}
_ENV = __import__("os").environ
SAMP_MODE = (_ENV.get("LADDER_SAMPLER") or "reference").strip().lower()
if SAMP_MODE == "native":
    _SAMP = {"seed": 42}  # только воспроизводимость; сэмплер — дефолты сервера/модели
elif SAMP_MODE == "recommended":
    _SAMP = {"seed": 42}  # заполнится в main() после определения имени модели
elif SAMP_MODE == "custom":
    _SAMP = dict(_REF_SAMP)
    for _e, _k, _cast in (("LADDER_TEMP", "temperature", float), ("LADDER_TOP_P", "top_p", float),
                          ("LADDER_TOP_K", "top_k", int), ("LADDER_MIN_P", "min_p", float),
                          ("LADDER_PRESENCE", "presence_penalty", float),
                          ("LADDER_SEED", "seed", int)):
        _v = _ENV.get(_e)
        if _v not in (None, ""):
            _SAMP[_k] = _cast(_v)
else:
    SAMP_MODE = "reference"
    _SAMP = dict(_REF_SAMP)


def find_preset(model_name: str, think: bool):
    """Подобрать рекомендованный сэмплер из sampler_presets.json по имени модели."""
    try:
        data = json.loads((HERE / "sampler_presets.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    low = (model_name or "").lower()
    for p in data.get("presets", []):
        if any(t in low for t in p.get("match", [])):
            params = p.get("think" if think else "nonthink") or p.get("nonthink")
            if params:
                return {"name": p.get("name", "?"), "source": p.get("source", ""),
                        "params": dict(params)}
    return None

# Мульти-прогон: LADDER_RUNS=N — прогнать всё N раз с сидами base, base+1, ...
# и усреднить (одиночный прогон может «гулять»). / Multi-run averaging:
# N runs with seeds base..base+N-1, mean in the summary, per-task stability kept.
N_RUNS = max(1, int(_ENV.get("LADDER_RUNS", "1") or 1))
BASE_SEED = _SAMP.get("seed", 42)

# Имя модели в запросах. vLLM/LM Studio/llama.cpp обслуживают одну модель и имя
# игнорируют, а Ollama требует настоящее — поэтому: env LADDER_MODEL, иначе
# спрашиваем сервер (/v1/models). / Model name: env LADDER_MODEL, else asked
# from the server; single-model servers ignore it, Ollama needs the real one.
_MODEL = None


def _model() -> str:
    global _MODEL
    if _MODEL:
        return _MODEL
    _MODEL = __import__("os").environ.get("LADDER_MODEL", "")
    if not _MODEL:
        try:
            j = json.loads(urllib.request.urlopen(f"{_ROOT}/v1/models", timeout=10).read())
            ids = [m.get("id") for m in j.get("data", []) if m.get("id")]
            if ids:
                _MODEL = ids[0]
                if len(ids) > 1:
                    print(f"[ladder] сервер отдаёт {len(ids)} моделей — беру первую: {_MODEL} "
                          f"(выбрать другую: env LADDER_MODEL=имя)", flush=True)
        except Exception:
            pass
    if not _MODEL:
        _MODEL = "x"  # прежнее поведение / legacy: одномодельные серверы имя игнорируют
    return _MODEL


# Отключение «думанья» в non-think — тонкий момент, два независимых рычага:
#  1) chat_template_kwargs={"enable_thinking": False} — поле запроса. Понимают
#     vLLM и llama.cpp (--jinja). LM Studio и Ollama (OpenAI-режим) молча его
#     игнорируют: незнакомое поле выбрасывается без ошибки.
#  2) токен /no_think в промпте — «мягкий переключатель» старых Qwen. В новых
#     поколениях (3-2507 и далее: модель либо instruct, либо thinking) он больше
#     НЕ действует — проверено на qwen3.5-9b: думала во всех 12/12, несмотря на него.
#     Плюс он семейство-специфичен (/no_think — Qwen, /nothink — GLM) и меняет ТЕКСТ
#     промпта → на temp>0 сдвигает весь поток сэмплирования → цифры перестают быть
#     сравнимыми с эталоном.
# Вывод: по умолчанию /no_think НЕ шлём (чтобы не портить сравнимость). Надёжно
# выключить reasoning можно только на СЕРВЕРЕ (тумблер в LM Studio; --reasoning-budget 0
# у llama.cpp; think:false в нативном API Ollama). Тест это не «чинит», а ЛОГИРУЕТ:
# если модель всё же думала в non-think — прогон помечается несравнимым (см. main()).
# Для экспериментов токен можно вернуть: env LADDER_NOTHINK=1.
INJECT_NOTHINK = _ENV.get("LADDER_NOTHINK", "0") == "1"


def _nothink(text: str) -> str:
    return (text + " /no_think") if (INJECT_NOTHINK and not THINK) else text


def ask(prompt: str, mx: int = None) -> str:
    mx = mx or _MAX_TOKENS
    j = _post({"model": _model(), "messages": [{"role": "user", "content": _nothink(prompt)}],
               "max_tokens": mx, **_SAMP, "stream": False,
               "chat_template_kwargs": {"enable_thinking": THINK}})
    msg = j["choices"][0]["message"]
    content, reasoning = _split_reasoning(msg, msg.get("content") or "")
    # Слабая модель иногда кладёт финальный код ВНУТРЬ размышлений, а в content —
    # пусто/без код-блока. Не теряем зачёт: берём код из reasoning и помечаем
    # флагом code_from_think (виден в отчёте — зачёт «с оговоркой»).
    if reasoning and not _CODE_RE.search(content) and _CODE_RE.search(reasoning):
        content = (content + "\n\n" + reasoning).strip() if content else reasoning
        LAST["code_from_think"] = True
        USAGE["code_from_think"] += 1
    _check_answer(content, reasoning)
    return content


def ask_tools(query: str, tools: list, mx: int = None):
    mx = mx or _MAX_TOKENS
    j = _post({"model": _model(), "messages": [{"role": "user", "content": _nothink(query)}],
               "tools": tools, "tool_choice": "auto",
               "max_tokens": mx, **_SAMP, "stream": False,
               "chat_template_kwargs": {"enable_thinking": THINK}})
    msg = j["choices"][0]["message"]
    _content, reasoning = _split_reasoning(msg, msg.get("content") or "")
    _check_answer(_content, reasoning)
    tcs = msg.get("tool_calls") or []
    if not tcs:
        return None, None
    fn = tcs[0]["function"]
    return fn.get("name"), fn.get("arguments")


def extract_code(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\n(.*?)```", text, re.DOTALL)
    return blocks[-1] if blocks else text


def run_func(code: str, test_code: str):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.py"; f.write_text(code + "\n\n" + test_code, encoding="utf-8")
        try:
            r = subprocess.run(_child_cmd(f), capture_output=True, text=True,
                               timeout=EXEC_TIMEOUT, cwd=td, env=_child_env(td))
        except subprocess.TimeoutExpired as e:
            return False, "timeout", _sandbox_events(getattr(e, "stderr", "") or "")
        sb = _sandbox_events(r.stderr)
        if r.returncode == 0:
            return True, "", sb
        err = (r.stderr or "").strip().splitlines()
        return False, (err[-1] if err else "nonzero")[:80], sb


def run_stdin(code: str, tests: list):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "sol.py"; f.write_text(code, encoding="utf-8")
        sb = []
        for t in tests:
            try:
                r = subprocess.run(_child_cmd(f), input=t["input"], capture_output=True,
                                   text=True, timeout=EXEC_TIMEOUT, cwd=td, env=_child_env(td))
            except subprocess.TimeoutExpired as e:
                return False, "timeout", sb + _sandbox_events(getattr(e, "stderr", "") or "")
            sb += _sandbox_events(r.stderr)
            if r.returncode != 0:
                err = (r.stderr or "").strip().splitlines()
                return False, (err[-1] if err else "runtime error")[:80], sb
            if r.stdout.strip() != str(t["output"]).strip():
                return False, "wrong answer", sb
        return True, "", sb


def check_tool(exp_name, exp_args, got_name, got_args):
    if got_name != exp_name:
        return False
    try:
        got = json.loads(got_args) if isinstance(got_args, str) else (got_args or {})
    except Exception:
        return False
    for k, v in (exp_args or {}).items():
        if str(got.get(k)) != str(v):
            return False
    return True


def do_code(out):
    cases = json.loads((HERE / "ladder_cases.json").read_text(encoding="utf-8"))
    cases = [c for c in cases if c["level"] in CODE_LEVELS]
    by = defaultdict(lambda: [0, 0]); res = []; n_blocked = 0
    for c in cases:
        sb = []
        LAST.clear()
        try:
            code = extract_code(ask(c["prompt"]))
            ok, why, sb = (run_stdin(code, c["tests"]) if c["type"] == "stdin" else run_func(code, c["test_code"]))
        except Exception as e:
            ok, why = False, repr(e)[:80]
        by[c["level"]][0] += ok; by[c["level"]][1] += 1
        row = {"id": c["id"], "level": c["level"], "pass": ok, "why": why}
        if LAST.get("tok") is not None:
            row["tok"] = LAST["tok"]
        flags = [k for k in ("cut", "loop", "empty", "thought", "code_from_think") if LAST.get(k)]
        if flags:
            row["flags"] = flags
            if LAST.get("tail"):
                row["tail"] = LAST["tail"]
            if LAST.get("think_tail"):
                row["think_chars"] = LAST.get("think_chars")
                row["think_tail"] = LAST["think_tail"]
        if sb:
            row["sandbox"] = sb; n_blocked += 1
        res.append(row)
        marks = "".join({"cut": " ✂️обрыв-лимита", "loop": " 🔁цикл?", "empty": " ∅пусто",
                         "thought": f" 🧠думала~{(LAST.get('think_chars') or 0)//4}ток",
                         "code_from_think": " 🔧код-из-размышлений"}[f] for f in flags)
        print(f"  {'✅' if ok else '❌'} [{c['level']:8}] {c['id']}" + ("" if ok else f"  ({why})") + marks, flush=True)
        for ln in sb:
            print(f"     🛡️ {ln}", flush=True)
    if n_blocked:
        print(f"  🛡️ песочница отразила попытки в {n_blocked} задачах (подробности в json) "
              f"/ sandbox blocked attempts in {n_blocked} tasks", flush=True)
    out["code"] = {"by_level": {k: {"pass": v[0], "total": v[1]} for k, v in by.items()},
                   "sandbox_blocked_tasks": n_blocked, "results": res}


def do_tools(out):
    cases = json.loads((HERE / "tooluse_cases.json").read_text(encoding="utf-8"))
    p = t = 0; res = []
    for c in cases:
        LAST.clear()
        try:
            name, args = ask_tools(c["query"], c["tools"])
            ok = check_tool(c["expected_name"], c["expected_args"], name, args)
        except Exception as e:
            ok = False; name = f"ERR:{repr(e)[:40]}"
        p += ok; t += 1
        row = {"id": c["id"], "pass": ok, "expected": c["expected_name"], "got": name}
        flags = [k for k in ("cut", "loop", "empty", "thought") if LAST.get(k)]
        if flags:
            row["flags"] = flags
            if LAST.get("think_tail"):
                row["think_tail"] = LAST["think_tail"]
        res.append(row)
        marks = " 🧠думала" if LAST.get("thought") else ""
        print(f"  {'✅' if ok else '❌'} [tool {c['n_tools']}] {c['id']}  ждали:{c['expected_name']} → {name}{marks}", flush=True)
    out["tools"] = {"pass": p, "total": t, "results": res}


def selftest() -> int:
    """Самопроверка песочницы без сервера: python run_ladder.py selftest.
    Доказывает скептикам: злонамеренный код реально блокируется, честный — работает."""
    import os as _os, tempfile as _tf
    print("[selftest] Проверка песочницы / sandbox self-test\n")
    if SANDBOX and not RUNNER.exists():
        print(f"❌ Не найден {RUNNER.name} рядом с run_ladder.py"); return 2
    if not SANDBOX:
        print("⚠️ LADDER_UNSAFE=1 — селфтест бессмыслен с выключенной песочницей"); return 2
    # файл-приманка ВНЕ песочницы: попробуем удалить/перезаписать его из кода
    fd, probe = _tf.mkstemp(prefix="ladder_probe_"); _os.close(fd)
    Path(probe).write_text("приманка/canary", encoding="utf-8")
    fails = 0

    def case(name, code_snippet, expect_ok, expect_blocked=False):
        nonlocal fails
        ok, why, sb = run_func(code_snippet, "")
        good = (ok == expect_ok) and (not expect_blocked or bool(sb) or "SANDBOX" in why)
        fails += not good
        detail = "" if good else f"  (ok={ok}, why={why!r}, sandbox={sb})"
        print(f"  {'✅' if good else '❌'} {name}{detail}", flush=True)

    try:
        print(" Разрешённое должно работать / allowed things must work:")
        case("честный код исполняется / honest code runs",
             "assert sum(range(10)) == 45\nprint('ok')", True)
        case("threading (глубокая рекурсия) работает / threading works",
             "import threading\nt = threading.Thread(target=lambda: None)\nt.start(); t.join()", True)
        case("запись в СВОЮ временную папку / write inside own tmp dir",
             "open('s.txt', 'w').write('hi')\nassert open('s.txt').read() == 'hi'", True)
        case("tempfile пишет внутри песочницы / tempfile works inside sandbox",
             "import tempfile\nwith tempfile.NamedTemporaryFile('w', delete=True) as f:\n"
             "    f.write('x')\nprint('tempfile ok')", True)
        case("запись в os.devnull / writing to os.devnull",
             "import os\nopen(os.devnull, 'w').write('muted')\nprint('devnull ok')", True)
        print("\n Запрещённое должно блокироваться / forbidden things must be blocked:")
        case("интернет / internet access",
             "import urllib.request\nurllib.request.urlopen('http://example.com', timeout=5)",
             False, True)
        case("сеть даже на localhost / network even to localhost",
             "import socket\nsocket.create_connection(('127.0.0.1', 9), timeout=3)",
             False, True)
        case("os.system", "import os\nos.system('echo pwned')", False, True)
        case("subprocess", "import subprocess\nsubprocess.run(['echo', 'pwned'])", False, True)
        case("удаление чужого файла / deleting a foreign file",
             f"import os\nos.remove({probe!r})", False, True)
        case("перезапись чужого файла / overwriting a foreign file",
             f"open({probe!r}, 'w').write('boom')", False, True)
        case("ctypes (обход хуков) / ctypes (hook bypass)",
             "import ctypes\nctypes.CDLL(None)", False, True)
        case("import с подмодулем (ctypes.util) / dotted import of blocked pkg",
             "import ctypes.util", False, True)
        case("обход через importlib.import_module / importlib bypass",
             "import importlib\nm = importlib.import_module('multiprocessing')\nm.Process",
             False, True)
        case("код глушит sys.stderr — попытка всё равно в логе / stderr spoof still logged",
             "import sys, os\nsys.stderr = open(os.devnull, 'w')\n"
             "try:\n    os.system('echo x')\nexcept Exception:\n    pass\nprint('done')",
             True, True)
        p = Path(probe)
        if p.exists() and p.read_text(encoding="utf-8") == "приманка/canary":
            print("\n  ✅ файл-приманка цел и не изменён / canary file intact")
        else:
            fails += 1
            print("\n  ❌ файл-приманка ПОСТРАДАЛ / canary file was damaged!")
    finally:
        try:
            _os.remove(probe)
        except OSError:
            pass
    print(f"\n[selftest] {'✅ ВСЁ ОК — песочница работает / all good' if not fails else f'❌ ПРОВАЛОВ: {fails}'}")
    return 1 if fails else 0


def _run_tracks() -> dict:
    o = {}
    if TRACK in ("code", "all"):
        print("\n=== CODE (лестница) ===", flush=True); do_code(o)
    if TRACK in ("tools", "all"):
        print("\n=== TOOL-USE (function-calling) ===", flush=True); do_tools(o)
    return o


def _aggregate(runs: list) -> dict:
    """Усреднить N прогонов: средние по уровням + стабильность каждой задачи."""
    out = {}
    if "code" in runs[0]:
        levels = {}
        for lv in runs[0]["code"]["by_level"]:
            ps = [r["code"]["by_level"][lv]["pass"] for r in runs]
            levels[lv] = {"pass": round(sum(ps) / len(ps), 1),
                          "total": runs[0]["code"]["by_level"][lv]["total"],
                          "per_run": ps}
        tasks = {}
        for r in runs:
            for row in r["code"]["results"]:
                t = tasks.setdefault(row["id"], {"id": row["id"], "level": row["level"],
                                                 "passed_n": 0, "n": 0, "why": "", "flags": []})
                t["n"] += 1; t["passed_n"] += bool(row["pass"])
                if not row["pass"] and not t["why"]:
                    t["why"] = row.get("why", "")
                for f in row.get("flags") or []:
                    if f not in t["flags"]:
                        t["flags"].append(f)
                if row.get("tail"):
                    t["tail"] = row["tail"]
        res = []
        for t in tasks.values():
            t["pass"] = t["passed_n"] == t["n"]
            if not t["flags"]:
                t.pop("flags")
            res.append(t)
        out["code"] = {"by_level": levels,
                       "sandbox_blocked_tasks": max(r["code"].get("sandbox_blocked_tasks", 0) for r in runs),
                       "results": res}
    if "tools" in runs[0]:
        ps = [r["tools"]["pass"] for r in runs]
        tasks = {}
        for r in runs:
            for row in r["tools"]["results"]:
                t = tasks.setdefault(row["id"], {"id": row["id"], "expected": row["expected"],
                                                 "got": row["got"], "passed_n": 0, "n": 0})
                t["n"] += 1; t["passed_n"] += bool(row["pass"])
                if not row["pass"]:
                    t["got"] = row["got"]
        for t in tasks.values():
            t["pass"] = t["passed_n"] == t["n"]
        out["tools"] = {"pass": round(sum(ps) / len(ps), 1), "total": runs[0]["tools"]["total"],
                        "per_run": ps, "results": list(tasks.values())}
    return out


def main() -> int:
    t0 = time.time()
    mode = "THINK" if THINK else "no-think"
    if SAMP_MODE == "recommended":
        pr = find_preset(_model(), THINK)
        if pr:
            _SAMP.clear(); _SAMP.update(pr["params"]); _SAMP["seed"] = BASE_SEED
            print(f"[preset] {pr['name']} → {pr['params']}  (источник: {pr['source']})",
                  flush=True)
        else:
            print(f"[preset] модель '{_model()}' не нашлась в sampler_presets.json — "
                  f"параметры не шлю (как native)", flush=True)
    # Отпечаток условий / conditions fingerprint — печатаем и сохраняем в json.
    # По нему любой чужой прогон самопроверяем: совпадают ли условия с эталонными.
    fingerprint = {"sampler": dict(_SAMP), "sampler_mode": SAMP_MODE, "think": THINK,
                   "max_tokens": _MAX_TOKENS, "n_runs": N_RUNS, "base_seed": BASE_SEED,
                   "levels": CODE_LEVELS, "exec_timeout_s": EXEC_TIMEOUT,
                   "sandbox": SANDBOX, "n_code": None, "n_tools": None}
    print(f"[ladder] {LABEL} | track={TRACK} | {mode} | прогонов: {N_RUNS}", flush=True)
    print(f"[server] {BASE} | model={_model()}", flush=True)
    print(f"[conditions] sampler_mode={SAMP_MODE} sampler={_SAMP} think={THINK} "
          f"max_tokens={_MAX_TOKENS} levels={CODE_LEVELS} "
          f"sandbox={'on' if SANDBOX else 'OFF'}", flush=True)
    # ⚠️ предупреждение о невалидности если сэмплер не эталонный
    if SAMP_MODE != "reference" or _SAMP != _REF_SAMP:
        print(f"⚠️  WARNING: сэмплер НЕ эталонный ({SAMP_MODE}) — цифры НЕ сравнимы с "
              f"reference! / non-reference sampler, numbers not comparable", flush=True)
    if SANDBOX and not RUNNER.exists():
        print(f"❌ Не найден {RUNNER.name} рядом с run_ladder.py — он обязателен "
              f"(или LADDER_UNSAFE=1 для старого небезопасного режима).", flush=True)
        return 2
    if not SANDBOX:
        print("⚠️  LADDER_UNSAFE=1: песочница ВЫКЛЮЧЕНА — код модели исполняется "
              "без защиты! / sandbox is OFF!", flush=True)
    if N_RUNS <= 1:
        out = _run_tracks()
    else:
        runs = []
        for ri in range(N_RUNS):
            _SAMP["seed"] = BASE_SEED + ri
            print(f"\n{'#' * 55}\n### ПРОГОН {ri + 1}/{N_RUNS} — seed {_SAMP['seed']}\n{'#' * 55}",
                  flush=True)
            runs.append(_run_tracks())
        _SAMP["seed"] = BASE_SEED
        out = _aggregate(runs)
        print(f"\n[multi-run] усреднено по {N_RUNS} прогонам (seed {BASE_SEED}..{BASE_SEED + N_RUNS - 1})",
              flush=True)
    wall_min = (time.time() - t0) / 60
    if "code" in out:
        fingerprint["n_code"] = sum(v["total"] for v in out["code"]["by_level"].values())
    if "tools" in out:
        fingerprint["n_tools"] = out["tools"]["total"]
    # non-think, а модель всё же думала → прогон НЕ сравним с эталоном (эталонные
    # прогоны — настоящий non-think). Пишем это в отпечаток, отчёт учтёт. /
    # Ran as non-think but the model reasoned anyway → not comparable to reference.
    fingerprint["nothink_thought"] = (not THINK) and USAGE["thought"] > 0
    fingerprint["inject_nothink"] = INJECT_NOTHINK
    # Сводка по токенам/скорости и маркерам подозрительных ответов. / Usage summary.
    usage = {"prompt_tokens": USAGE["prompt"], "completion_tokens": USAGE["completion"],
             "requests": USAGE["req"], "request_seconds": round(USAGE["secs"], 1),
             "gen_tok_s": round(USAGE["completion"] / USAGE["secs"], 1) if USAGE["secs"] else None,
             "answers_cut_by_limit": USAGE["cut"], "loop_suspects": USAGE["loop"],
             "empty_answers": USAGE["empty"], "thinking_answers": USAGE["thought"],
             "code_from_think": USAGE["code_from_think"]}
    fp = HERE / f"ladder_{LABEL}.json"
    fp.write_text(json.dumps({"label": LABEL, "port": PORT, "model": _model(), "think": THINK,
                              "conditions": fingerprint, "usage": usage,
                              "wall_minutes": round(wall_min, 1), "results": out},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*55}\n[ladder] {LABEL} ({mode}) — ИТОГ:")
    if "code" in out:
        for lv in LEVELS:
            d = out["code"]["by_level"].get(lv)
            if d:
                pct = round(100 * d["pass"] / d["total"]); bar = "█"*round(pct/10) + "░"*(10-round(pct/10))
                spread = (f"  (по прогонам: {'/'.join(str(x) for x in d['per_run'])})"
                          if d.get("per_run") else "")
                print(f"  code {lv:8}: {d['pass']:>2}/{d['total']:<2} {bar} {pct}%{spread}")
    if "tools" in out:
        d = out["tools"]; pct = round(100*d["pass"]/d["total"]) if d["total"] else 0
        spread = (f"  (по прогонам: {'/'.join(str(x) for x in d['per_run'])})"
                  if d.get("per_run") else "")
        print(f"  tool-use    : {d['pass']:>2}/{d['total']:<2} {'█'*round(pct/10)+'░'*(10-round(pct/10))} {pct}%{spread}")
    print(f"  ⏱️ ВРЕМЯ ТЕСТА: {wall_min:.1f} мин")
    if usage["completion_tokens"]:
        print(f"  ⚡ генерация: {usage['gen_tok_s']} tok/s · токены: prompt {usage['prompt_tokens']:,} + ответы {usage['completion_tokens']:,}")
    if usage["thinking_answers"]:
        if THINK:
            print(f"  🧠 модель думала в {usage['thinking_answers']} задачах (reasoning-хвосты в отчёте)")
        else:
            print(f"  🧠⚠️  ВНИМАНИЕ: режим non-think, но модель ДУМАЛА в "
                  f"{usage['thinking_answers']} задачах — reasoning НЕ отключился.")
            print(f"       → эти цифры НЕ сравнимы с эталонными (эталон — настоящий non-think).")
            print(f"       → отключи reasoning на СЕРВЕРЕ: LM Studio — тумблер reasoning у модели; "
                  f"llama.cpp — флаг --reasoning-budget 0; Ollama — think:false в нативном API.")
    if usage["code_from_think"]:
        print(f"  🔧 код взят из размышлений в {usage['code_from_think']} задачах "
              f"(модель положила решение внутрь <think> — зачёт с оговоркой, см. отчёт)")
    sus = usage["answers_cut_by_limit"] + usage["loop_suspects"] + usage["empty_answers"]
    if sus:
        print(f"  🚨 подозрительные ответы: обрыв по лимиту {usage['answers_cut_by_limit']} · "
              f"цикл? {usage['loop_suspects']} · пустых {usage['empty_answers']} (детали в отчёте)")
    elif usage["completion_tokens"]:
        print("  ✅ галлюцинаций-маркеров нет: без обрывов, циклов и пустых ответов")
    print(f"-> {fp.name}\n{'='*55}")
    # Красивый сводный отчёт (ваши прогоны + эталонные). Не критично для результата:
    # если make_report.py рядом нет — просто пропускаем. / Optional pretty report.
    try:
        import make_report
        print(f"[report] обновлён -> {make_report.build(HERE).name} (открой в браузере)")
    except Exception as e:
        print(f"[report] пропущен: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if SELFTEST else main())
