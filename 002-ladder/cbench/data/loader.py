"""Загрузчик банка задач cases/cases.json → list[Case].

Только чтение JSON и валидация — без I/O наружу (кроме чтения файла банка).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional

from ..model import Case, CaseBank, FileSpec, ExpectedResult, TestSpec, CaseKind


class LoadError(Exception):
    """Ошибка формата/содержимого банка задач."""


def load_cases(path: Path, levels: Optional[List[str]] = None,
               topics: Optional[List[str]] = None,
               ids: Optional[List[str]] = None) -> CaseBank:
    """Загрузить и провалидировать банк задач.

    Аргументы фильтрации: levels/topics/ids — подмножества для прогона.
    Пустые значения = без фильтра.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LoadError(f"банк задач не найден: {path}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LoadError(f"некорректный JSON в {path}: {e}")
    if not isinstance(data, list):
        raise LoadError(f"{path}: ожидается список задач")

    seen = set()
    cases: List[Case] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise LoadError(f"{path}: задача #{i} — не объект")
        c = _parse_case(item, i, path)
        if c.id in seen:
            raise LoadError(f"{path}: дублирующийся id={c.id!r}")
        seen.add(c.id)
        cases.append(c)

    if levels:
        cases = [c for c in cases if c.level in levels]
    if topics:
        cases = [c for c in cases if c.topic in topics]
    if ids:
        cases = [c for c in cases if c.id in ids]

    if not cases:
        raise LoadError(f"{path}: после фильтрации не осталось задач "
                        f"(levels={levels}, topics={topics}, ids={ids})")
    bank_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return CaseBank(cases=cases, source_hash=bank_hash, source_file=str(path))


def _parse_case(item: dict, idx: int, path: Path) -> Case:
    def need(key: str):
        if key not in item or item[key] in (None, ""):
            raise LoadError(f"{path}: задача #{idx}: нет поля '{key}'")
        return item[key]

    cid = str(need("id"))
    topic = str(need("topic"))
    level = str(need("level"))
    kind = str(need("kind"))
    prompt = str(need("prompt"))
    io_mode = item.get("io_mode")
    compile_flags = [str(f) for f in (item.get("compile_flags") or [])]
    harness = str(item.get("harness") or "")

    tests = []
    if kind == CaseKind.PROGRAM:
        raw_tests = item.get("tests")
        if not isinstance(raw_tests, list) or not raw_tests:
            raise LoadError(f"{path}: {cid}: program-задача без tests")
        for t in raw_tests:
            tests.append(_parse_test(t, cid, path))

    return Case(id=cid, topic=topic, level=level, kind=kind, prompt=prompt,
                io_mode=io_mode, compile_flags=compile_flags, harness=harness,
                tests=tests)


def _parse_test(t: dict, cid: str, path: Path) -> TestSpec:
    if not isinstance(t, dict):
        raise LoadError(f"{path}: {cid}: test — не объект")
    exp = t.get("expected") or {}
    files = [_parse_file(f, cid, path) for f in (t.get("files") or [])]
    exp_files = [_parse_file(f, cid, path) for f in (exp.get("files") or [])]
    return TestSpec(
        argv=[str(a) for a in (t.get("argv") or [])],
        stdin=str(t.get("stdin") or ""),
        files=files,
        expected=ExpectedResult(
            stdout=str(exp.get("stdout") or ""),
            files=exp_files,
            exit_code=int(exp.get("exit_code", 0)),
        ),
        timeout_s=float(t.get("timeout_s", 20.0)),
    )


def _parse_file(f: dict, cid: str, path: Path) -> FileSpec:
    if not isinstance(f, dict) or "name" not in f:
        raise LoadError(f"{path}: {cid}: файл без имени")
    return FileSpec(name=str(f["name"]), content=str(f.get("content") or ""))
