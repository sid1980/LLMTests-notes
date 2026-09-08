"""Доменный слой: структуры данных результатов и конфигурации прогона.

Никакого I/O — только данные, которыми обмениваются слои.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelReply:
    """Что вернула модель после вырезания reasoning."""
    content: str = ""
    reasoning: str = ""
    flags: List[str] = field(default_factory=list)  # cut/loop/empty/thought/code_from_think
    tail: str = ""            # хвост ответа при обрыве/цикле (для диагностики)
    think_tail: str = ""      # хвост размышлений
    think_chars: int = 0


@dataclass
class CompileResult:
    ok: bool
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    tool: str = ""            # имя компилятора
    version: str = ""
    flags: List[str] = field(default_factory=list)
    profile: str = "reference"  # reference | diagnostic


@dataclass
class RunOutcome:
    """Итог одного запуска скомпилированного бинарника."""
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timeout: bool = False
    sandbox_events: List[str] = field(default_factory=list)  # [SANDBOX] строки
    sandbox_degraded: bool = False
    signal: Optional[int] = None  # SIGSEGV/abort на Linux


@dataclass
class TaskResult:
    """Итог по одной задаче."""
    id: str
    level: str
    topic: str
    kind: str
    pass_: bool
    why: str = ""              # compile_error|runtime_error|timeout|wrong_answer|sanitizer_error|ok
    flags: List[str] = field(default_factory=list)
    tok: Optional[int] = None
    tail: str = ""
    think_tail: str = ""
    think_chars: int = 0
    compile: Optional[CompileResult] = None
    runs: List[RunOutcome] = field(default_factory=list)
    sandbox: List[str] = field(default_factory=list)
    diagnostic: str = ""  # вывод sanitizer-прогона (если CBENCH_SANITIZERS=1)


@dataclass
class LevelStat:
    pass_: float
    total: int
    per_run: List[int] = field(default_factory=list)


@dataclass
class UsageStat:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests: int = 0
    request_seconds: float = 0.0
    gen_tok_s: Optional[float] = None
    answers_cut_by_limit: int = 0
    loop_suspects: int = 0
    empty_answers: int = 0
    thinking_answers: int = 0
    code_from_think: int = 0


@dataclass
class RunSummary:
    """Агрегат прогона (одного или усреднённого по мульти-прогону)."""
    by_level: Dict[str, LevelStat] = field(default_factory=dict)
    by_topic: Dict[str, LevelStat] = field(default_factory=dict)
    results: List[TaskResult] = field(default_factory=list)
    sandbox_blocked_tasks: int = 0
    usage: UsageStat = field(default_factory=UsageStat)


@dataclass
class ProviderConfig:
    """Конфиг подключения к модели (пресет openai/llamacpp/lmstudio)."""
    name: str                  # openai | llamacpp | lmstudio
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enable_thinking_support: bool = False  # шлёт ли chat_template_kwargs.enable_thinking

    def redacted(self) -> Dict[str, Any]:
        """Конфиг без секрета — для печати/conditions."""
        d = {"name": self.name, "base_url": self.base_url, "model": self.model,
             "enable_thinking_support": self.enable_thinking_support,
             "has_api_key": bool(self.api_key)}
        return d


@dataclass
class Conditions:
    """Отпечаток условий прогона — по нему любой прогон самопроверяем."""
    sampler: Dict[str, Any] = field(default_factory=dict)
    sampler_mode: str = "reference"
    think: bool = False
    max_tokens: int = 16384
    n_runs: int = 1
    base_seed: int = 42
    levels: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    exec_timeout_s: float = 20.0
    sandbox: bool = True
    sandbox_mode: str = ""
    compiler: str = ""
    compiler_version: str = ""
    compiler_flags: List[str] = field(default_factory=list)
    platform: str = ""
    python_version: str = ""
    provider: Dict[str, Any] = field(default_factory=dict)  # ProviderConfig.redacted()
    case_bank_hash: str = ""
    n_cases: int = 0
    sanitizers: bool = False
    inject_nothink: bool = False
    nothink_thought: bool = False
