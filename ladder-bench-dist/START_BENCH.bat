@echo off
REM ============================================================================
REM  Двойной клик -> сканирует локальные LLM-серверы (vLLM / LM Studio /
REM  Ollama / llama.cpp), даёт выбрать сервер и модель, запускает бенчмарк.
REM  Double-click -> scans local LLM servers, pick one, benchmark runs.
REM  Аргументы не нужны / no arguments needed.
REM ============================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM find python
set "PY=python"
where python >nul 2>nul || set "PY=py"

"%PY%" start_bench.py
echo.
pause
endlocal
