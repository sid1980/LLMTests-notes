"""Доменный слой — чистые структуры данных, без I/O."""
from .case import Case, CaseBank, CaseKind, IOMode, Level, FileSpec, ExpectedResult, TestSpec
from .result import (
    ModelReply, CompileResult, RunOutcome, TaskResult, RunSummary,
    UsageStat, LevelStat, ProviderConfig, Conditions,
)

__all__ = [
    "Case", "CaseBank", "CaseKind", "IOMode", "Level", "FileSpec",
    "ExpectedResult", "TestSpec",
    "ModelReply", "CompileResult", "RunOutcome", "TaskResult", "RunSummary",
    "UsageStat", "LevelStat", "ProviderConfig", "Conditions",
]
