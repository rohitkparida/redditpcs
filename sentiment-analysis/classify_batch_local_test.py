import json
import os
import time
from pathlib import Path
import openvino_genai as ov_genai

# Define paths
base_dir = Path(r"c:\Users\Public\Work\redditpcs\sentiment-analysis")
model_path = r"C:\Users\Public\Work\llm_model\phi-2-int4-ov"
batch_file = base_dir / "batches" / "amd-radeon-rx-7900-xtx" / "amd-radeon-rx-7900-xtx.batch-28.json"

print("Loading test batch comments...")
with open(batch_file, 'r', encoding='utf-8') as f:
    full_batch = json.load(f)

# Collect the first 5 comments where classifyThis is True
test_comments = []

def collect_comments_recursive(node):
    if len(test_comments) >= 5:
        return
    if node.get("classifyThis") is True:
        # Create a clean minimal version to fit the model's context nicely
        test_comments.append({
            "commentId": node.get("commentId"),
            "text": node.get("text"),
            "upvotes": node.get("upvotes")
        })
    for reply in node.get("replies", []):
        collect_comments_recursive(reply)

for root in full_batch.get("comments", []):
    collect_comments_recursive(root)
    if len(test_comments) >= 5:
        break

print(f"Collected {len(test_comments)} comments for testing.")

# Load Prompt
prompt_path = base_dir / "REDDIT_CLASSIFICATION_PROMPT.md"
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt_text = f.read()

prompt_text = prompt_text.replace("[PRODUCT_NAME_HERE]", "AMD Radeon RX 7900 XTX")

# Create the minimal JSON batch string
minimal_batch = {
    "productName": "AMD Radeon RX 7900 XTX",
    "comments": test_comments
}
minimal_batch_str = json.dumps(minimal_batch, indent=2)

combined_prompt = f"{prompt_text}\n\nAnalyze this JSON batch and return the flat classifications object as specified in the output format. Ensure it is valid JSON:\n\n{minimal_batch_str}\n\nResponse JSON:"

print("\nLoading local INT4 model on CPU...")
t0 = time.time()
pipe = ov_genai.LLMPipeline(model_path, "CPU")
print(f"Model loaded in {time.time() - t0:.2f} seconds.")

# Set generation config for clean JSON output
config = ov_genai.GenerationConfig()
config.max_new_tokens = 600
config.temperature = 0.1  # Low temperature for highly deterministic classification

print("Generating classifications...")
t1 = time.time()
response = pipe.generate(combined_prompt, config)
gen_time = time.time() - t1
print(f"Generation completed in {gen_time:.2f} seconds.")

# Output raw and parsed results for user review
print("\n" + "="*60)
print("                    TEST CLASSIFICATION RESULTS")
print("="*60)

# Try to parse response
try:
    # Clean up markdown code blocks if the model wrapped it in ```json
    clean_response = response.strip()
    if clean_response.startswith("```"):
        lines = clean_response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_response = "\n".join(lines).strip()
    
    classification_data = json.loads(clean_response)
    comments_list = classification_data.get("comments", [])
    class_map = {c["commentId"]: c for c in comments_list if "commentId" in c}
    
    for i, original in enumerate(test_comments):
        cid = original["commentId"]
        print(f"\n--- Comment #{i+1} (ID: {cid}, Upvotes: {original['upvotes']}) ---")
        print(f"Comment Text:\n  \"{original['text'][:250]}...\"")
        print("-" * 40)
        if cid in class_map:
            cls = class_map[cid]
            print(f"Relevance          : {cls.get('relevance')}")
            print(f"Relevance Reasoning: {cls.get('relevanceReasoning')}")
            print(f"Sentiment          : {cls.get('sentiment')}")
            print(f"Sentiment Reasoning: {cls.get('sentimentReasoning')}")
        else:
            print("WARNING: Model omitted this comment ID from response!")
            
except Exception as e:
    print("FAILED TO PARSE RESPONSE AS JSON!")
    print(f"Error: {e}")
    print("\nRaw Model Output:")
    print(response)

print("\n" + "="*60)
