@echo off
REM ============================================================================
REM  REFERENCE RUN (Windows) -- identical conditions to the reference numbers.
REM  Runs the SAME sampler/levels as results-example so numbers are comparable.
REM
REM  Usage:  run_reference.bat <port> <label> [think]
REM    <port>   your OpenAI-compatible server port (vLLM 8000, LM Studio 1234, ...)
REM    <label>  name for output (ladder_<label>.json)
REM    think    (optional) word "think" -> reasoning mode for thinking models
REM
REM  Examples:
REM    run_reference.bat 8000 my-model
REM    run_reference.bat 8000 my-model think
REM ============================================================================
setlocal
if "%~1"=="" ( echo Usage: run_reference.bat ^<port^> ^<label^> [think] & exit /b 1 )
if "%~2"=="" ( echo Usage: run_reference.bat ^<port^> ^<label^> [think] & exit /b 1 )

set "PORT=%~1"
set "LABEL=%~2"
set "MODE=%~3"

REM --- FIXED REFERENCE CONDITIONS (do not change -> comparability) ---
REM Sampler is hardcoded in run_ladder.py: temp 1.0 / top_p 0.95 / top_k 20 / min_p 0 / seed 42.
set "LADDER_LEVELS=easy,medium,hard"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if /i "%MODE%"=="think" (
  set "THINK=1"
  set "LADDER_MAX_TOKENS=32000"
  echo [reference] THINKING mode, max_tokens=32000
) else (
  set "THINK=0"
  set "LADDER_MAX_TOKENS=16384"
  echo [reference] NON-THINKING mode, max_tokens=16384
)

REM find python
set "PY=python"
where python >nul 2>nul || set "PY=py"

"%PY%" run_ladder.py %PORT% %LABEL% all
echo.
echo Done. Result -^> ladder_%LABEL%.json
echo When publishing, state: model, quant/format, think/non-think, experts (for MoE).
endlocal
