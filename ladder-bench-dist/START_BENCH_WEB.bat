@echo off
REM ============================================================================
REM  Двойной клик -> веб-панель бенча в браузере: скан серверов, параметры,
REM  мульти-прогон, живой лог, отчёт. / Web control panel in your browser.
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

"%PY%" bench_web.py
echo.
pause
endlocal
