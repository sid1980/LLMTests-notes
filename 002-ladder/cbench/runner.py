"""Композиционный корень: связывает адаптеры в pipeline прогона.

Единственный модуль, знающий все слои. Собирает: config → provider/client →
compiler → sandbox → grader → loader → запуск по каждой задаче → RunSummary →
Conditions → JSON (+ отчёт).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from .config import RunConfig, build_config, resolve_endpoint, platform_tag
from .model import (TaskResult, RunSummary, UsageStat, LevelStat, Conditions,
                    ProviderConfig)
from .data import load_cases, LoadError
from .llm import OpenAICompatClient, resolve_provider, LLMError
from .codegen import extract_c, has_code_fence
from .exec import detect, make_sandbox, Grader
from . import sampler

HERE = Path(__file__).resolve().parent.parent
CASES_PATH = HERE / "cases" / "cases.json"
OUT_NAME = "cbench_{label}.json"


class Runner:
    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        self.compiler = None
        self.sandbox = make_sandbox()
        self.grader = None
        self.client = None
        self.samp = {}
        self.samp_mode = "reference"
        self.usage = UsageStat()
        self.conditions = Conditions()

    # --- настройка ----------------------------------------------------------
    def setup(self):
        self.compiler = detect(self.cfg.cc)
        if self.compiler is None:
            raise SystemExit(
                "❌ компилятор Си не найден. Установите gcc/clang (Linux) или MSVC (Windows),\n"
                "   либо укажите путь: CBENCH_CC=<путь> (или --cc).")
        self.grader = Grader(self.compiler, self.sandbox, sanitizers=self.cfg.sanitizers)

        base_url = resolve_endpoint(self.cfg.endpoint) if self.cfg.base_url is None \
            else self.cfg.base_url
        pcfg = resolve_provider(self.cfg.provider, base_url, self.cfg.api_key, self.cfg.model)
        self.client = OpenAICompatClient(pcfg, http_timeout=self.cfg.http_timeout)

        self.samp_mode = sampler.sampler_mode()
        self.samp = sampler.resolve_sampler()
        if self.samp_mode == "recommended":
            pr = sampler.find_preset(self.client.model_name(), self.cfg.think)
            if pr:
                self.samp = dict(pr["params"])
                self.samp["seed"] = 42
                print(f"[preset] {pr['name']} → {pr['params']} (источник: {pr['source']})",
                      flush=True)
            else:
                print(f"[preset] модель '{self.client.model_name()}' не найдена в "
                      f"sampler_presets.json — параметры не шлю (как native)", flush=True)
        self.samp["seed"] = self.samp.get("seed", 42)

    # --- один запрос --------------------------------------------------------
    def _ask(self, prompt: str):
        reply = self.client.generate(prompt, self.cfg.max_tokens, self.samp,
                                     self.cfg.think)
        # слабая модель могла положить код внутрь <think>: не теряем зачёт.
        if reply.reasoning and not has_code_fence(reply.content) and \
                has_code_fence(reply.reasoning):
            reply.content = (reply.content + "\n\n" + reply.reasoning).strip()
            reply.flags.append("code_from_think")
        self.usage.prompt_tokens += 0  # токены учитываются в client.usage
        for f in reply.flags:
            if f == "cut":
                self.usage.answers_cut_by_limit += 1
            elif f == "loop":
                self.usage.loop_suspects += 1
            elif f == "empty":
                self.usage.empty_answers += 1
            elif f == "thought":
                self.usage.thinking_answers += 1
            elif f == "code_from_think":
                self.usage.code_from_think += 1
        return reply

    # --- один прогон трека code --------------------------------------------
    def run_code(self, cases) -> RunSummary:
        summary = RunSummary()
        by_level = defaultdict(lambda: [0, 0])
        by_topic = defaultdict(lambda: [0, 0])
        n_blocked = 0
        for c in cases:
            row = TaskResult(id=c.id, level=c.level, topic=c.topic, kind=c.kind,
                             pass_=False)
            try:
                reply = self._ask(c.prompt)
                code = extract_c(reply.content)
                row = self.grader.grade(c, code, list(reply.flags))
                row.tok = self.client.last.get("tok")
                row.tail = reply.tail or row.tail
                row.think_tail = reply.think_tail
                row.think_chars = reply.think_chars
                row.code = code
                row.reasoning = reply.reasoning
            except KeyboardInterrupt:
                summary.partial = True
                print("\n[interrupt] прервано — сохраняю частичные результаты", flush=True)
                break
            except LLMError as e:
                row.why = f"llm_error: {e}"
            except Exception as e:
                row.why = f"internal: {repr(e)[:80]}"
            by_level[c.level][0] += row.pass_
            by_level[c.level][1] += 1
            by_topic[c.topic][0] += row.pass_
            by_topic[c.topic][1] += 1
            if row.sandbox:
                n_blocked += 1
            summary.results.append(row)
            self._print_row(row)
            for ln in row.sandbox:
                print(f"     🛡️ {ln}", flush=True)
        summary.by_level = {k: LevelStat(pass_=v[0], total=v[1])
                            for k, v in by_level.items()}
        summary.by_topic = {k: LevelStat(pass_=v[0], total=v[1])
                            for k, v in by_topic.items()}
        summary.sandbox_blocked_tasks = n_blocked
        return summary

    def _print_row(self, row: TaskResult):
        marks = "".join({
            "cut": " ✂обрыв", "loop": " 🔁цикл?", "empty": " ∅пусто",
            "thought": " 🧠думала", "code_from_think": " 🔧из-мышления",
            "sanitizer_error": " ⚠sanitizer"}[f] for f in row.flags)
        print(f"  {'✅' if row.pass_ else '❌'} [{row.level:8}] {row.id} "
              f"({row.topic})" + ("" if row.pass_ else f"  ({row.why})") + marks,
              flush=True)

    # --- агрегация мульти-прогона ------------------------------------------
    def aggregate(self, runs) -> RunSummary:
        out = RunSummary()
        lv = defaultdict(list)
        tp = defaultdict(list)
        for r in runs:
            for k, v in r.by_level.items():
                lv[k].append(v.pass_)
            for k, v in r.by_topic.items():
                tp[k].append(v.pass_)
        out.by_level = {k: LevelStat(pass_=round(sum(v) / len(v), 1),
                                     total=runs[0].by_level[k].total, per_run=v)
                        for k, v in lv.items()}
        out.by_topic = {k: LevelStat(pass_=round(sum(v) / len(v), 1),
                                     total=runs[0].by_topic[k].total, per_run=v)
                        for k, v in tp.items()}
        tasks = {}
        for r in runs:
            for row in r.results:
                t = tasks.setdefault(row.id, dict(id=row.id, level=row.level,
                                                  topic=row.topic, kind=row.kind,
                                                  n=0, passed=0, why="", flags=[]))
                t["n"] += 1
                t["passed"] += bool(row.pass_)
                if not row.pass_ and not t["why"]:
                    t["why"] = row.why
                for f in row.flags:
                    if f not in t["flags"]:
                        t["flags"].append(f)
                if row.tail:
                    t["tail"] = row.tail
                if row.code:
                    t["code"] = row.code
                if row.reasoning:
                    t["reasoning"] = row.reasoning
                if row.diagnostic:
                    t["diagnostic"] = row.diagnostic
        results = []
        for t in tasks.values():
            results.append(TaskResult(id=t["id"], level=t["level"], topic=t["topic"],
                                      kind=t["kind"], pass_=t["passed"] == t["n"],
                                      why=t["why"], flags=t["flags"],
                                      tail=t.get("tail", ""),
                                      code=t.get("code", ""),
                                      reasoning=t.get("reasoning", ""),
                                      diagnostic=t.get("diagnostic", "")))
        out.results = results
        out.sandbox_blocked_tasks = max(r.sandbox_blocked_tasks for r in runs)
        return out

    def fingerprint(self, summary: RunSummary, n_cases: int, bank_hash: str):
        self.conditions.sampler = dict(self.samp)
        self.conditions.sampler_mode = self.samp_mode
        self.conditions.think = self.cfg.think
        self.conditions.max_tokens = self.cfg.max_tokens
        self.conditions.http_timeout = self.cfg.http_timeout
        self.conditions.n_runs = self.cfg.n_runs
        self.conditions.base_seed = self.samp.get("seed", 42)
        self.conditions.levels = self.cfg.levels
        self.conditions.topics = self.cfg.topics
        self.conditions.exec_timeout_s = 20.0
        self.conditions.sandbox = not self.cfg.unsafe
        self.conditions.sandbox_mode = self.sandbox.mode
        self.conditions.compiler = self.compiler.name
        self.conditions.compiler_version = self.compiler.version()
        self.conditions.compiler_flags = []
        self.conditions.platform = platform_tag()
        self.conditions.python_version = sys.version.split()[0]
        self.conditions.provider = self.client.cfg.redacted()
        self.conditions.case_bank_hash = bank_hash
        self.conditions.n_cases = n_cases
        self.conditions.sanitizers = self.cfg.sanitizers
        self.conditions.nothink_thought = (not self.cfg.think) and self.usage.thinking_answers > 0

    def run(self) -> int:
        t0 = time.time()
        self.setup()
        try:
            bank = load_cases(CASES_PATH, levels=self.cfg.levels,
                              topics=self.cfg.topics or None,
                              ids=self.cfg.case_ids or None)
        except LoadError as e:
            raise SystemExit(f"❌ {e}")

        print(f"[cbench] {self.cfg.label} | track={self.cfg.track} | "
              f"think={'on' if self.cfg.think else 'off'} | runs={self.cfg.n_runs}",
              flush=True)
        print(f"[server] {self.client.endpoint()} | model={self.client.model_name()}", flush=True)
        print(f"[compiler] {self.compiler.name} {self.compiler.version()}", flush=True)
        print(f"[conditions] sampler_mode={self.samp_mode} sampler={self.samp} "
              f"max_tokens={self.cfg.max_tokens} http_timeout={self.cfg.http_timeout}s "
              f"sandbox={'off' if self.cfg.unsafe else self.sandbox.mode}",
              flush=True)
        if self.cfg.unsafe:
            print("⚠️  CBENCH_UNSAFE=1: песочница ВЫКЛЮЧЕНА — код исполняется без защиты!", flush=True)

        if self.cfg.n_runs <= 1:
            summary = self.run_code(bank.cases)
        else:
            runs = []
            base = self.samp.get("seed", 42)
            for ri in range(self.cfg.n_runs):
                self.samp["seed"] = base + ri
                print(f"\n{'#'*55}\n### ПРОГОН {ri+1}/{self.cfg.n_runs} — seed {self.samp['seed']}\n{'#'*55}",
                      flush=True)
                r = self.run_code(bank.cases)
                runs.append(r)
                if r.partial:
                    break
            self.samp["seed"] = base
            summary = self.aggregate(runs)
            summary.partial = any(r.partial for r in runs)

        # usage из клиента
        cu = self.client.usage
        self.usage.prompt_tokens = cu.get("prompt", 0)
        self.usage.completion_tokens = cu.get("completion", 0)
        self.usage.requests = cu.get("req", 0)
        self.usage.request_seconds = round(cu.get("secs", 0.0), 1)
        self.usage.gen_tok_s = (round(self.usage.completion_tokens / cu["secs"], 1)
                                if cu.get("secs") else None)
        summary.usage = self.usage

        self.fingerprint(summary, len(bank.cases), bank.source_hash)

        wall_min = (time.time() - t0) / 60
        out = self._to_dict(summary, wall_min)
        fp = HERE / OUT_NAME.format(label=self.cfg.label)
        fp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        self._print_summary(summary, wall_min)
        print(f"-> {fp.name}", flush=True)
        try:
            from . import report
            print(f"[report] обновлён -> {report.build(HERE).name}", flush=True)
        except Exception as e:
            print(f"[report] пропущен: {e}", flush=True)
        return 0

    def _to_dict(self, summary: RunSummary, wall_min: float) -> dict:
        usage = self.usage
        results = []
        for r in summary.results:
            d = {"id": r.id, "level": r.level, "topic": r.topic, "pass": r.pass_}
            if r.why:
                d["why"] = r.why
            if r.flags:
                d["flags"] = r.flags
            if r.tok is not None:
                d["tok"] = r.tok
            if r.tail:
                d["tail"] = r.tail
            if r.code:
                d["code"] = r.code
            if r.reasoning:
                d["reasoning"] = r.reasoning
            if r.think_tail:
                d["think_chars"] = r.think_chars
                d["think_tail"] = r.think_tail
            if r.diagnostic:
                d["diagnostic"] = r.diagnostic
            if r.compile and not r.compile.ok:
                d["compile_error"] = (r.compile.stderr or r.compile.stdout)[-300:]
            if r.sandbox:
                d["sandbox"] = r.sandbox
            results.append(d)
        return {
            "label": self.cfg.label,
            "provider": self.client.cfg.redacted(),
            "model": self.client.model_name(),
            "think": self.cfg.think,
            "partial": summary.partial,
            "conditions": self._conditions_dict(),
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "requests": usage.requests,
                "request_seconds": usage.request_seconds,
                "gen_tok_s": usage.gen_tok_s,
                "answers_cut_by_limit": usage.answers_cut_by_limit,
                "loop_suspects": usage.loop_suspects,
                "empty_answers": usage.empty_answers,
                "thinking_answers": usage.thinking_answers,
                "code_from_think": usage.code_from_think,
            },
            "wall_minutes": round(wall_min, 1),
            "results": {
                "code": {
                    "by_level": {k: {"pass": v.pass_, "total": v.total,
                                     **({"per_run": v.per_run} if v.per_run else {})}
                                 for k, v in summary.by_level.items()},
                    "by_topic": {k: {"pass": v.pass_, "total": v.total}
                                 for k, v in summary.by_topic.items()},
                    "sandbox_blocked_tasks": summary.sandbox_blocked_tasks,
                    "results": results,
                }
            },
        }

    def _conditions_dict(self) -> dict:
        c = self.conditions
        return {
            "sampler": c.sampler, "sampler_mode": c.sampler_mode, "think": c.think,
            "max_tokens": c.max_tokens, "http_timeout": c.http_timeout,
            "n_runs": c.n_runs, "base_seed": c.base_seed,
            "levels": c.levels, "topics": c.topics, "exec_timeout_s": c.exec_timeout_s,
            "sandbox": c.sandbox, "sandbox_mode": c.sandbox_mode,
            "compiler": c.compiler, "compiler_version": c.compiler_version,
            "platform": c.platform, "python_version": c.python_version,
            "provider": c.provider, "case_bank_hash": c.case_bank_hash,
            "n_cases": c.n_cases, "sanitizers": c.sanitizers,
            "nothink_thought": c.nothink_thought,
        }

    def _print_summary(self, summary: RunSummary, wall_min: float):
        print(f"\n{'='*55}\n[cbench] {self.cfg.label} — ИТОГ:")
        if summary.partial:
            done = len(summary.results)
            print(f"  ⚠️ ПРОГОН ПРЕРВАН: сохранены результаты только {done} задач "
                  f"(не полный прогон).")
        for lv, d in sorted(summary.by_level.items()):
            pct = round(100 * d.pass_ / d.total) if d.total else 0
            bar = "█" * round(pct / 10) + "░" * (10 - round(pct / 10))
            spread = (f"  (по прогонам: {'/'.join(map(str, d.per_run))})"
                      if d.per_run else "")
            print(f"  level {lv:8}: {d.pass_:>3}/{d.total:<3} {bar} {pct}%{spread}")
        for tp, d in sorted(summary.by_topic.items()):
            pct = round(100 * d.pass_ / d.total) if d.total else 0
            print(f"  topic {tp:10}: {d.pass_:>3}/{d.total:<3} {pct}%")
        print(f"  ⏱️ время теста: {wall_min:.1f} мин")
        if self.usage.completion_tokens:
            print(f"  ⚡ генерация: {self.usage.gen_tok_s} tok/s · токены: "
                  f"prompt {self.usage.completion_tokens and self.usage.prompt_tokens:,} + "
                  f"ответы {self.usage.completion_tokens:,}")
        sus = (self.usage.answers_cut_by_limit + self.usage.loop_suspects
               + self.usage.empty_answers)
        if sus:
            print(f"  🚨 подозрительные ответы: обрыв {self.usage.answers_cut_by_limit} · "
                  f"цикл? {self.usage.loop_suspects} · пустых {self.usage.empty_answers}")
        print("=" * 55)


def selftest() -> int:
    """Проверка окружения: компилятор + компиляция + запуск + timeout."""
    print("[selftest] проверка компилятора и песочницы\n")
    comp = detect()
    if comp is None:
        print("❌ компилятор Си не найден (нужен gcc/clang/MSVC).")
        return 2
    print(f"  ✅ компилятор: {comp.name} {comp.version()}")
    sand = make_sandbox()
    fails = 0
    with tempfile.TemporaryDirectory(prefix="cbench_selftest_") as td:
        d = Path(td)
        src = d / "t.c"
        src.write_text(
            '#include <stdio.h>\n'
            'int main(void){ int a=2,b=3; printf("%d\\n", a+b); return 0; }\n',
            encoding="utf-8")
        ext = ".exe" if sys.platform.startswith("win") else ""
        out = d / f"t{ext}"
        from .exec.compiler import REFERENCE_FLAGS_UNIX, REFERENCE_FLAGS_MSVC, MsvcCompiler
        flags = REFERENCE_FLAGS_MSVC if isinstance(comp, MsvcCompiler) else REFERENCE_FLAGS_UNIX
        cr = comp.compile(src, out, flags, d)
        if not cr.ok:
            print(f"  ❌ компиляция не удалась: {(cr.stderr or cr.stdout)[:200]}")
            fails += 1
        else:
            r = sand.run(str(out), [], "", str(d), 10.0)
            good = r.exit_code == 0 and r.stdout.strip() == "5"
            print(f"  {'✅' if good else '❌'} запуск: exit={r.exit_code} stdout={r.stdout.strip()!r}")
            fails += not good
        # timeout-проверка
        hang = d / "hang.c"
        hang.write_text('int main(void){ for(;;){} return 0; }\n', encoding="utf-8")
        hangout = d / f"hang{ext}"
        cr2 = comp.compile(hang, hangout, flags, d)
        if cr2.ok:
            r2 = sand.run(str(hangout), [], "", str(d), 2.0)
            print(f"  {'✅' if r2.timeout else '❌'} timeout сработал: timeout={r2.timeout}")
            fails += not r2.timeout
    print(f"\n[selftest] {'✅ ВСЁ ОК' if not fails else f'❌ ПРОВАЛОВ: {fails}'}")
    return 1 if fails else 0
