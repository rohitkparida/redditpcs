# PC Parts Reddit Recs Site — Full Summary

---

## The Product
Reddit-powered PC parts recommendation site. Shows what Reddit actually thinks about PC components. Monetized via affiliate links (Amazon, Newegg etc). Differentiator is Reddit trust layer — real quotes, sentiment scores, community consensus. No competitor does this.

---

## Stack
- **Frontend**: To be built
- **Database**: Google Sheets for MVP → Supabase when ready
- **Data pipeline**: Grok prompts → Google Sheets initially, automated later
- **Hosting**: Vercel (free tier)
- **Affiliate**: Amazon Associates + Newegg

---

## Homepage Design
- **Nav**: Component categories (GPU, CPU, RAM etc)
- **Hero**: Search bar + budget pills (All / Under $300 / $300-500 / $500-800 / $800+)
- **Section 1**: Leaderboard — most recommended parts ranked by mention count with sentiment dots
- **Section 2**: Hot discussions this week
- **Section 3**: Reddit says avoid these — highest differentiating section
- **Section 4**: Hot comparisons (X vs Y with Reddit verdict %)
- **Section 5**: Auto-scrolling carousel of popular Reddit builds
- **Footer**: About, How it works, Request a part, Support us
- Grid of components not tabs
- Builds section below categories in carousel format
- Budget range slider stays on builds page not carousel
- Carousel has static pills (All / Under $800 / $800-1200 / $1200+)

---

## Component Page
- Reddit mention count
- Sentiment score (% positive)
- Loves/complaints grid
- Inline Reddit quotes with highlight phrases
- Link to source threads
- Affiliate buy button
- "Last updated: Month Year" subtle footer text
- Popular builds using this part at bottom

---

## Non-Negotiables
1. Reddit mention count per part
2. Sentiment score
3. Actual Reddit quotes inline
4. Link back to source thread
5. Parts organized by category
6. Budget filter
7. Search
8. Affiliate buy link on every part
9. Avoid these section
10. Data freshness indicator

---

## Data Strategy
- Scrape cpus.gg and gpus.gg for parts list, specs, tags
- Run tags through LLM to expand and rephrase (not copy)
- Reddit data via .json suffix — no PRAW needed
- Refresh manually once a month
- Show "Last updated: Month Year" — honest, subtle
- ~100 parts at launch, manually seeded

---

## Scoring System
- Sentiment calculated at **author level** not comment level
- Each unique author = exactly one vote
- Net sentiment per author determined by majority of their individual classified comments.
- `sentimentScore` = positive authors / total unique authors × 100
- Deduplication by author handled in **code not prompt**
- If same author classified multiple times → keep highest upvoted comment

---

## Pipeline Architecture

### Overview
```
Fetch → Store trees → Split into batches 
     → LLM classify → Merge → Aggregate 
     → Database → Frontend
```

### Fetch Script
- Stores full comment trees per product
- Captures: commentId, author, text, upvotes, replies, threadUrl, subreddit
- Author stored at fetch time, stripped before sending to LLM

### Batch Structure
```json
{
  "batchId": "9800x3d-batch-05",
  "threadUrl": "https://reddit.com/r/buildapc/comments/...",
  "threadTitle": "9800X3D review - stunning performance",
  "rootComment": {
    "commentId": "lx3y39o",
    "text": "I have a 13900k and am tempted...",
    "upvotes": 47,
    "classifyThis": true,
    "relevance": null,
    "relevanceReasoning": null,
    "sentiment": null,
    "sentimentReasoning": null
  },
  "comments": [
    {
      "commentId": "lx4ps1v",
      "text": "Are you having a rough time?",
      "upvotes": 12,
      "relevance": null,
      "relevanceReasoning": null,
      "sentiment": null,
      "sentimentReasoning": null,
      "replies": [
        {
          "commentId": "lx4qlei",
          "text": "Nah I'm one of the lucky ones...",
          "upvotes": 1,
          "relevance": null,
          "relevanceReasoning": null,
          "sentiment": null,
          "sentimentReasoning": null,
          "replies": []
        }
      ]
    }
  ]
}
```

### Batch Sizing
- **Character count based** not comment count
- `MAX_CHARS = 8,000` / `MIN_CHARS = 4,000` (safe defaults for all free models)
- Never cut mid-branch — complete branches always stay together
- If thread spans multiple batches → root repeated as anchor, `classifyThis: false`
- If single branch exceeds MAX_CHARS → truncate deepest replies, log discards

### LLM Fills
```
relevance, relevanceReasoning
sentiment, sentimentReasoning  
```

### Code Handles
```
author (deduplication)
character count batching
root comment averaging across batches
validation
aggregation
```


### Root Comment Handling
- `classifyThis: true` on first batch occurrence
- `classifyThis: false` on subsequent batches (context only)
- If classified multiple times → majority vote wins
- Ties → more conservative classification wins (positive/negative tie → neutral)

### Merge Script
- Deduplicates by author — keep highest upvoted comment
- Averages root comment sentiment across batches by majority vote
- Reattaches author field from fetch data

### Validation Script
```python
assert comment['relevance'] in ['include', 'exclude']
assert comment['sentiment'] in ['positive', 'negative', 'neutral']
assert comment['relevanceReasoning'] != ""
assert comment['sentimentReasoning'] != ""
```

### Aggregation Output
- `sentimentScore` — % positive authors
- `recommendCount` — authors who explicitly recommend
- Top 5 quotes for frontend display
- `loves` — 3-5 common praise themes
- `complaints` — 2-4 common criticism themes

---

## Database Schema (Supabase)
```sql
parts (id, name, category, price, affiliate_url, specs, tags)
comments (id, part_id, author, text, upvotes, sentiment, 
          relevance, thread_url, subreddit, analyzed_at)
sentiment_summary (part_id, sentiment_score, recommend_count,
                   loves, complaints, updated_at)
quotes (id, part_id, comment_id, text, upvotes, subreddit, thread_url)
builds (id, title, total_cost, reddit_url, upvotes, source_type)
```

---

## Automation
- Classification automated via OpenRouter free models
- `google/gemini-2.0-flash-exp:free` primary
- `meta-llama/llama-3.3-70b-instruct:free` fallback
- Rotate between models to stay within free tier daily limits
- Add $5-10 credit if needed — entire pipeline costs under $3

---

## Business Model
- Affiliate commissions (Amazon 2-3% on PC parts)
- High AOV (~$400 average part) = ~$10 per conversion
- Target: 50k monthly visits at 2% conversion = ~$11k/month realistic at scale
- Bare Minimum target =  $500/month (because that's my current day job monthly income, so I can quit my job and do this fulltime.)
- North star: Joo Tat of RedditRecs at $5.2k/month from similar model
- Launch manually, automate once traffic confirmed

---

## Future Scope & Roadmap
- **Incremental Thread Expansion**: Populate with 7-10 "Elite" threads first, then expand by asking Grok for supplementary URLs.
- **Delta Analysis Engine**: Update `split_batches.py` to skip `commentId`s that already exist in `classified.json` to prevent re-analyzing and double-counting.
- **Automated Discovery**: Build a script to auto-search Reddit for new reviews using Search APIs.
- **Sentiment Weighting**: Weight final scores based on comment upvotes (logarithmic scale).
- **Consensus Tooltips**: UI feature to show "Why" behind the sentiment using LLM reasoning.