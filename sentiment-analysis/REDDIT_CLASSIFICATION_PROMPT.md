# Reddit Sentiment & Relevance Classification Prompt

## Task
You are an expert data analyst specializing in PC hardware consumer sentiment. Your task is to analyze a JSON batch of Reddit comments (organized as a thread tree) and classify each one based on its **Relevance** to the product and its **Sentiment**.

## Product for Analysis
**[PRODUCT_NAME_HERE]**

---

## 1. Relevance Classification (`relevance`)
Determine if the comment provides meaningful insight into the product.

### **Mark as `include` if:**
- **Personal Experience**: User shares their experience using the product.
- **Recommendation**: User recommends (or advises against) the product.
- **Opinionated Performance**: Discussion on thermals, FPS, value, or "worth it" factor.
- **Comparisons**: Direct comparison between this product and a competitor.
- **Technical Critique**: Specific praise or complaints about the product's design.

### **Mark as `exclude` if:**
- **Off-topic**: Discussion about games, other products, or general meta-talk.
- **Purely Factual/Q&A**: Specification questions or factual answers without opinion.
- **Meme/Joke**: Jokes, memes, or low-effort banter.
- **Bot/Automoderator**: Automated system messages.

---

## 2. Sentiment Classification (`sentiment`)
*Only applicable if relevance is `include`.*

- **positive**: Satisfaction, high performance, good value, or a "buy" recommendation.
- **negative**: Disappointment, overheating, poor value, stability issues, or "don't buy".
- **neutral**: Relevant discussion without a clear positive or negative leaning.

---

## 3. Reasoning Fields
For every classified comment, you MUST provide:
- **`relevanceReasoning`**: A short (1-sentence) explanation of why it was included or excluded.
- **`sentimentReasoning`**: A short (1-sentence) explanation of why it was tagged as positive, negative, or neutral.

---

## Instructions
1. **Analyze Context**: Use the hierarchical structure (replies) to understand sarcasm, rebuttals, or context for short replies.
2. **Handle `classifyThis`**: Only provide classification for comments where `"classifyThis": true`.
3. **Be Objective**: Classify based on the user's expressed opinion, not general knowledge.

## Output Format
Return ONLY a valid JSON object in the exact format shown below, mapping each `"commentId"` (where `"classifyThis": true`) to its classification results. Do NOT return the tree structure, do not repeat the text, and do not include markdown blocks outside the JSON.

```json
{
  "comments": [
    {
      "commentId": "example_id",
      "relevance": "include",
      "relevanceReasoning": "...",
      "sentiment": "positive",
      "sentimentReasoning": "..."
    }
  ]
}
```
