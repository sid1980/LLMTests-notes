"""Доменный слой: чистые структуры данных задач бенчмарка.

Никакого I/O (HTTP/файлы/процессы) здесь нет — только описания. Это позволяет
адаптерам (llm/, exec/, data/, codegen/) зависеть от модели, но не друг от друга.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class CaseKind:
    """Способ ответа модели: отдельная функция или полная программа."""
    FUNCTION = "function"
    PROGRAM = "program"
    ALL = (FUNCTION, PROGRAM)


class IOMode:
    """Режим ввода-вывода для полной программы (kind=program)."""
    STDIN_STDOUT = "stdin_stdout"
    ARGV = "argv"
    FILES = "files"
    ARGV_FILES = "argv_files"
    ALL = (STDIN_STDOUT, ARGV, FILES, ARGV_FILES)


class Level:
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ALL = (EASY, MEDIUM, HARD)


@dataclass
class FileSpec:
    """Входной или выходной файл: имя относительно cwd теста + содержимое."""
    name: str
    content: str


@dataclass
class ExpectedResult:
    """Эталон для сверки одного запуска."""
    stdout: str = ""
    files: List[FileSpec] = field(default_factory=list)
    exit_code: int = 0


@dataclass
class TestSpec:
    """Как прогнать и проверить один запуск скомпилированной программы."""
    argv: List[str] = field(default_factory=list)
    stdin: str = ""
    files: List[FileSpec] = field(default_factory=list)   # входные файлы в cwd
    expected: ExpectedResult = field(default_factory=ExpectedResult)
    timeout_s: float = 20.0


@dataclass
class Case:
    """Одна задача бенчмарка."""
    id: str
    topic: str
    level: str
    kind: str                      # CaseKind
    prompt: str
    io_mode: Optional[str] = None  # IOMode (только для kind=program)
    compile_flags: List[str] = field(default_factory=list)
    harness: str = ""              # только для kind=function
    tests: List[TestSpec] = field(default_factory=list)  # только для kind=program

    def __post_init__(self):
        if self.kind not in CaseKind.ALL:
            raise ValueError(f"case {self.id}: неверный kind={self.kind!r}")
        if self.level not in Level.ALL:
            raise ValueError(f"case {self.id}: неверный level={self.level!r}")
        if self.kind == CaseKind.PROGRAM:
            if self.io_mode not in IOMode.ALL:
                raise ValueError(f"case {self.id}: неверный io_mode={self.io_mode!r}")
            if not self.tests:
                raise ValueError(f"case {self.id}: program-задача без tests")
        else:
            if not self.harness:
                raise ValueError(f"case {self.id}: function-задача без harness")


@dataclass
class CaseBank:
    """Загруженный банк задач + его контрольная сумма (для conditions)."""
    cases: List[Case]
    source_hash: str = ""
    source_file: str = ""
