# Reddit Thread Discovery Prompt for Grok (Hybrid Workflow)

## Task
Identify the most relevant and high-quality Reddit threads for a specific PC hardware product. 

**Goal**: Find the "Gold Standard" threads where real users are discussing their experiences, performance, and value.

## Search Strategy
1. **Queries**: 
   - "[Product Name] reddit review"
   - "[Product Name] worth it reddit"
   - "[Product Name] vs [competitor] reddit"
2. **Subreddits**: Focus on r/buildapc, r/hardware, r/pcmasterrace, r/Amd, r/nvidia, r/intel.
3. **Recency**: Look for threads from the last 12 months.
4. **Quality**: Prioritize threads with **high comment counts** (20+ comments) and active discussion.

## Output Format
Return a JSON block with the following structure:

```json
{
  "productName": "PRODUCT_NAME_HERE",
  "analyzedAt": "2026-05-08",
  "threads": [
    {
      "url": "https://www.reddit.com/r/subreddit/comments/abc123/title_of_thread/",
      "title": "Thread Title Here",
      "commentCount": 150,
      "relevanceReason": "Deep dive into gaming performance and thermal issues."
    }
  ]
}
```

## Instructions
1. Find **5-10 high-quality threads** for the product.
2. Verify the URLs are correct and direct.
3. Ensure the threads have actual user discussions, not just news links or empty posts.
4. Return the JSON block clearly so it can be used for automated data collection.

## Product to Analyze
**PRODUCT_NAME_HERE**
