# Models in the example results / Модели в примере

Все прогоны: local INT4 (AutoRound W4A16, group_size 128), vLLM, RTX 4090 48GB,
sampler `temp 1.0 / top_p 0.95 / top_k 20 / min_p 0 / seed 42`, **non-thinking**.
Значение = % решённых задач уровня.

| Метка в json | Полное имя модели | Происхождение | Арх | Квант | hard | tools |
|---|---|---|---|:--:|:--:|:--:|
| `qwen36-27b-wide` | **Qwen3.6-27B** (wide-квант) | чистая база (Alibaba/Qwen) | dense | INT4 наш «wide»: SSM-проекции в BF16 | **78** | 83 |
| `qwen36-27b-base-int4-lorbus` | **Qwen3.6-27B** | чистая база (Alibaba/Qwen) | dense | INT4, квант [Lorbus/Qwen3.6-27B-int4-AutoRound](https://huggingface.co/Lorbus/Qwen3.6-27B-int4-AutoRound) | 70 | 83 |
| `qwen36-27b-abliterated-int4` | **Qwen3.6-27B abliterated** | база + наша мягкая Heretic-абляция (KL 0.0089); опубликована: [antonyMox/Qwen3.6-27B-abliterated-AutoRound-INT4-MTP](https://huggingface.co/antonyMox/Qwen3.6-27B-abliterated-AutoRound-INT4-MTP) | dense | INT4 наш | 70 | **87** |
| `qwen35-27b-base-int4-v2calib` | **Qwen3.5-27B** | чистая база | dense | INT4 наш («wide»: linear_attn в BF16) | 68 | 80 |
| `qwen36-35b-base-exp8` | **Qwen3.6-35B-A3B** | чистая база | MoE | INT4 наш, 8 экспертов/токен | 50 | 80 |
| `qwopus27b-coder-v2calib` | **Qwopus3.6-27B-Coder** | Claude-Opus reasoning-дистилл коде­ра, автор [Jackrong](https://huggingface.co/Jackrong) | dense | INT4 наш | 45 | 80 |
| `qwopus35b-coder-200-10exp-temp1` | **Qwopus3.6-35B-A3B-Coder** | Claude-Opus дистилл, Jackrong | MoE | INT4 наш, 10 экспертов | 45 | 80 |
| `qwopus27b-coder-censored` | **Qwopus3.6-27B-Coder** (censored) | Claude-Opus дистилл, Jackrong | dense | INT4 наш (64 iters) | 35 | 87 |
| `huihui-35b-int4-10exp` | **Huihui Qwen3.6-35B-A3B Claude-4.7-Opus abliterated** | Opus-дистилл + аблитерация (huihui) | MoE | INT4 наш | 38 | 73 |

## Что такое «Qwopus» / What is "Qwopus"

**Qwopus** = народное имя для дистиллятов **Qw**en × Cl**opus** (Claude Opus): базовую Qwen
дообучали на reasoning-трейсах Claude Opus. Не официальные Qwen-модели — комьюнити-файнтюны
(в основном автора Jackrong). Мы квантовали их в INT4 сами из BF16-исходников.

**Qwopus** = community nickname for Qwen models distilled on Claude-Opus reasoning traces
(mostly by Jackrong). Not official Qwen releases. We quantized them to INT4 ourselves.

## Ключевой вывод примера / Key takeaway

Чистые базы Qwen (27B hard 70, 35B hard 50) на кодинге **обходят Opus-дистилл-кодеры**
(hard 45) при одинаковом рецепте кванта — в non-thinking режиме. Дистилл под Opus-стиль,
похоже, просаживает сырой алгоритмический код. (Проверка в thinking-режиме — отдельно.)

Clean Qwen bases beat the Opus-distilled coders on this benchmark (same quant recipe,
non-thinking). Distillation toward Opus reasoning-style seems to cost raw algorithmic coding.
