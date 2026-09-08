#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интерактивный запуск бенча / Interactive benchmark launcher.

Сканирует локальные LLM-серверы (vLLM, LM Studio, Ollama, llama.cpp, ...),
показывает что нашёл, даёт выбрать сервер и модель — и запускает run_ladder.py
в эталонных условиях (как run_reference). Двойной клик по START_BENCH.bat —
и поехали. / Scans local LLM servers, lets you pick one, runs the benchmark
under reference conditions. No arguments, no configuration.

Только стандартная библиотека / stdlib only — no pip installs.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))

# Какие порты сканируем (список из реально живущих дефолтов).
# Which default ports to probe.
SCAN_TARGETS = [
    (1234, "LM Studio"),
    (8000, "vLLM"),
    (5001, "vLLM"),
    (5000, "text-gen-webui"),
    (11434, "Ollama"),
    (8080, "llama.cpp"),
]
SCAN_TIMEOUT = 1.5  # сек на порт / seconds per port


def _get_json(url: str, timeout: float = SCAN_TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def probe(port: int, kind: str):
    """Жив ли сервер на порту и какие модели отдаёт. / Is the server alive, which models."""
    try:
        j = _get_json(f"http://127.0.0.1:{port}/v1/models")
        models = [m.get("id", "") for m in j.get("data", []) if m.get("id")]
        return {"port": port, "kind": kind, "models": models}
    except Exception:
        pass
    if port == 11434:
        # Ollama: если /v1/models не ответил — пробуем родной API / native API fallback
        try:
            j = _get_json(f"http://127.0.0.1:{port}/api/tags")
            models = [m.get("name", "") for m in j.get("models", []) if m.get("name")]
            return {"port": port, "kind": "Ollama", "models": models}
        except Exception:
            pass
    return None


def scan():
    with ThreadPoolExecutor(max_workers=len(SCAN_TARGETS)) as ex:
        found = list(ex.map(lambda t: probe(*t), SCAN_TARGETS))
    return [f for f in found if f]


def pick(prompt: str, n: int, default: int = 1) -> int:
    """Выбор номера из списка. Enter = default, q = выход. / Pick a number; Enter=default, q=quit."""
    while True:
        s = input(prompt).strip().lower()
        if s == "q":
            print("Выход / bye")
            raise SystemExit(0)
        if not s:
            return default
        if s.isdigit() and 1 <= int(s) <= n:
            return int(s)
        print(f"  нужен номер 1..{n} (Enter = {default}, q = выход) / enter a number")


def safe_label(name: str) -> str:
    """Имя модели -> безопасное имя файла. / Model name -> safe file label."""
    name = name.rsplit("/", 1)[-1]  # 'org/model' -> 'model'
    return re.sub(r"[^\w.-]+", "-", name).strip("-") or "model"


def main() -> int:
    print("=" * 60)
    print("  🪜 Coding Ladder Benchmark — интерактивный запуск")
    print("=" * 60)

    while True:
        print("\nСканирую локальные серверы моделей... / scanning local servers...")
        servers = scan()
        if servers:
            break
        print("""
❌ Ни одного живого сервера не нашла. Запустите один из:
   - LM Studio -> вкладка Developer -> Start Server (порт 1234)
   - Ollama    -> ollama serve  (и ollama pull <модель>)
   - vLLM / llama.cpp server — своим обычным способом
No local server found — start LM Studio / Ollama / vLLM / llama.cpp first.""")
        s = input("Enter — пересканировать, q — выход / Enter = rescan, q = quit: ").strip().lower()
        if s == "q":
            return 0

    print("\nНашла / found:")
    for i, s in enumerate(servers, 1):
        n = len(s["models"])
        shown = ", ".join(s["models"][:3]) + (", ..." if n > 3 else "")
        print(f"  [{i}] {s['kind']:<15} :{s['port']}  ({n} модел.: {shown})" if n
              else f"  [{i}] {s['kind']:<15} :{s['port']}  (модели не показал)")

    srv = servers[pick(f"\nК какому серверу подключаться? [1..{len(servers)}, Enter=1]: ", len(servers)) - 1]

    # --- выбор модели / model choice ---
    models = srv["models"]
    if len(models) > 1:
        print(f"\nМодели на {srv['kind']}:")
        for i, m in enumerate(models, 1):
            print(f"  [{i}] {m}")
        model = models[pick(f"Какую тестируем? [1..{len(models)}, Enter=1]: ", len(models)) - 1]
    elif models:
        model = models[0]
        print(f"\nМодель: {model}")
    else:
        model = input("\nСервер не отдал список моделей. Введите имя модели (Enter = пропустить): ").strip()

    if srv["kind"] == "Ollama":
        print("\n⚠️  Ollama игнорирует часть эталонного сэмплера (top_k/min_p) —")
        print("   цифры будут ПРИМЕРНЫМИ, с reference-прогонами сравнивать осторожно.")
        print("   Ollama's OpenAI endpoint drops top_k/min_p — treat numbers as approximate.")

    # --- режим / mode ---
    print("\nРежим / mode:")
    print("  [1] обычный (non-think) — как эталонные прогоны / like reference runs")
    print("  [2] thinking — для reasoning-моделей, бюджет 32k токенов")
    think = pick("Выбор [Enter=1]: ", 2) == 2

    # --- сэмплер / sampler ---
    print("\nСэмплер / sampler:")
    print("  [1] эталонный Qwen — temp 1.0 · top_p 0.95 · top_k 20 · seed 42.")
    print("      Единственный режим, сравнимый с эталонными цифрами / comparable mode")
    print("  [2] по справочнику — рекомендации для семейства модели из sampler_presets.json")
    print("      (Qwen3.5/3.6, Coder-Next, GLM, Gemma; unsloth-доки). ⚠ несравнимо")
    print("  [3] родной для модели — параметры не переопределяем, работают дефолты")
    print("      сервера/модели (generation_config с HF). ⚠ несравнимо с эталоном")
    print("  [4] свой — задать temp и др. руками (эксперименты). ⚠ несравнимо")
    sm = pick("Выбор [Enter=1]: ", 4)
    samp_env, suffix = {}, ""
    if sm == 2:
        samp_env["LADDER_SAMPLER"] = "recommended"; suffix = "-rec"
    elif sm == 3:
        samp_env["LADDER_SAMPLER"] = "native"; suffix = "-native"
    elif sm == 4:
        samp_env["LADDER_SAMPLER"] = "custom"
        print("  Enter = оставить эталонное значение:")
        for ptxt, ek in (("temperature [1.0]: ", "LADDER_TEMP"),
                         ("top_p [0.95]: ", "LADDER_TOP_P"),
                         ("top_k [20]: ", "LADDER_TOP_K"),
                         ("min_p [0]: ", "LADDER_MIN_P")):
            v = input("    " + ptxt).strip().replace(",", ".")
            if v:
                samp_env[ek] = v
        suffix = "-t" + samp_env["LADDER_TEMP"] if "LADDER_TEMP" in samp_env else "-custom"

    # --- трек / track ---
    print("\nЧто гонять / track:")
    print("  [1] всё: код (112 задач) + tool-use (30)   ~полный прогон")
    print("  [2] только код / code only")
    print("  [3] только tool-use / tools only")
    track = ("all", "code", "tools")[pick("Выбор [Enter=1]: ", 3) - 1]

    # --- число прогонов / repeats ---
    print("\nПрогонов на модель (среднее + разброс; 3–5 = «поставил на ночь»):")
    print("  [1] один   [2] три (сиды 42,43,44)   [3] пять")
    runs = ("1", "3", "5")[pick("Выбор [Enter=1]: ", 3) - 1]
    if runs != "1":
        suffix += "-x" + runs

    # --- имя результата / label ---
    default_label = safe_label(model or srv["kind"]) + suffix + ("-think" if think else "")
    label = input(f"\nИмя результата [Enter = {default_label}]: ").strip() or default_label
    label = safe_label(label)

    # --- запуск (эталонные условия, кроме явно выбранного сэмплера) ---
    env = dict(os.environ,
               PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               LADDER_LEVELS="easy,medium,hard",
               THINK="1" if think else "0",
               LADDER_MAX_TOKENS="32000" if think else "16384",
               LADDER_RUNS=runs,
               **samp_env)
    if model:
        env["LADDER_MODEL"] = model

    samp_name = {1: "эталонный сэмплер", 2: "сэмплер из справочника ⚠",
                 3: "native сэмплер ⚠", 4: "свой сэмплер ⚠"}[sm]
    print(f"\n▶ {srv['kind']} :{srv['port']} | {model or '(имя авто)'} | "
          f"{'think' if think else 'non-think'} | {samp_name} | {track} -> ladder_{label}.json\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "run_ladder.py"),
                        str(srv["port"]), label, track], env=env, cwd=HERE)
    if r.returncode == 0:
        print(f"\n✅ Готово! Результат: ladder_{label}.json")
        print("   При публикации цифр укажите: модель, квант/формат, think/non-think, сервер.")
        report = os.path.join(HERE, "report.html")
        if os.path.exists(report) and not os.environ.get("LADDER_NO_OPEN"):
            try:
                import webbrowser
                webbrowser.open(f"file:///{report.replace(os.sep, '/')}")
                print("   📊 Открываю сводный отчёт (report.html) в браузере...")
            except Exception:
                print(f"   📊 Сводный отчёт: {report}")
    else:
        print(f"\n❌ Раннер завершился с ошибкой (код {r.returncode}) — см. вывод выше.")
    return r.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nПрервано / interrupted")
        raise SystemExit(130)
