# ARCHITECTURE — cbench (бенчмарк знания языка Си для локальных LLM)

## 1. Назначение

`cbench` — бенчмарк без внешних зависимостей (только стандартная библиотека
Python 3.8+) для оценки **знания языка Си** локальными LLM. Модель пишет код на
Си → код **компилируется** → исполняется на **реальных тестах** (pass/fail, без
LLM-судьи). Работает с любым OpenAI-совместимым эндпоинтом
`/v1/chat/completions` в трёх вариантах подключения:

1. **внешний провайдер** по протоколу OpenAI (base URL + API key);
2. **llama.cpp-server** (локальный, `http://127.0.0.1:8080`);
3. **LM Studio** (локальный, `http://127.0.0.1:1234`; допускается reverse-proxy,
   например Caddy).

Кроссплатформенно: **Windows** и **Linux**.

## 2. Принципы проектирования

- **Минимальная связанность.** Слои общаются через протоколы/интерфейсы и
  чистые структуры данных. Единственная точка, знающая «всё» — `runner.py`
  (композиционный корень).
- **Адаптеры вместо ветвлений.** Три провайдера = один HTTP-клиент + три
  конфига; компиляторы = один протокол + несколько реализаций; две ОС = один
  протокол `Sandbox` + две реализации.
- **Домен без I/O.** `model/` — чистые `@dataclass`, не зависят ни от чего,
  кроме stdlib.
- **Честность измерений.** В каждом прогоне сохраняется `conditions`-отпечаток
  условий; фиксируются маркеры «галлюцинаций» (обрыв по лимиту / цикл / пусто);
  честная оговорка о границах песочницы.

## 3. Слои и направление зависимостей

```
        ┌──────────────────────────────────────────────────┐
СЛОЙ 3  │ runner.py (оркестратор)  config.py  report.py   │  знает всё
        └────────────────▲─────────────────▲───────────────┘
                         │                 │
        ┌────────────────┴─────────────────┴───────────────┐
СЛОЙ 1  │ llm/  exec/  data/  codegen/  sampler.py        │  адаптеры (не знают друг друга)
        └────────────────▲─────────────────────────────────┘
                         │
        ┌────────────────┴─────────────────────────────────┐
СЛОЙ 0  │ model/  (Case, TestSpec, Result, ...)           │  чистые данные
        └──────────────────────────────────────────────────┘
```

Правила:

- `model/` импортирует только `dataclasses`/stdlib.
- Адаптеры (`llm/`, `exec/`, `data/`, `codegen/`) импортируют **только `model`**
  и не знают друг о друге (LLM не знает про компилятор, компилятор не знает про
  LLM).
- `runner.py` — единственный модуль, который импортирует все адаптеры и
  связывает их в работающий pipeline (composition root).
- `config.py`, `sampler.py`, `report.py` зависят только от `model` (+ JSON-данных).

## 4. Модули (ответственность)

