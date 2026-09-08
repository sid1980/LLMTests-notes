"""Grader: компиляция → запуск → сверка по типу задачи.

Зависит только от model (TaskResult/CompileResult/RunOutcome) и адаптеров
Compiler/Sandbox (через композицию). Не знает про LLM.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Optional

from ..model import (Case, CaseKind, TaskResult, CompileResult, RunOutcome,
                     ExpectedResult)
from .compiler import (Compiler, REFERENCE_FLAGS_UNIX, DIAGNOSTIC_FLAGS_UNIX,
                       REFERENCE_FLAGS_MSVC, DIAGNOSTIC_FLAGS_MSVC, MsvcCompiler)
from .sandbox import Sandbox


def _norm(s: str) -> str:
    """Нормализация вывода: CRLF→LF, срез хвостовых пробелов строки,
    срез ведущих/хвостовых пустых строк (внутренние пустые строки сохраняются)."""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in s.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


class Grader:
    def __init__(self, compiler: Compiler, sandbox: Sandbox, sanitizers: bool = False):
        self.compiler = compiler
        self.sandbox = sandbox
        self.sanitizers = sanitizers

    def _reference_flags(self, extra: List[str]) -> List[str]:
        if isinstance(self.compiler, MsvcCompiler):
            return REFERENCE_FLAGS_MSVC + extra
        return REFERENCE_FLAGS_UNIX + extra

    def _diagnostic_flags(self, extra: List[str]) -> List[str]:
        if isinstance(self.compiler, MsvcCompiler):
            return DIAGNOSTIC_FLAGS_MSVC + extra
        return DIAGNOSTIC_FLAGS_UNIX + extra

    def _bin_ext(self) -> str:
        return ".exe" if os.name == "nt" else ""

    def grade(self, case: Case, model_code: str, reply_flags: List[str]) -> TaskResult:
        res = TaskResult(id=case.id, level=case.level, topic=case.topic,
                         kind=case.kind, pass_=False, flags=list(reply_flags))
        with tempfile.TemporaryDirectory(prefix="cbench_") as td:
            d = Path(td)
            src = d / "sol.c"
            if case.kind == CaseKind.FUNCTION:
                src.write_text(model_code + "\n\n" + case.harness, encoding="utf-8")
            else:
                src.write_text(model_code, encoding="utf-8")
            out = d / f"sol{self._bin_ext()}"

            cr = self.compiler.compile(src, out, self._reference_flags(case.compile_flags), d)
            res.compile = cr
            if not cr.ok:
                res.why = "compile_error"
                res.tail = (cr.stderr or cr.stdout or "")[-500:]
                return res

            if case.kind == CaseKind.FUNCTION:
                ok, why, runs, sb = self._run_function(out, case)
                res.why = why
                res.pass_ = ok
                res.runs = runs
                res.sandbox = sb
            else:
                ok, why, runs, sb = self._run_program(out, case)
                res.why = why
                res.pass_ = ok
                res.runs = runs
                res.sandbox = sb

            if self.sanitizers and isinstance(self.compiler, Compiler) and \
                    not isinstance(self.compiler, MsvcCompiler):
                self._run_diagnostic(src, d, case, res)
        return res

    def _run_function(self, binary: Path, case: Case):
        r = self.sandbox.run(str(binary), [], "", str(binary.parent), 20.0)
        sb = r.sandbox_events
        if r.timeout:
            return False, "timeout", [r], sb
        if r.exit_code == 0:
            return True, "", [r], sb
        return False, "runtime_error", [r], sb

    def _run_program(self, binary: Path, case: Case):
        runs: List[RunOutcome] = []
        sb: List[str] = []
        for t in case.tests:
            d = binary.parent
            for f in t.files:
                (d / f.name).write_text(f.content, encoding="utf-8")
            r = self.sandbox.run(str(binary), t.argv, t.stdin, str(d), t.timeout_s)
            runs.append(r)
            sb += r.sandbox_events
            if r.timeout:
                return False, "timeout", runs, sb
            if r.exit_code != t.expected.exit_code:
                return False, "runtime_error", runs, sb
            if _norm(r.stdout) != _norm(t.expected.stdout):
                return False, "wrong_answer", runs, sb
            if not self._check_files(d, t.expected):
                return False, "wrong_answer", runs, sb
        return True, "", runs, sb

    def _check_files(self, d: Path, expected: ExpectedResult) -> bool:
        for f in expected.files:
            p = d / f.name
            if not p.exists():
                return False
            try:
                if _norm(p.read_text(encoding="utf-8")) != _norm(f.content):
                    return False
            except OSError:
                return False
        return True

    def _run_diagnostic(self, src: Path, d: Path, case: Case, res: TaskResult):
        """Sanitizer-прогон (GCC/Clang): ловит UB/выход за границы — не влияет на score."""
        try:
            out = d / "sol_diag"
            cr = self.compiler.compile(src, out, self._diagnostic_flags(case.compile_flags), d)
            if not cr.ok:
                return
            r = self.sandbox.run(str(out), [], "", str(d), 30.0)
            stderr = (r.stderr or "")
            # Флагим только по тексту sanitizer-отчёта (а не по exit-коду):
            # на Windows ASan-рантайм может не загрузиться (DLL missing) — это
            # не ошибка кода модели.
            mark = ("runtime error" in stderr or "AddressSanitizer" in stderr
                    or "UndefinedBehaviorSanitizer" in stderr
                    or "LeakSanitizer" in stderr or "heap-use-after-free" in stderr
                    or "stack-buffer-overflow" in stderr or "use-after-free" in stderr
                    or "signed integer overflow" in stderr
                    or "division by zero" in stderr)
            if mark:
                res.flags.append("sanitizer_error")
                res.diagnostic = stderr[-500:]
        except Exception:
            pass
