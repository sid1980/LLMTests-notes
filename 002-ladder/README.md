# 🧠 cbench — бенчмарк знания языка Си для локальных LLM

Бенч без внешних зависимостей (только стандартная библиотека Python 3.8+) для
оценки **знания языка Си** локальными LLM. Модель пишет код на Си → код
**компилируется** → **исполняется на реальных тестах** (pass/fail, без LLM-судьи).
Работает с любым OpenAI-совместимым эндпоинтом `/v1/chat/completions` в трёх
вариантах: **внешний провайдер (OpenAI)**, **llama.cpp-server**, **LM Studio**
(в т.ч. через reverse-proxy, например Caddy). Кроссплатформенно: **Windows и Linux**.

Подробности: [`ARCHITECTURE.md`](ARCHITECTURE.md), руководство пользователя:
[`docs/UserGuide/user_guide.md`](docs/UserGuide/user_guide.md).

---

## Требования

- Python 3.8+ (только stdlib, ничего не ставить).
- Компилятор Си: **gcc/clang** (Linux) или **MSVC `cl.exe`** (Windows);
  на Windows также работает clang из MSYS2/PATH.
- Запущенный сервер модели с OpenAI-совместимым API.

## Быстрый старт

```bash
# 0. Проверить окружение (компилятор + песочница):
python run_cbench.py selftest

# 1. Проверить банк задач:
python run_cbench.py validate

# 2. Проверить, что сервер честно применяет параметры (опционально):
python probe_sampler.py 1234

# 3. Прогнать бенч:
python run_cbench.py 1234 my-model code                 # LM Studio локально
python run_cbench.py http://192.168.56.1:1234 my-model code   # LM Studio через Caddy
python run_cbench.py 8080 my-model code                 # llama.cpp
python run_cbench.py https://api.openai.com/v1 my-model code --provider openai --api-key sk-...
```

Результат — `cbench_<label>.json` + автообновляемый `report.html`.

## Запуск под Windows (cmd / PowerShell)

Переменные окружения задаются иначе, чем в bash (`VAR=value command` там не
работает):

```bat
:: cmd.exe — на время команды (через &&):
set CBENCH_MAX_TOKENS=32000 && python run_cbench.py 1234 my-model code

:: либо на время сессии:
set CBENCH_MAX_TOKENS=32000
python run_cbench.py 1234 my-model code
```

```powershell
# PowerShell:
$env:CBENCH_MAX_TOKENS=32000; python run_cbench.py 1234 my-model code
```

Подробности — в руководстве (`docs/UserGuide/user_guide.md`, раздел «Синтаксис
команд под Windows»).

## Запуск через reverse-proxy (Caddy)

Если LM Studio проксируется Caddy:

```text
caddy_windows_amd64.exe reverse-proxy --from http://192.168.56.1:1234 --to 192.168.1.70:1234
```

то бенчмарк обращается на **внешний** адрес прокси:

```bash
CBENCH_PROVIDER=lmstudio CBENCH_BASE_URL=http://192.168.56.1:1234 python run_cbench.py http://192.168.56.1:1234 my-model code
```

## Основные переменные окружения

| Переменная | По умолчанию | Что делает |
|---|---|---|
| `CBENCH_PROVIDER` | авто | `openai` / `llamacpp` / `lmstudio` |
| `CBENCH_BASE_URL` | по провайдеру | базовый URL (порт или http(s)://…) |
| `CBENCH_MODEL` | авто (`/v1/models`) | имя модели |
| `CBENCH_API_KEY` | — | ключ для внешнего провайдера |
| `CBENCH_CC` | авто | путь к компилятору (gcc/clang/cl) |
| `CBENCH_LEVELS` | `easy,medium,hard` | какие уровни гонять |
| `CBENCH_TOPICS` | — | темы через запятую (например `files`) |
| `CBENCH_RUNS` | `1` | число прогонов (усреднение по сидам) |
| `CBENCH_SAMPLER` | `reference` | `reference`/`native`/`recommended`/`custom` |
| `CBENCH_SANITIZERS` | `0` | `1` — диагностический прогон (ASan/UBSan) |
| `CBENCH_UNSAFE` | `0` | `1` — ВЫКЛЮЧИТЬ песочницу |
| `THINK` | `0` | `1` — reasoning-режим |
| `CBENCH_MAX_TOKENS` | `16384` | лимит токенов ответа (для думающих моделей — 32000+) |
| `CBENCH_HTTP_TIMEOUT` | `1800` | таймаут HTTP-запроса к модели, сек |

Температура по умолчанию — `0.15` (эталонный сэмплер `reference`). Изменяется
через `CBENCH_SAMPLER=custom CBENCH_TEMP=0.3` или константу `REF_SAMP` в
`cbench/sampler.py`. Думающие модели могут съедать токен-бюджет и обрывать код —
поднимайте `CBENCH_MAX_TOKENS`; если сервер отвечает медленно — `CBENCH_HTTP_TIMEOUT`.

## Файлы

```
run_cbench.py         — точка входа (CLI)
cbench/               — пакет: model/ llm/ exec/ data/ codegen/ runner/config/report/sampler
cases/cases.json      — банк задач Си (63 задачи: math/arrays/strings/files/bitops)
solutions/*.c         — эталонные решения (по файлу на задачу)
build_cases.py        — пересборка cases/cases.json из solutions/*.c
verify_solutions.py   — прогон каждого решения через настоящий Grader
sampler_presets.json  — рекомендованные сэмплеры по семействам моделей
probe_sampler.py      — проверка честности параметров сервера
make_report.py        — пересборка report.html
run_reference.bat/.sh — эталонные обёртки (фиксированные условия)
docs/UserGuide/       — руководство пользователя (md + HTML с поиском)
```

## Безопасность

Код модели компилируется и исполняется в песочнице (таймаут, чистое окружение,
ограничения ресурсов на Linux, process group + Job Object на Windows). Это защита
от *случайно-вредного кода LLM*, а не крепость против человека — при паранойе
гоняйте в VM/WSL/Docker. Подробнее — в `ARCHITECTURE.md` (раздел «Песочница»).

## Сравнимость цифр

Каждый JSON содержит блок `conditions` (сэмплер, think, компилятор, платформа,
hash банка задач) — по нему любой прогон самопроверяем. При публикации указывайте:
модель, квант/формат, think/non-think, компилятор, сэмплер.
