import json
import time
import openvino_genai as ov_genai

model_path = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"

pipe = ov_genai.LLMPipeline(model_path, "CPU")

# Prompt testing UserBenchmark sarcasm without any hints
sarcastic_comment = "Oh yes, UserBenchmark says the Core i3 is 50% faster than the 7900 XTX in desktop utility, so Intel is clearly the superior platform. Truly the gold standard of hardware journalism."

prompt = f"""You are an expert data analyst specializing in PC hardware consumer sentiment.
Analyze the following Reddit comment about the product "AMD Radeon RX 7900 XTX" and classify its Relevance and Sentiment. Be highly alert to tech sarcasm, such as references to UserBenchmark's notorious benchmarks.

Comment text:
"{sarcastic_comment}"

Return ONLY a valid JSON in this exact format:
{{
  "relevance": "include" or "exclude",
  "relevanceReasoning": "1-sentence explanation",
  "sentiment": "positive", "negative", or "neutral",
  "sentimentReasoning": "1-sentence explanation"
}}

Response JSON:"""

config = ov_genai.GenerationConfig()
config.max_new_tokens = 150
config.temperature = 0.1

print("Testing sarcasm detection on local model...")
response = pipe.generate(prompt, config)

print("\n--- Model Response ---")
print(response.strip())
