#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка, что каждое эталонное решение из solutions/*.c проходит свои тесты.

Грейдит решения тем же Grader'ом, что и бенч (compile -> run -> verify).
Запуск:  python verify_solutions.py
"""
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")
except Exception:
    pass

from cbench.data import load_cases  # noqa: E402
from cbench.exec.compiler import detect  # noqa: E402
from cbench.exec.grader import Grader  # noqa: E402
from cbench.exec.sandbox import make_sandbox  # noqa: E402


def main() -> int:
    bank = load_cases(HERE / "cases" / "cases.json")
    compiler = detect()
    if compiler is None:
        print("compiler not found")
        return 2
    sandbox = make_sandbox()
    grader = Grader(compiler, sandbox, sanitizers=False)

    failed = []
    skipped = 0
    for case in bank.cases:
        src = HERE / "solutions" / f"{case.id}.c"
        if not src.exists():
            print(f"SKIP  {case.id:16s} (нет решения в solutions/)")
            skipped += 1
            continue
        code = src.read_text(encoding="utf-8")
        res = grader.grade(case, code, [])
        status = "PASS" if res.pass_ else "FAIL"
        print(f"{status}  {case.id:16s} {case.level:7s} {case.topic:8s}"
              f"  tests={len(case.tests)}" + (f"  why={res.why}" if not res.pass_ else ""))
        if not res.pass_:
            failed.append(case.id)

    print(f"\n{len(bank.cases) - len(failed) - skipped}/{len(bank.cases)} passed"
          f" (skipped {skipped})")
    if failed:
        print("failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
