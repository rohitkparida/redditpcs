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

# Extract first 3 comments where classifyThis is True
test_comments = []

def collect_comments_recursive(node):
    if len(test_comments) >= 3:
        return
    if node.get("classifyThis") is True:
        test_comments.append({
            "commentId": node.get("commentId"),
            "text": node.get("text"),
            "upvotes": node.get("upvotes")
        })
    for reply in node.get("replies", []):
        collect_comments_recursive(reply)

for root in full_batch.get("comments", []):
    collect_comments_recursive(root)
    if len(test_comments) >= 3:
        break

print("\nLoading local INT4 model on CPU...")
t0 = time.time()
pipe = ov_genai.LLMPipeline(model_path, "CPU")
print(f"Model loaded in {time.time() - t0:.2f} seconds.")

# Set generation config
config = ov_genai.GenerationConfig()
config.max_new_tokens = 150
config.temperature = 0.1

print("\nProcessing comments one-by-one locally...")

print("\n" + "="*70)
print("             ONE-BY-ONE LOCAL CLASSIFICATION RESULTS")
print("="*70)

for i, item in enumerate(test_comments):
    comment_text = item["text"]
    
    # Simple, highly directed single-comment prompt
    single_prompt = f"""You are an expert data analyst specializing in PC hardware consumer sentiment.
Analyze the following Reddit comment about the product "AMD Radeon RX 7900 XTX" and classify its Relevance and Sentiment.

Comment text:
"{comment_text}"

Return ONLY a valid JSON in this exact format:
{{
  "relevance": "include" or "exclude",
  "relevanceReasoning": "1-sentence explanation",
  "sentiment": "positive", "negative", or "neutral" (only if relevance is include, otherwise null),
  "sentimentReasoning": "1-sentence explanation"
}}

Response JSON:"""

    print(f"\n--- Comment #{i+1} (ID: {item['commentId']}, Upvotes: {item['upvotes']}) ---")
    print(f"Text:\n  \"{comment_text[:200]}...\"")
    print("-" * 50)
    
    t_start = time.time()
    response = pipe.generate(single_prompt, config)
    elapsed = time.time() - t_start
    
    # Try parsing response
    clean_res = response.strip()
    # Handle optional markdown backticks if model adds them
    if clean_res.startswith("```"):
        lines = clean_res.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_res = "\n".join(lines).strip()
        
    try:
        data = json.loads(clean_res)
        print(f"Relevance          : {data.get('relevance')}")
        print(f"Relevance Reasoning: {data.get('relevanceReasoning')}")
        print(f"Sentiment          : {data.get('sentiment')}")
        print(f"Sentiment Reasoning: {data.get('sentimentReasoning')}")
    except Exception as e:
        print("FAILED TO PARSE RESPONSE AS JSON!")
        print("Raw Output:")
        print(response)
    print(f"Inference Time     : {elapsed:.2f} seconds")

print("\n" + "="*70)
