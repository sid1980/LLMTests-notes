#!/usr/bin/env bash
# ============================================================================
#  REFERENCE RUN — прогон в ТОЧНО ТЕХ ЖЕ условиях, что эталонные цифры.
#  Так ваши результаты СРАВНИМЫ с нашими (results-example/).
#  REFERENCE RUN — identical conditions to the reference numbers, so your
#  results are directly comparable.
#
#  Usage:  ./run_reference.sh <port> <label> [think]
#    <port>   порт вашего OpenAI-совместимого сервера (vLLM :8000, LM Studio :1234, ...)
#    <label>  имя для результата (файл ladder_<label>.json)
#    think    (опц.) слово "think" -> reasoning-режим для думающих моделей
#
#  Примеры / examples:
#    ./run_reference.sh 8000 my-model              # non-thinking (как большинство наших)
#    ./run_reference.sh 8000 my-model think        # thinking-режим (32k budget)
# ============================================================================
set -eu

PORT="${1:?укажите порт: ./run_reference.sh <port> <label> [think]}"
LABEL="${2:?укажите label: ./run_reference.sh <port> <label> [think]}"
MODE="${3:-nothink}"

# --- ЗАФИКСИРОВАННЫЕ ЭТАЛОННЫЕ УСЛОВИЯ (не менять — иначе несравнимо) ---
# Сэмплер зашит в run_ladder.py: temp 1.0 / top_p 0.95 / top_k 20 / min_p 0 / seed 42.
# Полная лестница (easy+medium+hard) + tools. Таймаут задачи 20с.
export LADDER_LEVELS="easy,medium,hard"

if [ "$MODE" = "think" ]; then
  export THINK=1
  export LADDER_MAX_TOKENS=32000     # запас под reasoning, иначе content пустой
  echo "[reference] THINKING mode, max_tokens=32000"
else
  export THINK=0
  export LADDER_MAX_TOKENS=16384
  echo "[reference] NON-THINKING mode, max_tokens=16384"
fi

# кодировка вывода (эмодзи в консоли)
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

python run_ladder.py "$PORT" "$LABEL" all
echo ""
echo "Готово. Результат -> ladder_${LABEL}.json"
echo "При публикации укажите: модель, квант/формат, think/non-think, эксперты (для MoE)."
