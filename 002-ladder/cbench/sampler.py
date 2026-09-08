"""Сэмплер: режимы и эталонные условия (перенос идеи ladder-bench-dist)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent.parent

REF_SAMP = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "seed": 42}

_ENV = os.environ


def resolve_sampler() -> dict:
    """Итоговый сэмплер по CBENCH_SAMPLER (+ переопределения для custom)."""
    mode = (_ENV.get("CBENCH_SAMPLER") or "reference").strip().lower()
    if mode == "native":
        return {"seed": 42}
    if mode == "recommended":
        return {"seed": 42}  # заполнится после определения имени модели
    if mode == "custom":
        s = dict(REF_SAMP)
        for env, key, cast in (("CBENCH_TEMP", "temperature", float),
                               ("CBENCH_TOP_P", "top_p", float),
                               ("CBENCH_TOP_K", "top_k", int),
                               ("CBENCH_MIN_P", "min_p", float),
                               ("CBENCH_PRESENCE", "presence_penalty", float),
                               ("CBENCH_SEED", "seed", int)):
            v = _ENV.get(env)
            if v not in (None, ""):
                s[key] = cast(v)
        return s
    return dict(REF_SAMP)


def sampler_mode() -> str:
    return (_ENV.get("CBENCH_SAMPLER") or "reference").strip().lower()


def find_preset(model_name: str, think: bool):
    """Подобрать рекомендованный сэмплер из sampler_presets.json."""
    p = HERE / "sampler_presets.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    low = (model_name or "").lower()
    for pr in data.get("presets", []):
        if any(t in low for t in pr.get("match", [])):
            params = pr.get("think" if think else "nonthink") or pr.get("nonthink")
            if params:
                return {"name": pr.get("name", "?"), "source": pr.get("source", ""),
                        "params": dict(params)}
    return None
