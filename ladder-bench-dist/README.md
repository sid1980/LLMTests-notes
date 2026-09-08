# 🪜 Coding Ladder Benchmark

A small, dependency-free benchmark for **local LLMs on coding + tool-use**. Generated code is
actually executed against real tests — no LLM-as-judge, no guessing. Runs against any
OpenAI-compatible `/v1/chat/completions` endpoint (vLLM, LM Studio, llama.cpp server, ...).

Небольшой бенч без зависимостей для **локальных LLM на кодинг + tool-use**. Код реально
исполняется на тестах (не «оценка моделью»). Работает с любым OpenAI-совместимым эндпоинтом.

---

## ✨ Highlights / Чем полезен

- **Реальное исполнение кода** на 142 задачах (easy/medium/hard + tool-use) — не LLM-судья, а `pass/fail` по настоящим тестам.
- 🛡️ **Песочница** для кода модели (PEP 578 audit-хуки): без сети, без процессов, без доступа к чужим файлам и секретам. Самопроверка: `python run_ladder.py selftest`.
- 🧪 **`probe_sampler.py`** — за 10 секунд проверяет, что твой сервер РЕАЛЬНО применяет параметры (temperature/top_k/seed/max_tokens), а не отбрасывает их молча. Запусти ДО бенча.
- 🧠 **Честный учёт reasoning**: в non-think режиме тест ловит «думанье» (поле `reasoning_content`/`reasoning`/`thinking` **и** блоки `<think>…</think>`, даже незакрытые и с подставленным сервером тегом). Если модель думала там, где не должна — прогон помечается **несравнимым с эталоном**.
- 📊 **HTML-отчёт** с сортировкой, маркерами галлюцинаций (обрыв/цикл/пусто/зависание), reasoning-хвостами и детализацией по каждой задаче.
- 🔁 **Мульти-прогон** (усреднение по сидам) + отпечаток условий (`conditions`) в каждом json — любой чужой результат самопроверяем на сравнимость.
- 🖥️ Запуск в один клик: веб-панель в браузере, терминальное меню или чистый CLI. Только stdlib, ничего не ставить.

---

## What it measures / Что меряет

| Track | Задач | Что делает |
|---|---|---|
| **code — easy** | 12 | HumanEval-класс, простые функции |
| **code — medium** | 60 | средние задачи (MBPP-класс) |
| **code — hard** | 40 | тяжёлые алгоритмы (LiveCodeBench-класс) |
| **tools** | 30 | function-calling: выбрать нужный инструмент + верные аргументы |

**code:** модель пишет решение → мы извлекаем код-блок → запускаем на тестах (stdin/unit).
Засчитывается только полное прохождение всех тестов задачи.
**tools:** модель получает набор инструментов и запрос → должна вызвать правильный tool с
правильными аргументами. Сверяем имя + аргументы.

Число в результате — **процент решённых** задач уровня.

---

## Requirements / Требования

- **Python 3.8+**, только стандартная библиотека (no pip installs).
- Запущенный локальный сервер модели с OpenAI-совместимым API (`/v1/chat/completions`):
  **vLLM** (:8000), **LM Studio** (:1234), **llama.cpp** `llama-server` (:8080), **Ollama** (:11434), text-gen-webui...
- 🛡️ Код модели исполняется **в песочнице** — см. раздел Safety ниже. / Model code runs
  **sandboxed** — see Safety below.

---

## 🛡️ Safety / Безопасность

