import openvino_genai as ov_genai
import time

model_path = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"
print("Loading model on GPU...")
t0 = time.time()
try:
    pipe = ov_genai.LLMPipeline(model_path, "GPU")
    print(f"Success! Model loaded on GPU in {time.time() - t0:.2f}s")
except Exception as e:
    print(f"Failed to load on GPU: {e}")
    print("Trying CPU...")
    t0 = time.time()
    try:
        pipe = ov_genai.LLMPipeline(model_path, "CPU")
        print(f"Success! Model loaded on CPU in {time.time() - t0:.2f}s")
    except Exception as e2:
        print(f"Failed to load on CPU: {e2}")
