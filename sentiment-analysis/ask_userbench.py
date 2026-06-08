import openvino_genai as ov_genai

model_path = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"

pipe = ov_genai.LLMPipeline(model_path, "CPU")

prompt = "Instruct: What is UserBenchmark and is it reliable?\nOutput:"

config = ov_genai.GenerationConfig()
config.max_new_tokens = 300
config.temperature = 0.5

print("Asking local model about UserBenchmark...")
response = pipe.generate(prompt, config)

print("\n--- Model Response ---")
print(response.strip())