| Модуль | Слой | Отвечает за |
|---|---|---|
| `model/case.py` | 0 | `Case`, `TestSpec`, `ExpectedResult`, `FileSpec`, `CaseKind`, `IOMode`, `Topic`, `Level` |
| `model/result.py` | 0 | `ModelReply`, `CompileResult`, `RunOutcome`, `TaskResult`, `RunSummary`, `Conditions`, `ProviderConfig` |
| `data/loader.py` | 1 | загрузка и валидация `cases/cases.json` → `list[Case]`, фильтры, hash банка |
| `llm/client.py` | 1 | протокол `LLMClient`, реализация `OpenAICompatClient` (urllib) |
| `llm/providers.py` | 1 | `ProviderConfig` + пресеты `openai` / `llamacpp` / `lmstudio` |
| `llm/reasoning.py` | 1 | вырезание `<think>`/`reasoning_content`, маркеры cut/loop/empty |
| `codegen/extract.py` | 1 | извлечение C-кода из ```` ```c ````-блоков (и plain-fallback) |
| `exec/compiler.py` | 1 | протокол `Compiler` + `GccCompiler`/`ClangCompiler`/`MsvcCompiler` + `detect()` |
| `exec/sandbox.py` | 1 | протокол `Sandbox` + `LinuxSandbox`/`WindowsSandbox` |
| `exec/grader.py` | 1 | compile → run → verify по `CaseKind`/`IOMode` |
| `sampler.py` | 1 | пресеты сэмплера (`sampler_presets.json`), эталонные условия |
| `report.py` | 2 | сборка итогового JSON и HTML-отчёта |
| `config.py` | 3 | CLI/env → `RunConfig`, `Conditions`, выбор провайдера/компилятора |
| `runner.py` | 3 | оркестрация, агрегация мульти-прогонов, запись результата |

## 5. Модель данных

### 5.1 Сущности

| Сущность | Поля (ключевые) | Назначение |
|---|---|---|
| `Case` | `id, topic, level, kind, io_mode, prompt, compile_flags, harness, tests` | одна задача |
| `TestSpec` | `argv, stdin, files, expected, timeout_s` | как прогнать и проверить один запуск |
| `FileSpec` | `name, content` | входной/выходной файл |
| `ExpectedResult` | `stdout, files, exit_code` | эталон для сверки |
| `ModelReply` | `content, reasoning, flags` | что вернула модель |
| `CompileResult` | `ok, exit_code, stdout, stderr, tool, version` | итог компиляции |
| `RunOutcome` | `exit_code, stdout, stderr, timeout, sandbox_events, sandbox_degraded` | итог запуска бинарника |
| `TaskResult` | `pass, why, flags, tok, tail, compile, runs` | итог по задаче |
| `RunSummary` | `by_level, by_topic, per_run, usage, sandbox_blocked` | агрегат прогона |
| `Conditions` | `sampler, sampler_mode, think, max_tokens, n_runs, base_seed, levels, topics, compiler, sandbox, case_bank_hash, platform` | отпечаток условий |
| `ProviderConfig` | `name, base_url, api_key, model, enable_thinking_support` | конфиг подключения |

### 5.2 `cases/cases.json` — схема одной задачи

```jsonc
{
  "id": "c-matrix-001",
  "topic": "files",              // тема: arrays|pointers|memory|strings|structs|files|bitops|recursion|...
  "level": "easy",               // easy | medium | hard
  "kind": "program",             // function | program
  "io_mode": "argv_files",       // stdin_stdout | argv | files | argv_files  (только для kind=program)
  "compile_flags": ["-std=c11"],
  "prompt": "…контракт задачи (текст для модели)…",
  "harness": "…",                // только для kind=function: main() с проверками
  "tests": [                     // только для kind=program: список запусков
    {
      "argv": ["matrix1.txt", "matrix2.txt"],
      "stdin": "",
      "files": [ { "name": "matrix1.txt", "content": "2 2\n1 2\n3 4\n" } ],
      "expected": {
        "stdout": "…",                                   // сравнение с нормализацией хвостовых пробелов
        "files": [ { "name": "out.txt", "content": "…" } ],  // опционально: выходные файлы
        "exit_code": 0
      },
      "timeout_s": 20
    }
  ]
}
```

### 5.3 Типы задач и режимы ввода-вывода

`kind` и `io_mode` разделены намеренно — чтобы комбинировать без новых типов:

- **`function`** — модель дописывает одну функцию (в `prompt` даны `#include` +
  сигнатура), снизу приклеивается `harness` (`main()` с проверками).
- **`program` + `stdin_stdout`** — полная программа: stdin → stdout.
- **`program` + `argv`** — аргументы командной строки.
- **`program` + `files`** — чтение/запись файлов (имена фиксированы в `prompt`).
- **`program` + `argv_files`** — имена файлов передаются через argv (пример:
  MatrixOp).

## 6. Три варианта подключения (providers)

Все три говорят по OpenAI-протоколу → один `OpenAICompatClient`. Различие —
только `ProviderConfig`:

| Пресет | base_url по умолч. | api_key | имя модели | enable_thinking |
|---|---|---|---|---|
| `openai` | из env/аргумента (https…) | обязателен | обязательно | не шлётся |
| `llamacpp` | `http://127.0.0.1:8080` | нет | авто `/v1/models` | `chat_template_kwargs` |
| `lmstudio` | `http://127.0.0.1:1234` | нет | авто `/v1/models` | тумблер сервера |

Выбор: `CBENCH_PROVIDER` (или по base_url/порту). Имя модели: `CBENCH_MODEL`
или авто-детект через `/v1/models`.

### 6.1 Работа через reverse-proxy (Caddy)

Возможна конфигурация, когда LM Studio проксируется Caddy:

```text
caddy_windows_amd64.exe reverse-proxy --from http://192.168.56.1:1234 --to 192.168.1.70:1234
```

Тогда бенчмарк обращается на **внешний** адрес прокси:

```text
CBENCH_PROVIDER=lmstudio
CBENCH_BASE_URL=http://192.168.56.1:1234
```

Внутренний адрес (`192.168.1.70:1234`) знает только Caddy; в конфигурацию
бенчмарка он **не попадает**.

## 7. Пайплайн исполнения

```
Case.prompt ──▶ LLMClient.generate ──▶ reasoning.split ──▶ extract_c
     ──▶ compiler.compile (таймаут) ──▶ sandbox.run (каждый TestSpec)
     ──▶ grader.verify ──▶ TaskResult ──▶ RunSummary + Conditions ──▶ JSON + HTML
```

## 8. Компиляторы

`Compiler` (протокол): `compile(source_path, out_path, flags, cwd) -> CompileResult`.

