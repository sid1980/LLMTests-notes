set LLAMA_PATH="d:\forAll\STC\Work\LLM\Bin\Win10\llama.cpp\llama-bench.exe"
set OUT=d:\forAll\STC\Work\LLMTests-notes\003-llama_bench\Qwen2.5-Coder-14B-Instruct-Q6_K.cpu.result.txt

%LLAMA_PATH% ^
   -m d:\forAll\STC\Work\LLM\Models\lmstudio-community\Qwen2.5-Coder-14B-Instruct-GGUF\Qwen2.5-Coder-14B-Instruct-Q6_K.gguf ^
   -ngl 99 ^
   -p 512 ^
   -n 128 ^
   -t 8,9,10,11,12,13,14 > "%OUT%" 2>&1
