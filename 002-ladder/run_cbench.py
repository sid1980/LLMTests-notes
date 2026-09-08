#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cbench — бенчмарк знания языка Си для локальных LLM.

Запуск:
  python run_cbench.py <endpoint-or-port> <label> [code|all]
  python run_cbench.py http://192.168.56.1:1234 my-model code   # LM Studio через Caddy
  python run_cbench.py 1234 my-model all                        # LM Studio локально
  python run_cbench.py 8080 my-model all                        # llama.cpp
  python run_cbench.py https://api.openai.com/v1 my-model all --provider openai --api-key sk-...
  python run_cbench.py selftest                                 # проверка окружения

Env: CBENCH_PROVIDER, CBENCH_BASE_URL, CBENCH_MODEL, CBENCH_API_KEY, CBENCH_CC,
     CBENCH_LEVELS, CBENCH_TOPICS, CBENCH_CASES, CBENCH_RUNS, CBENCH_SAMPLER,
     CBENCH_SANITIZERS, CBENCH_UNSAFE, THINK, CBENCH_MAX_TOKENS.

Только стандартная библиотека Python 3.8+.
"""
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# UTF-8 в консоль на любой ОС (Windows cp1251 бьёт кириллицу/эмодзи).
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")
except Exception:
    pass


def main(argv=None) -> int:
    from cbench.config import build_config
    from cbench.runner import Runner, selftest

    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "selftest":
        return selftest()
    if argv and argv[0] in ("validate",):
        return _validate()

    cfg = build_config(argv)
    runner = Runner(cfg)
    return runner.run()


def _validate() -> int:
    from cbench.data import load_cases
    from cbench.runner import CASES_PATH
    try:
        bank = load_cases(CASES_PATH)
        print(f"✅ банк задач валиден: {len(bank.cases)} задач, hash={bank.source_hash}")
        return 0
    except Exception as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
