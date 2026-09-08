@echo off
REM ============================================================================
REM  REFERENCE RUN (Windows) -- identical conditions to the reference numbers.
REM  Usage:  run_reference.bat <endpoint> <label> [think]
REM    <endpoint>  port or full URL (1234 / http://192.168.56.1:1234 / https://...)
REM    <label>     name for output (cbench_<label>.json)
REM    think       (optional) word "think" -> reasoning mode
REM ============================================================================
setlocal
if "%~1"=="" ( echo Usage: run_reference.bat ^<endpoint^> ^<label^> [think] & exit /b 1 )
if "%~2"=="" ( echo Usage: run_reference.bat ^<endpoint^> ^<label^> [think] & exit /b 1 )

set "ENDPOINT=%~1"
set "LABEL=%~2"
set "MODE=%~3"

set "CBENCH_LEVELS=easy,medium,hard"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if /i "%MODE%"=="think" (
  set "THINK=1"
  set "CBENCH_MAX_TOKENS=32000"
  echo [reference] THINKING mode, max_tokens=32000
) else (
  set "THINK=0"
  set "CBENCH_MAX_TOKENS=16384"
  echo [reference] NON-THINKING mode, max_tokens=16384
)

set "PY=python"
where python >nul 2>nul || set "PY=py"

"%PY%" run_cbench.py "%ENDPOINT%" "%LABEL%" all
echo.
echo Done. Result -^> cbench_%LABEL%.json
endlocal