- `GccCompiler` / `ClangCompiler`: `cc -std=c11 -O2 -Wall -Wextra -Wpedantic -o out src.c`.
- `MsvcCompiler`: поиск `cl.exe` через `vswhere` + загрузка окружения
  `vcvars64.bat`, компиляция `cl /nologo /O2 /W3 src.c /Fe:out.exe`.
- `detect()`: override `CBENCH_CC` → `shutil.which("cc|clang|gcc")` →
  на Windows `vswhere` для MSVC.

Два профиля компиляции:

- **reference** (идёт в score): `-O2 -Wall -Wextra -Wpedantic`.
- **diagnostic** (опционально, `CBENCH_SANITIZERS=1`): `-fsanitize=address,undefined`
  (GCC/Clang) — ловит выход за границы, use-after-free, переполнение, UB. Не
  влияет на основной score, диагностика сохраняется отдельно.

Компиляция: таймаут, scrubbed env, ограниченные пути, лимит размера исходника.

## 9. Песочница (нативный код)

`Sandbox` (протокол): `run(binary, argv, stdin, cwd, files, timeout) -> RunOutcome`.

Общее для обеих ОС:

- cwd = временная папка теста (туда же кладутся входные файлы);
- чистое окружение (ключи/токены не видны), остаются только безопасные переменные;
- wall-clock таймаут + убийство дерева процессов;
- ограничение stdout/stderr;
- удаление временной папки после теста.

Linux (`LinuxSandbox`):

- `setsid` (отдельная process group);
- `resource.setrlimit`: `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`, `RLIMIT_NPROC`, `RLIMIT_NOFILE`;
- сеть best-effort через `unshare` (если разрешено; иначе `sandbox_degraded`).

Windows (`WindowsSandbox`):

- `CREATE_NEW_PROCESS_GROUP` + завершение дерева `taskkill /T /F`;
- лимиты памяти/CPU best-effort через Job Object (`ctypes`); при недоступности —
  предупреждение `sandbox_degraded`;
- надёжная блокировка сети не гарантируется.

**Честная оговорка:** это защита от *случайно-вредного кода LLM* (реальный риск
бенчмарка), а не военная крепость против целенаправленного человека. При
паранойе — гоняйте в VM/WSL/Docker/контейнере; бенчу это не мешает.

## 10. Сэмплер и conditions-отпечаток

Режимы (env `CBENCH_SAMPLER`):

- `reference` (дефолт) — фиксированный эталонный сэмплер (температура `0.15`,
  `top_p 0.95`, `top_k 20`, `seed 42`), единственный, чьи цифры сравнимы с
  эталонными;
- `native` — параметры не шлются, работают дефолты сервера/модели;
- `recommended` — параметры из `sampler_presets.json` по имени модели;
- `custom` — эталон + переопределения из env (`CBENCH_TEMP`, `CBENCH_TOP_P`, …).

`Conditions` (отпечаток) сохраняется в каждом JSON: sampler, sampler_mode, think,
max_tokens, http_timeout, n_runs, base_seed, levels, topics, exec_timeout,
compiler (имя + версия + флаги), sandbox (вкл/режим/degraded), platform,
case_bank_hash, n_cases. Неэталонный сэмплер или «думанье» в non-think-режиме →
прогон помечается несравнимым.

Таймаут HTTP-запроса к модели задаётся `CBENCH_HTTP_TIMEOUT` (по умолчанию 1800
сек) или флагом `--timeout` — для медленных (например, думающих) серверов.

## 11. Отчёт

После прогона — `cbench_<label>.json` + HTML (`make_report.py`): таблица прогонов
(ваши + эталонные), процент по уровням и темам с барами, маркеры аномалий
(обрыв/цикл/пусто/таймаут), токены и скорость, детали по задаче (почему
провалена, expected/actual, stderr компилятора и программы, reasoning-хвосты).

## 12. Точки расширения

- Новая задача → строка в `cases/cases.json` (валидация на входе), либо
  `solutions/<id>.c` + запись в `SPECS` в `build_cases.py` (пересборка банка),
  затем `verify_solutions.py` (прогон решений через Grader).
- Новая тема → новое значение `topic`.
- Новый провайдер → `ProviderConfig` в `llm/providers.py`.
- Новый компилятор → реализация `Compiler` + регистрация в `detect()`.
- Новая ОС-песочница → реализация `Sandbox`.

## 13. Кроссплатформенность

- Всё на stdlib; пути через `pathlib`; принудительная UTF-8 для консоли и файлов.
- Windows: MSVC (`vcvars64.bat`) или clang из PATH; `taskkill /T /F`; Job Object.
- Linux: gcc/clang; `setrlimit`; `setsid`.
- Результаты разных компиляторов сравнимы настолько, насколько код не содержит
  undefined behavior (UB-задачи — только при явной пометке `diagnostic`).
