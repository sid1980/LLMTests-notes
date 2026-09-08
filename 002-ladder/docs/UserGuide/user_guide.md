# Руководство пользователя — cbench

Бенчмарк для оценки **знания языка Си** локальными LLM. Модель пишет код на Си,
он **компилируется** и **исполняется на реальных тестах** (pass/fail, без
LLM-судьи). Работает с любым OpenAI-совместимым сервером в трёх вариантах
подключения: внешний провайдер (OpenAI), llama.cpp-server, LM Studio (в том числе
через reverse-proxy, например Caddy).

---

## 1. Что измеряет бенчмарк

Для каждой задачи модель получает текстовое условие, пишет решение на Си, а
бенчмарк:

1. извлекает код из ответа;
2. **компилирует** его (gcc/clang/MSVC);
3. **запускает** скомпилированный бинарник в песочнице;
4. сверяет вывод с эталоном (`pass` / `fail`).

Результат — **процент решённых задач** по уровням сложности (`easy`, `medium`,
`hard`) и по темам (`math`, `arrays`, `strings`, `bitops`, `files`). Никакой
«оценки другой моделью» — только реальное исполнение.

Большинство задач — **вычислительные** («задачи на просчёт») из сборника
[cppstudio.com](http://cppstudio.com/cat/285/), адаптированные под Си. Уровни
отображаются так: категории Beginner и Easy → `easy`, Normal → `medium`,
Hard и Experienced → `hard`.

Типы задач:

| Тип | Описание |
|---|---|
| `function` | модель дописывает одну функцию, тест через `main()` с проверками |
| `program` + stdin/stdout | полная программа: читает stdin, пишет stdout |
| `program` + argv | аргументы командной строки |
| `program` + files | чтение/запись файлов |
| `program` + argv_files | имена файлов передаются через argv (пример — MatrixOp) |

---

## 2. Требования и установка

- **Python 3.8+** — только стандартная библиотека, ничего устанавливать не нужно.
- **Компилятор Си**: на Linux — `gcc` или `clang`; на Windows — MSVC `cl.exe`
  (Visual Studio Build Tools) или clang из PATH (например, MSYS2 clang64).
- Запущенный сервер модели с OpenAI-совместимым API.

Проверка окружения (компилятор + компиляция + запуск + таймаут):

```bash
python run_cbench.py selftest
```

### 2.1 Синтаксис команд под Windows (cmd / PowerShell)

Все примеры ниже даны для **bash** (Linux/macOS). Под Windows конструкция
`VAR=value command` **не работает** — это синтаксис bash. Задайте переменную
окружения так:

| Оболочка | Задать на время команды | Пример |
|---|---|---|
| **cmd.exe** | `set VAR=value && python …` | `set CBENCH_MAX_TOKENS=32000 && python run_cbench.py 1234 my-model code` |
| **PowerShell** | `$env:VAR=value; python …` | `$env:CBENCH_MAX_TOKENS=32000; python run_cbench.py 1234 my-model code` |
| **bash / Linux** | `VAR=value python …` | `CBENCH_MAX_TOKENS=32000 python run_cbench.py 1234 my-model code` |

**cmd.exe** — можно задать переменную отдельной командой, она действует до
закрытия окна:

```bat
set CBENCH_MAX_TOKENS=32000
python run_cbench.py 1234 my-model code
```

**PowerShell** — аналогично на время сессии:

```powershell
$env:CBENCH_MAX_TOKENS = "32000"
python run_cbench.py 1234 my-model code
```

Несколько переменных сразу:

```bat
:: cmd.exe
set CBENCH_MAX_TOKENS=32000 && set CBENCH_TEMP=0.15 && python run_cbench.py 1234 my-model code
```

```powershell
# PowerShell
$env:CBENCH_MAX_TOKENS="32000"; $env:CBENCH_TEMP="0.15"; python run_cbench.py 1234 my-model code
```

---

## 3. Установка компилятора

### 3.1 Linux — GCC/Clang

```bash
# Ubuntu/Debian
sudo apt install gcc            # или: sudo apt install clang

# Fedora
sudo dnf install gcc            # или: sudo dnf install clang
```

Проверка: `gcc --version` или `clang --version`.

### 3.2 Windows — MSVC (Visual Studio)

1. Установите **Visual Studio 2019/2022 Community** или **Build Tools**.
2. Обязательно отметьте рабочую нагрузку **«Разработка классических приложений на C++»** (включает компилятор MSVC и `vswhere`).
3. Бенчмарк сам находит `cl.exe` через `vswhere` и подгружает окружение через `vcvars64.bat`.

Проверка: `python run_cbench.py selftest` должен показать найденный компилятор.

### 3.3 Windows — clang (MSYS2, опционально)

```text
pacman -S mingw-w64-clang-x86_64-clang
```

Если clang есть в `PATH`, он будет найден автоматически.

### 3.4 Принудительный выбор компилятора

```bash
CBENCH_CC=clang python run_cbench.py 1234 my-model code
CBENCH_CC=gcc   python run_cbench.py 1234 my-model code
# или полный путь:
CBENCH_CC="C:\msys64\clang64\bin\clang.exe" python run_cbench.py 1234 my-model code
```

Windows (cmd / PowerShell):

```bat
set CBENCH_CC=clang && python run_cbench.py 1234 my-model code
```

```powershell
$env:CBENCH_CC="C:\msys64\clang64\bin\clang.exe"; python run_cbench.py 1234 my-model code
```

---

## 4. Подключение к модели: три варианта

Все три варианта говорят по одному OpenAI-протоколу — разница только в
конфигурации. Бенчмарк выбирает пресет по `CBENCH_PROVIDER` или автоматически по
порту/URL.

| Вариант | Порт по умолч. | API key | Имя модели |
|---|---|---|---|
| **LM Studio** | `1234` | не нужен | авто (`/v1/models`) |
| **llama.cpp-server** | `8080` | не нужен | авто (`/v1/models`) |
| **внешний провайдер (OpenAI)** | задаётся URL | обязателен | обязательно |

### 4.1 LM Studio (локально)

```bash
python run_cbench.py 1234 my-model code
```

### 4.2 llama.cpp-server

```bash
python run_cbench.py 8080 my-model code
```

### 4.3 Внешний провайдер (OpenAI-протокол)

```bash
python run_cbench.py https://api.openai.com/v1 my-model code \
    --provider openai --api-key sk-...
```

---

## 5. LM Studio через reverse-proxy (Caddy)

Если LM Studio проксируется Caddy, например:

```text
caddy_windows_amd64.exe reverse-proxy --from http://192.168.56.1:1234 --to 192.168.1.70:1234
```

то:

- `192.168.56.1:1234` — **внешний** адрес прокси, на него обращается бенчмарк;
- `192.168.1.70:1234` — **внутренний** адрес LM Studio, его знает только Caddy.

Запуск бенчмарка:

```bash
CBENCH_PROVIDER=lmstudio CBENCH_BASE_URL=http://192.168.56.1:1234 \
    python run_cbench.py http://192.168.56.1:1234 my-model code
```

Windows (cmd / PowerShell):

```bat
set CBENCH_PROVIDER=lmstudio && set CBENCH_BASE_URL=http://192.168.56.1:1234 && python run_cbench.py http://192.168.56.1:1234 my-model code
```

```powershell
$env:CBENCH_PROVIDER="lmstudio"; $env:CBENCH_BASE_URL="http://192.168.56.1:1234"; python run_cbench.py http://192.168.56.1:1234 my-model code
```

Проверка доступности и честности параметров сервера:

```bash
python probe_sampler.py http://192.168.56.1:1234
```

> ⚠️ Если сервис доступен из недоверенной сети — ограничьте доступ firewall или
> добавьте TLS/аутентификацию: HTTP-трафик и модель проходят по сети в открытом виде.

---

## 6. Быстрый старт (пошагово)

```bash
# 1. Окружение
python run_cbench.py selftest

# 2. Банк задач
python run_cbench.py validate

# 3. (опционально) проверка сервера
python probe_sampler.py 1234

# 4. Прогон
python run_cbench.py 1234 my-model code
```

Под Windows те же команды без изменений (переменные окружения задаются как в
разделе **2.1 «Синтаксис команд под Windows»**).

Результат: `cbench_my-model.json` + автообновляемый `report.html` (открыть в
браузере).

---

## 7. Командная строка

```text
python run_cbench.py <endpoint> <label> [code|all] [опции]
```

| Аргумент | Описание |
|---|---|
| `endpoint` | порт (`1234`) или полный URL (`http://192.168.56.1:1234`, `https://api.openai.com/v1`) |
| `label` | метка прогона (имя файла результата) |
| `track` | `code` (только код) или `all` |
| `selftest` | вместо прогона — проверка компилятора и песочницы |
| `validate` | проверка корректности банка задач |

Опции:

| Опция | Описание |
|---|---|
| `--provider` | `openai` / `llamacpp` / `lmstudio` |
| `--base-url` | переопределить базовый URL |
| `--api-key` | ключ API (внешний провайдер) |
| `--model` | имя модели |
| `--level` | уровни через запятую: `--level easy,hard` |
| `--topic` | темы через запятую: `--topic files,pointers` |
| `--case` | id задач через запятую |
| `--runs` | число прогонов (усреднение) |
| `--timeout` | таймаут HTTP-запроса к модели, сек (по умолчанию 1800) |
| `--cc` | путь к компилятору |
| `--sanitizers` | диагностический прогон ASan/UBSan |
| `--unsafe` | отключить песочницу |

Примеры:

```bash
python run_cbench.py 1234 my-model code --level hard
python run_cbench.py 1234 my-model code --topic files
python run_cbench.py 1234 my-model code --case c-matrix-001
python run_cbench.py 1234 my-model code --runs 3
```

---

## 8. Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CBENCH_PROVIDER` | авто | `openai` / `llamacpp` / `lmstudio` |
| `CBENCH_BASE_URL` | по провайдеру | базовый URL |
| `CBENCH_MODEL` | авто (`/v1/models`) | имя модели |
| `CBENCH_API_KEY` | — | ключ API |
| `CBENCH_CC` | авто | путь к компилятору |
| `CBENCH_LEVELS` | `easy,medium,hard` | уровни через запятую |
| `CBENCH_TOPICS` | — | темы через запятую |
| `CBENCH_CASES` | — | id задач через запятую |
| `CBENCH_RUNS` | `1` | число прогонов (сиды 42, 43, …) |
| `CBENCH_SAMPLER` | `reference` | режим сэмплера |
| `CBENCH_SANITIZERS` | `0` | `1` — доп. прогон ASan/UBSan |
| `CBENCH_UNSAFE` | `0` | `1` — выключить песочницу |
| `CBENCH_COMPILE_TIMEOUT` | `60` | таймаут компиляции, сек |
| `THINK` | `0` | `1` — reasoning-режим |
| `CBENCH_MAX_TOKENS` | `16384` | лимит токенов ответа (для думающих моделей — 32000+) |
| `CBENCH_HTTP_TIMEOUT` | `1800` | таймаут HTTP-запроса к модели, сек |
| `CBENCH_TEMP`/`CBENCH_TOP_P`/`CBENCH_TOP_K`/`CBENCH_MIN_P`/`CBENCH_SEED` | эталон | переопределения для `CBENCH_SAMPLER=custom` |

### 8.1 Параметры сэмплера, таймаут и лимит токенов

**Температура по умолчанию — `0.15`** (эталонный сэмплер `reference`). Изменить её
можно двумя способами:

1. **Переменной окружения** — режим `custom` + переопределение:
   ```bash
   CBENCH_SAMPLER=custom CBENCH_TEMP=0.3 python run_cbench.py 1234 my-model code
   ```
   Windows:
   ```bat
   set CBENCH_SAMPLER=custom && set CBENCH_TEMP=0.3 && python run_cbench.py 1234 my-model code
   ```
   ```powershell
   $env:CBENCH_SAMPLER="custom"; $env:CBENCH_TEMP="0.3"; python run_cbench.py 1234 my-model code
   ```
2. **В коде** — константа `REF_SAMP` в файле `cbench/sampler.py` (значение по
   умолчанию для всех прогонов).

**Таймаут запроса к модели** — `CBENCH_HTTP_TIMEOUT` (по умолчанию `1800` сек)
или флаг `--timeout`. Увеличьте его, если сервер модели отвечает медленно
(например, думающая модель на CPU генерирует долго и запрос обрывается).

**Думающие (reasoning) модели.** Если модель думает даже в non-think-режиме
(в выводе появляется пометка `🧠думала`), рассуждения съедают токен-бюджет, и код
в ответе может обрезаться (`compile_error`). В этом случае увеличьте лимит:

```bash
CBENCH_MAX_TOKENS=32000 python run_cbench.py 1234 my-model code
```

Windows:

```bat
set CBENCH_MAX_TOKENS=32000 && python run_cbench.py 1234 my-model code
```

```powershell
$env:CBENCH_MAX_TOKENS=32000; python run_cbench.py 1234 my-model code
```

Если вы намеренно гоняете thinking-режим (`THINK=1`), ставьте `CBENCH_MAX_TOKENS`
равным 32000+, иначе `content` может прийти пустым.

---

## 9. Банк задач (cases.json)

Банк содержит **63 задачи**: 31 `easy`, 22 `medium`, 10 `hard`. Распределение по
темам: `math` (38), `arrays` (21), `strings` (2), `files` (1), `bitops` (1).

Каждой задаче соответствует:

- эталонное решение — `solutions/<id>.c`;
- заметка с исходным условием — `001-tasks/<id>.md` (URL страницы + условие).

Соответствие категорий cppstudio уровням cbench:

| Категория cppstudio | Уровень cbench |
|---|---|
| Beginner, Easy | `easy` |
| Normal | `medium` |
| Hard, Experienced | `hard` |

Формат одной задачи:

```json
{
  "id": "c-matrix-001",
  "topic": "files",
  "level": "easy",
  "kind": "program",
  "io_mode": "argv_files",
  "compile_flags": [],
  "prompt": "…текст задачи для модели…",
  "tests": [
    {
      "argv": ["matrix1.txt", "matrix2.txt"],
      "files": [
        { "name": "matrix1.txt", "content": "2 2\n1 2\n3 4\n" }
      ],
      "expected": {
        "stdout": "6 8\n10 12\n\n-4 -4\n-4 -4\n\n19 22\n43 50\n",
        "exit_code": 0
      },
      "timeout_s": 20
    }
  ]
}
```

Поля:

| Поле | Описание |
|---|---|
| `id` | уникальный идентификатор |
| `topic` | тема (произвольная строка: `files`, `pointers`, `memory`, …) |
| `level` | `easy` / `medium` / `hard` |
| `kind` | `function` / `program` |
| `io_mode` | для `program`: `stdin_stdout` / `argv` / `files` / `argv_files` |
| `compile_flags` | доп. флаги компиляции (обычно `[]`; на MSVC `-std=c11` транслируется в `/std:c11`) |
| `prompt` | текст задачи (с полным контрактом ввода-вывода) |
| `harness` | для `function`: `main()` с проверками, приклеивается к решению модели |
| `tests` | для `program`: список запусков с входными файлами, stdin, argv и эталоном |

### 9.1 Правила написания задачи

1. **Контракт ввода-вывода должен быть однозначным** — модель и эталон должны
   понимать его одинаково (формат файлов, разделители, порядок вывода).
2. **Эталон должен быть точным** — сравнение stdout с нормализацией хвостовых
   пробелов строк и пустых строк по краям (внутренние пустые строки сохраняются).
3. **Тестов должно быть несколько** — включайте крайние случаи (1×1, отрицательные
   числа, пустые входы).
4. После изменения банка меняется его `case_bank_hash` в `conditions` — прогоны
   со старым и новым банком несравнимы.

Проверка банка:

```bash
python run_cbench.py validate
```

### 9.2 Генерация банка и проверка решений

Банк генерируется из эталонных решений, а не пишется вручную:

```bash
# пересобрать cases/cases.json из solutions/*.c (эталон снимается прогоном решения):
python build_cases.py

# прогнать каждое эталонное решение через настоящий Grader (compile → run → verify):
python verify_solutions.py
```

`build_cases.py` компилирует каждое решение reference-флагами бенча, прогоняет
тестовые входы и **снимает stdout как эталон** — это гарантирует точное совпадение
для задач с плавающей точкой. Задачи, которых нет в спецификации скрипта,
сохраняются (например `c-matrix-001`).

Правила для новых задач:

1. **Вывод только ASCII.** Кириллица в выводе программы ломается на MSVC (кодовая
   страница), поэтому токены вида `больше`/`равны` заменяйте на `greater`/`equal`.
2. **Задачи с `math.h`** добавляйте в `compile_flags` значение `"-lm"` (на MSVC
   игнорируется, на gcc/clang линкует libm).
3. **Задачи со «случайными числами»** адаптируйте под чтение массива из stdin —
   иначе тесты недетерминированы.

---

## 10. Как устроена проверка (pipeline)

```text
prompt ──▶ LLM-запрос ──▶ вырезание reasoning ──▶ извлечение ```c-кода
     ──▶ компиляция (таймаут) ──▶ запуск в песочнице (каждый тест)
     ──▶ сверка stdout/exit-code/файлов ──▶ pass/fail
```

Причины провала (`why`):

| Значение | Что произошло |
|---|---|
| `compile_error` | код не скомпилировался |
| `runtime_error` | программа завершилась с ненулевым кодом/сигналом |
| `timeout` | превышен таймаут исполнения |
| `wrong_answer` | вывод/файлы не совпали с эталоном |
| `sanitizer_error` | ASan/UBSan нашёл UB (только при `CBENCH_SANITIZERS=1`) |

### 10.1 Маркеры аномалий ответа

| Флаг | Значение |
|---|---|
| `cut` | ответ обрезан по лимиту токенов |
| `loop` | хвост ответа зациклен |
| `empty` | пустой ответ |
| `thought` | модель думала (reasoning-режим) |
| `code_from_think` | код взят из размышлений |

---

## 11. Песочница и безопасность

Код модели компилируется и исполняется в песочнице:

- рабочий каталог — временная папка теста (туда кладутся входные файлы);
- чистое окружение (ключи/токены из вашего env не видны коду);
- wall-clock таймаут + убийство дерева процессов;
- ограничение размера stdout/stderr;
- **Linux**: `setsid` + `setrlimit` (CPU, память, размер файла, число процессов);
- **Windows**: process group + `taskkill /T /F` + Job Object (best-effort).

> **Честная оговорка:** это защита от **случайно-вредного кода LLM**, а не крепость
> против целенаправленного атакующего. Надёжная блокировка сети на Windows не
> гарантируется. При паранойе — гоняйте в VM/WSL/Docker; бенчу это не мешает.

Отключение песочницы (не рекомендуется): `CBENCH_UNSAFE=1`.

---

## 12. Отчёт и результаты

После прогона создаётся `cbench_<label>.json` с полными данными и блоком
`conditions` (отпечаток условий: сэмплер, think, компилятор, платформа, hash
банка). По нему любой прогон самопроверяем на сравнимость.

Для каждой задачи в JSON сохраняется **полный код решения** (`code`) и **полный
текст рассуждений** (`reasoning`), если модель думала — это и есть «лог решения»
(поле `results.code.results[]`). Прогон, прерванный `Ctrl+C`, тоже сохраняется —
с флагом `"partial": true` (сохранены результаты только обработанных задач).

Сводный HTML-отчёт — `report.html` (обновляется автоматически):

```bash
python make_report.py
```

В отчёте: процент по уровням и темам, токены и скорость генерации, маркеры
аномалий. **Кликните по строке прогона** — откроется список задач с кодом
решения, рассуждениями модели, ошибкой компиляции и причиной провала.

---

## 13. Разбор примера: MatrixOp

Пример задачи из банка — `c-matrix-001` (тема `files`, уровень `easy`, тип
`program` + `argv_files`). Условие — из файла `001-tasks/001-MatrixOp.md`
(действия над считанными из файлов матрицами), доработанное до однозначного
контракта:

- программа получает **два аргумента** — имена файлов с матрицами;
- формат файла: первая строка `R C`, далее `R` строк по `C` целых чисел;
- гарантируется, что матрицы квадратные и одного размера;
- вывод: три матрицы (сумма, разность, произведение), каждая строка — отдельной строкой, элементы через один пробел, между матрицами — ровно одна пустая строка;
- память выделяется через `malloc` и освобождается через `free`.

Эталон для теста 1:

```text
A = [[1,2],[3,4]], B = [[5,6],[7,8]]

A+B = 6 8        A-B = -4 -4       A*B = 19 22
      10 12            -4 -4             43 50
```

Полный текст промпта и эталонов — в `cases/cases.json`.

---

## 14. Устранение неполадок

| Симптом | Причина / решение |
|---|---|
| `❌ компилятор Си не найден` | установите gcc/clang/MSVC, либо `CBENCH_CC=<путь>` |
| `нет соединения с …` | сервер не запущен или неверный URL/порт |
| `HTTP 4xx` | неверный API key (внешний провайдер) или имя модели |
| `сервер вернул не-JSON` | URL указывает не на OpenAI-эндпоинт (проверьте `/v1/chat/completions`) |
| `compile_error` у всех задач | проверьте компилятор: `python run_cbench.py selftest` |
| вывод «всё `wrong_answer`» | проверьте, что контракт в `prompt` совпадает с эталоном в `tests` |
| эмодзи/кириллица в консоли битые | `PYTHONIOENCODING=utf-8` (обёртки `run_reference.*` ставят сами) |
| LM Studio игнорирует `think` | reasoning отключается тумблером на стороне сервера |

---

## 15. ЧаВо (FAQ)

**Зачем компиляция, а не просто текст?**
Только реальное исполнение даёт честный `pass/fail` без LLM-судьи. Компиляция
дополнительно ловит синтаксические ошибки и (с `CBENCH_SANITIZERS=1`) UB.

**Почему результаты на gcc и MSVC могут отличаться?**
Код с undefined behavior ведёт себя по-разному на разных компиляторах. Для
сравнимых цифр используйте один компилятор и указывайте его при публикации.

**Как добавить свою задачу?**
Добавьте решение в `solutions/<id>.c` и запись в `SPECS` в `build_cases.py`, затем
`python build_cases.py && python verify_solutions.py`. Либо добавьте объект прямо в
`cases/cases.json` и проверьте: `python run_cbench.py validate`.

**Можно ли гонять одну задачу?**
Да: `python run_cbench.py 1234 my-model code --case c-matrix-001`.

**Сравнимы ли прогоны на разных сэмплерах?**
Нет. Фиксируйте `CBENCH_SAMPLER=reference` (по умолчанию) для сравнимых цифр.
