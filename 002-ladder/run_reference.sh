#!/usr/bin/env bash
# ============================================================================
#  REFERENCE RUN — прогон в ТОЧНО ТЕХ ЖЕ условиях, что эталонные цифры.
#  Usage:  ./run_reference.sh <endpoint> <label> [think]
#    <endpoint>  порт или полный URL (1234 / http://192.168.56.1:1234 / https://...)
#    <label>     имя для результата (файл cbench_<label>.json)
#    think       (опц.) слово "think" -> reasoning-режим
# ============================================================================
set -eu

ENDPOINT="${1:?укажите endpoint: ./run_reference.sh <endpoint> <label> [think]}"
LABEL="${2:?укажите label: ./run_reference.sh <endpoint> <label> [think]}"
MODE="${3:-nothink}"

export CBENCH_LEVELS="easy,medium,hard"

if [ "$MODE" = "think" ]; then
  export THINK=1
  export CBENCH_MAX_TOKENS=32000
  echo "[reference] THINKING mode, max_tokens=32000"
else
  export THINK=0
  export CBENCH_MAX_TOKENS=16384
  echo "[reference] NON-THINKING mode, max_tokens=16384"
fi

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

python run_cbench.py "$ENDPOINT" "$LABEL" all
echo ""
echo "Готово. Результат -> cbench_${LABEL}.json"