Код, который пишет модель, исполняется **в песочнице** (`sandbox_runner.py`) на
audit-хуках Python (PEP 578 — установленный хук нельзя снять, это гарантия интерпретатора).
Model-generated code runs **sandboxed** via Python audit hooks (PEP 578 — once installed,
a hook cannot be removed; that's an interpreter guarantee).

**Заблокировано / Blocked:**

| | |
|---|---|
| 🌐 Сеть / Network | вся, включая localhost (socket, urllib, http, ftp, smtp, ...) |
| 🐚 Процессы / Processes | subprocess, `os.system`/`exec`/`spawn`/`fork`, multiprocessing |
| 🗑️ Файлы / Files | запись/удаление/переименование **вне** временной папки теста |
| 🔑 Секреты / Secrets | чистое окружение — переменные среды (ключи, токены) коду не видны |
| 🔧 Прочее / Misc | реестр Windows (winreg), ctypes (канал обхода хуков), `os.kill` |

Плюс: таймаут 20с на задачу, изолированный режим Python (`-I`), лимит памяти на Unix.
`TEMP`/`TMP`/`TMPDIR` кода модели указывают внутрь временной папки теста — `tempfile`
и запись в `os.devnull` работают, как и до песочницы. Против обхода блок-листа
импортов через `importlib.import_module()` (он не генерирует audit-событие) в
`sys.modules` подсажены заглушки для ctypes/multiprocessing/winreg: любое их
использование блокируется и логируется. Попытки блокировки пишутся напрямую в fd 2 —
код модели не может скрыть их, подменив `sys.stderr`.
Каждая заблокированная попытка **логируется**: в консоль (строка `🛡️ [SANDBOX] blocked: ...`)
и в итоговый json (поле `sandbox` у задачи + счётчик `sandbox_blocked_tasks`) — даже если код
модели перехватил ошибку и задача прошла. Ничего не скрывается. / Every blocked attempt is
**logged** to console and the results json — even if the model code swallowed the exception.

**Проверьте сами / Verify yourself (5 секунд, сервер не нужен):**

```bash
python run_ladder.py selftest
```

Самотест доказывает: удаление/перезапись чужих файлов, интернет, localhost, запуск процессов,
ctypes, обход через `importlib.import_module` и dotted-import (`ctypes.util`) — блокируются;
честный код, threading, tempfile, `os.devnull` и запись в свою временную папку — работают;
а попытки блокировки видны в логе даже если код подменил `sys.stderr`.

**Честная оговорка / Honest caveat:** это защита от *случайно-вредного кода LLM* (главный
реальный риск бенчмарка), а не военная крепость. Против целенаправленного человека-атакующего
audit-хуки не абсолютны; известные остаточные лазейки: `dir_fd=` в os-вызовах (его путь не
попадает в audit-аргументы CPython) и ручная чистка `sys.modules` перед `importlib.import_module`.
Параноидальный вариант — гоняйте в VM/WSL/контейнере, бенч этому не
мешает. / This defends against *accidentally harmful LLM code* — the realistic threat here —
not against a determined human attacker. For full paranoia, run inside a VM/container.

**Сравнимость цифр / Score comparability:** песочница **не влияет на результаты** — промпты,
сэмплер, seed, лимиты, извлечение кода, критерий зачёта и таймаут не менялись; блокируются
только операции, которые ни одному честному решению не нужны (во всех 112 задачах их нет).
Семантика исполнения проверена на идентичность (`__main__`, stdin, коды возврата, рекурсия,
utf-8). Прогоны до песочницы (`results-example/`) и после — сравнимы. Если код модели всё же
упёрся в блокировку — это видно в json по полю `sandbox`. / The sandbox does not affect
scores: only operations no valid solution needs are blocked, and execution semantics are
verified identical. Pre-sandbox reference runs remain comparable.

---

## Run / Запуск

### 🧪 Сначала (по желанию): проверь сервер / Sanity-check the server first

Разные серверы по-разному честны с параметрами запроса: некоторые молча отбрасывают
`top_k`/`min_p` или даже `chat_template_kwargs`. `probe_sampler.py` за 10 секунд
проверяет по эффекту, что сервер РЕАЛЬНО применяет temperature/top_k/seed/max_tokens —
чтобы цифры бенча не врали. / Verify by effect that your server actually applies the
sampler params before you trust the numbers.

```bash
python probe_sampler.py 1234        # порт или полный URL, как у run_ladder
```

### 🖥️ Самое удобное: веб-панель в браузере (двойной клик)

**`START_BENCH_WEB.bat`** (любая ОС: `python bench_web.py`) — открывает страницу в браузере:
скан локальных серверов (vLLM, LM Studio, Ollama, llama.cpp), выбор модели, все параметры
(think, сэмплер, число прогонов, уровни), кнопка Старт, **живой лог** и кнопка «Отчёт».
**🌡 Серия температур**: впиши «1.0, 0.6, 0.2» — панель прогонит тест на каждой по очереди
сама («поставил и ушёл»), каждый попадёт в отчёт отдельной строкой `-t1.0`/`-t0.6`/...
Всё локально (127.0.0.1), ничего не устанавливается. / Web control panel: scan servers,
set params (incl. a temperature sweep queue), start, watch the live log — stdlib only.

### 🖱️ Или терминальное меню

**`START_BENCH.bat`** (любая ОС: `python start_bench.py`) — то же самое в терминале:
сам сканирует серверы, показывает найденное, даёт выбрать сервер/модель/режим/сэмплер/число
прогонов — и запускает. / Same flow as an interactive terminal menu.

### ⭐ Reference-скрипт (объективное сравнение из командной строки)

Чтобы ваши цифры были **сравнимы с эталонными** (`results-example/`) — запускайте через
готовый скрипт, он забивает ТОЧНО те же условия (сэмплер, уровни, лимиты). Ничего настраивать
не надо. / For comparable numbers use the reference wrapper — it locks identical conditions.

```bash
# Linux / Mac:
./run_reference.sh <port> <label>            # non-thinking (как большинство наших прогонов)
./run_reference.sh <port> <label> think      # thinking-режим (для reasoning-моделей, 32k budget)

# Windows:
run_reference.bat <port> <label>
run_reference.bat <port> <label> think
```

### Или напрямую (гибко) / Or directly (flexible)

```bash
python run_ladder.py <port> <label> [code|tools|all]
python run_ladder.py 8000 my-model all          # оба трека (vLLM дефолт :8000)
python run_ladder.py 1234 my-model code         # только код (LM Studio дефолт :1234)
python run_ladder.py 11434 my-model all         # Ollama (дефолт :11434)
python run_ladder.py http://192.168.1.5:1234 my-model   # вместо порта можно полный URL
```

Имя модели определяется **автоматически** (запрос `/v1/models` — берётся первая; vLLM и
LM Studio имя вообще игнорируют, Ollama требует настоящее). Если на сервере несколько
моделей — выбрать нужную: `LADDER_MODEL=имя`. / Model name is auto-detected from
`/v1/models`; override with `LADDER_MODEL` env when the server hosts several.

Результат печатается в консоль и сохраняется в `ladder_<label>.json`, плюс автоматически
обновляется сводный **`report.html`** (см. раздел «Отчёт» ниже).
**Каждый json содержит блок `conditions`** (сэмплер, think, max_tokens, уровни, число задач) —
по нему любой прогон самопроверяем: совпадают ли условия с эталонными. Если сэмплер изменён —
раннер печатает `⚠️ WARNING` и цифры считать несравнимыми.

### Env knobs / Переменные окружения

| Env | Default | Что делает |
|---|---|---|
| `THINK` | `0` | `1` = reasoning-режим (шлёт `enable_thinking:true`). `0` (non-think) шлёт `enable_thinking:false` через `chat_template_kwargs`. ⚠️ Это поле понимают **vLLM** и **llama.cpp** (`--jinja`); **LM Studio** и **Ollama** (OpenAI-режим) молча его игнорируют — там reasoning отключается **настройкой сервера** (тумблер reasoning у модели в LM Studio; `--reasoning-budget 0` у llama.cpp; `think:false` в нативном API Ollama). Из тела запроса надёжно выключить нельзя. Поэтому тест **логирует** думанье: если модель думала в non-think — в отчёте флаг `🧠` + хвост «о чём думала», а прогон помечается **несравнимым с эталоном** (эталон — настоящий non-think). |
| `LADDER_NOTHINK` | `0` | `1` = дополнительно дописать токен `/no_think` в конец промпта (старый «мягкий переключатель» Qwen). По умолчанию **выкл**: в новых Qwen (3-2507+) он не действует (проверено — qwen3.5-9b думала 12/12), семейство-специфичен (`/no_think` Qwen, `/nothink` GLM) и **меняет текст промпта** → на temp>0 сдвигает сэмплинг и ломает сравнимость. Оставлено только для экспериментов. |
| `LADDER_MAX_TOKENS` | `16384` | Лимит токенов ответа. Для THINK ставьте **32000+** (иначе reasoning съест бюджет и `content` придёт пустым). |
| `LADDER_LEVELS` | `easy,medium,hard` | Какие уровни кода гонять. Напр. `hard` — только hard (быстрее). Трек tools не зависит. |
| `LADDER_MODEL` | *(авто)* | Имя модели в запросах. По умолчанию берётся с сервера (`/v1/models`, первая). Нужно если на сервере несколько моделей (Ollama, LM Studio). |
| `LADDER_RUNS` | `1` | Число прогонов: `3`/`5` — каждый со своим сидом (42, 43, ...), в json среднее + разброс + стабильность каждой задачи. Одиночный прогон может «гулять». |
| `LADDER_SAMPLER` | `reference` | Режим сэмплера: `reference` — эталонный Qwen (единственный сравнимый); `recommended` — рекомендации для семейства модели из `sampler_presets.json` (Qwen3.5/3.6, Coder-Next, GLM, Gemma; unsloth-доки; нет в справочнике → как native); `native` — параметры не шлются, работают дефолты сервера/модели (generation_config с HF); `custom` — эталон + переопределения ниже. |
| `LADDER_TEMP` `LADDER_TOP_P` `LADDER_TOP_K` `LADDER_MIN_P` `LADDER_PRESENCE` `LADDER_SEED` | *(эталон)* | Переопределения для `LADDER_SAMPLER=custom` — эксперименты с температурой и т.д. |
| `LADDER_UNSAFE` | `0` | `1` = ВЫКЛЮЧИТЬ песочницу (старое небезопасное поведение). Не рекомендуется; в json попадёт `"sandbox": false`. |

```bash
# эксперимент: та же модель на temp 0.2 (в отчёте будет помечено «свой сэмплер ⚠»):
LADDER_SAMPLER=custom LADDER_TEMP=0.2 python run_ladder.py 1234 my-model-t02 code
```

---

## 📊 Отчёт / Report

После каждого прогона автоматически пересобирается **`report.html`** — открой в браузере
(интерактивный лаунчер открывает его сам):

- **Таблица всех прогонов**: ваши + эталонные рядом, сортировка кликом по столбцу;
  % по уровням с барами, режим think, сэмплер, **токены и скорость генерации (tok/s)**.
- **Маркеры галлюцинаций** (столбец «аномалии»): ✂ обрыв по лимиту токенов,
  🔁 зацикливание (периодичный хвост ответа), ∅ пустой ответ, ⏱ зависание кода.
- **Reasoning-маркеры**: 🧠 модель думала (с хвостом «о чём» по клику); 🔧 код взят из
  размышлений (модель положила решение внутрь `<think>` — зачёт с оговоркой).
- **Клик по строке — детали**: какие задачи провалены и почему, флаги по каждой,
  хвост «бреда» модели для подозрительных ответов — пощупать глазами.
- Прогоны с неэталонным сэмплером помечаются «⚠ свой сэмплер»/«⚠ native», а non-think-прогон,
  где модель всё же думала, — «⚠ НЕ сравнимо» — их цифры с эталонными **не сравнивать**.

Пересобрать руками: `python make_report.py`. / Rebuilt automatically after every run;
shows all runs (yours + reference) with hallucination markers and per-task drill-down.

```bash
# think-модель, полный бюджет, только hard+tools:
THINK=1 LADDER_MAX_TOKENS=32000 LADDER_LEVELS=hard python run_ladder.py 8000 my-model all
```

---

## ⚠️ Fair comparison / Честное сравнение

Чтобы цифры были сравнимы между моделями и людьми — **фиксируйте сэмплер**. По умолчанию в
раннере зашит официальный Qwen non-thinking сэмплер:

```
temperature 1.0 · top_p 0.95 · top_k 20 · min_p 0 · seed 42 · non-think
```

- Меняете модель другого семейства → используйте её родной рекомендованный сэмплер, но
  **укажите это** при публикации цифр (иначе несравнимо).
- `temperature` сильно влияет на код — прогоны на разной temp между собой не сравнивать.
- `seed 42` даёт воспроизводимость.
- ⚠️ **Ollama:** его OpenAI-совместимый режим игнорирует `top_k`/`min_p` из запроса —
  цифры через Ollama считайте **примерными**, с reference-прогонами сравнивайте осторожно.
  / Ollama's OpenAI endpoint drops `top_k`/`min_p` — treat those numbers as approximate.

При публикации указывайте: **модель, квант/формат, сэмплер, think/non-think, число экспертов
(для MoE)** — иначе цифра ни о чём.

---

## Example results / Пример результатов

В папке `results-example/` — наши прогоны на локальных INT4-квантах (RTX 4090, vLLM, non-think,
сэмплер выше). Используйте как ориентир «что нормально»:

| Модель (INT4) | арх | hard | tools |
|---|---|:--:|:--:|
| Qwen3.6-27B base (wide-квант) | dense | **78** | 83 |
| Qwen3.6-27B base | dense | 70 | 83 |
| Qwen3.6-27B abliterated (наша расцензурка) | dense | 70 | **87** |
| Qwen3.5-27B base (wide) | dense | 68 | 80 |
| Qwen3.6-35B-A3B base | MoE | 50 | 80 |
| Qwopus-27B-Coder (Opus-distill) | dense | 45 | 80 |
| Qwopus-35B-Coder (Opus-distill) | MoE | 45 | 80 |
| huihui-Claude 35B (abliterated) | MoE | 38 | 73 |
| Qwopus-27B-Coder censored | dense | 35 | **87** |

(полные json — в `results-example/`, поле `results.code.by_level` и `results.tools`)

---

## Files / Файлы

```
START_BENCH_WEB.bat   — двойной клик: веб-панель в браузере (скан/параметры/лог/отчёт)
bench_web.py          — та же панель на любой ОС: python bench_web.py
START_BENCH.bat       — двойной клик: терминальное меню (Windows)
start_bench.py        — то же меню на любой ОС: python start_bench.py
run_ladder.py         — раннер (запускаете его)
probe_sampler.py      — проверка сервера: применяет ли он параметры сэмплера (запустить ДО бенча)
sampler_presets.json  — справочник рекомендованных сэмплеров по семействам (дополняйте!)
make_report.py        — сводный report.html: все прогоны, аномалии, детали по клику
sandbox_runner.py     — песочница для кода модели (audit-хуки; см. Safety)
ladder_cases.json     — 112 код-задач (easy 12 / medium 60 / hard 40)
tooluse_cases.json    — 30 задач function-calling
results-example/      — наши эталонные прогоны (пример формата + ориентир)
```

## Notes / Заметки

- Формат `ladder_cases.json`: `{id, level, type: func|stdin, prompt, test_code}`.
- Формат `tooluse_cases.json`: `{id, category, n_tools, tools, query, expected_name, expected_args}`.
- Код извлекается из ```` ```python ```` блока (берётся последний блок).
- Таймаут исполнения одной задачи — 20 сек (защита от зависаний).
- В json каждого прогона: блок `usage` (токены, скорость, счётчики аномалий) и
  по-задачные `flags`/`tail` для подозрительных ответов (обрыв/цикл/пусто).

Сделано для подбора локальной кодинг-модели. Форкайте, добавляйте задачи, делитесь цифрами 🙂
