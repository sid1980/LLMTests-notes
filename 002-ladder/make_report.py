#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пересобрать HTML-отчёт по всем cbench_*.json в папке."""
import io
import sys
from pathlib import Path

# UTF-8 в консоль на любой ОС (Windows cp1251/cp1252 бьют кириллицу).
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cbench import report  # noqa: E402

if __name__ == "__main__":
    print(f"отчёт -> {report.build(HERE)}")
