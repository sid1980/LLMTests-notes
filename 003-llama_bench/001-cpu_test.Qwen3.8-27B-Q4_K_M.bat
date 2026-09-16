set LLAMA_PATH="d:\forAll\STC\Work\LLM\Bin\Win10\llama.cpp\llama-bench.exe"
set OUT=d:\forAll\STC\Work\LLMTests-notes\003-llama_bench\Qwen3.8-27B-Q4_K_M.cpu.result.txt

%LLAMA_PATH% ^
   -m d:\Lmstudio\models\lmstudio-community\Qwen3.8-27B-GGUF\Qwen3.8-27B-Q4_K_M.gguf ^
   -ngl 99 ^
   -p 512 ^
   -n 128 ^
   -t 7,8,9,10,11,12,13,14 > "%OUT%" 2>&1
