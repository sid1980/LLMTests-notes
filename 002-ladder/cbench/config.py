"""CLI/env → RunConfig (выбор провайдера, компилятора, фильтров, лимитов)."""
from __future__ import annotations

import argparse
import os
import platform
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RunConfig:
    endpoint: str = ""
    label: str = "model"
    track: str = "all"          # code | all
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    levels: List[str] = field(default_factory=lambda: ["easy", "medium", "hard"])
    topics: List[str] = field(default_factory=list)
    case_ids: List[str] = field(default_factory=list)
    think: bool = False
    max_tokens: int = 16384
    http_timeout: int = 1800
    n_runs: int = 1
    cc: Optional[str] = None
    sanitizers: bool = False
    unsafe: bool = False


def _split_csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    return [x.strip() for x in v.split(",") if x.strip()]


def build_config(argv: Optional[List[str]] = None) -> RunConfig:
    env = os.environ
    p = argparse.ArgumentParser(
        prog="run_cbench",
        description="Бенчмарк знания языка Си для локальных LLM (OpenAI-совместимый API).")
    p.add_argument("endpoint", nargs="?", default=None,
                   help="порт или полный URL (например, 1234 или http://192.168.56.1:1234)")
    p.add_argument("label", nargs="?", default="model", help="метка прогона")
    p.add_argument("track", nargs="?", default="all", choices=["code", "all"],
                   help="трек: code|all")
    p.add_argument("--provider", choices=["openai", "llamacpp", "lmstudio", "ollama"],
                   default=env.get("CBENCH_PROVIDER"))
    p.add_argument("--base-url", default=env.get("CBENCH_BASE_URL"))
    p.add_argument("--api-key", default=env.get("CBENCH_API_KEY"))
    p.add_argument("--model", default=env.get("CBENCH_MODEL"))
    p.add_argument("--level", default=env.get("CBENCH_LEVELS", "easy,medium,hard"),
                   help="уровни через запятую (easy,medium,hard)")
    p.add_argument("--topic", default=env.get("CBENCH_TOPICS", ""),
                   help="темы через запятую (files,pointers,...)")
    p.add_argument("--case", default=env.get("CBENCH_CASES", ""),
                   help="id задач через запятую")
    p.add_argument("--runs", type=int, default=int(env.get("CBENCH_RUNS", "1")))
    p.add_argument("--timeout", type=int,
                   default=int(env.get("CBENCH_HTTP_TIMEOUT", "1800")),
                   help="таймаут HTTP-запроса к модели, сек (по умолчанию 1800)")
    p.add_argument("--cc", default=env.get("CBENCH_CC"), help="переопределить компилятор")
    p.add_argument("--sanitizers", action="store_true",
                   default=env.get("CBENCH_SANITIZERS", "0") == "1")
    p.add_argument("--unsafe", action="store_true",
                   default=env.get("CBENCH_UNSAFE", "0") == "1")
    a = p.parse_args(argv)

    think = env.get("THINK", "0") == "1"
    max_tokens = int(env.get("CBENCH_MAX_TOKENS", env.get("LADDER_MAX_TOKENS", "16384")))

    endpoint = a.endpoint or "1234"

    return RunConfig(
        endpoint=endpoint,
        label=a.label,
        track=a.track,
        provider=a.provider,
        base_url=a.base_url,
        api_key=a.api_key,
        model=a.model,
        levels=_split_csv(a.level) or ["easy", "medium", "hard"],
        topics=_split_csv(a.topic),
        case_ids=_split_csv(a.case),
        think=think,
        max_tokens=max_tokens,
        http_timeout=max(1, a.timeout),
        n_runs=max(1, a.runs),
        cc=a.cc,
        sanitizers=a.sanitizers,
        unsafe=a.unsafe,
    )


def resolve_endpoint(endpoint: str) -> str:
    """Нормализовать endpoint (порт → URL, голый URL → base)."""
    e = endpoint.strip()
    if e.startswith(("http://", "https://")):
        e = e.rstrip("/")
        if e.endswith("/v1"):
            e = e[:-3]
        return e
    return f"http://127.0.0.1:{int(e)}"


def platform_tag() -> str:
    return platform.platform()
