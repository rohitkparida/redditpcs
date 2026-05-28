# Comprehensive Reddit Sentiment Analysis System

## Overview
This is a complete system for analyzing Reddit sentiment about PC hardware products, replacing unreliable LLM-generated sentiment scores with evidence-based, transparent sentiment analysis using actual Reddit comments.

## Problem Statement
The original system used `sentimentScore` fields that were:
- Hallucinated/fabricated by LLMs
- Not based on real user opinions
- Lacked transparency and verification
- Had no evidence to support the scores

## Solution Architecture
A multi-layered pipeline that:
1. Fetches real Reddit comments using .json search API
2. Classifies sentiment objectively (positive/negative/neutral)
3. Aggregates counts using reliable code
4. Stores evidence for full transparency
5. Updates frontend to display granular metrics

## Key Components

### 1. Data Structure Changes
**Before:**
```json
{
  "sentimentScore": 0.85,
  "mentions": 150
}
```

**After:**
```json
{
  "positiveReviews": 125,
  "negativeReviews": 15,
  "neutralReviews": 10,
  "recommendationRate": 0.89,
  "mentions": 150
}
```

### 2. Frontend Updates
- Updated `[category].astro` to show review counts instead of sentiment scores
- Updated `[product].astro` to display granular sentiment breakdown
- Added evidence section showing actual Reddit threads and comments
- Modified `getSentimentColor` to use `recommendationRate`

### 3. Data Collection Pipeline

#### Method A: Grok-Based (Limited)
- Use `PROMPT_FOR_GROK.md` with single product per conversation
- Grok classifies sentiment from Reddit discussions
- Limited by Grok's access to Reddit API
- May provide insufficient comment counts

#### Method B: Direct API Access (Preferred)
- Use `fetch_reddit_working.py` for reliable data collection
- Direct access to Reddit's .json search API
- Handles API limitations and rate limiting
- Provides consistent, comprehensive data

### 4. Processing Scripts

#### `count_comments.py`
- Counts sentiments from classified JSON data
- Replaces unreliable LLM-generated summaries
- Only includes `relevance: 'include'` comments
- Generates accurate sentiment breakdowns

#### `aggregate_comments.py`
- Aggregates classified comments across all products
- Creates unified sentiment database
- Handles multiple product categories (CPUs, GPUs, etc.)

#### `store_evidence.py`
- Organizes classified data for frontend display
- Creates evidence files in `src/data/sentiment-evidence/`
- Enables users to verify sources and see full context

#### `update_json_files.py`
- Updates main data files with aggregated counts
- Calculates recommendation rates
- Maintains data consistency across categories

#### `switch_analysis_method.py`
- Switches between targeted (50 opinions) and whole-thread analysis
- Maintains both datasets for flexibility
- Allows method comparison and validation

## Classification Schema

### Sentiment Categories
- **positive**: User expresses positive feelings (satisfied, impressed, happy)
- **negative**: User expresses negative feelings (disappointed, frustrated, regret)
- **neutral**: User expresses neutral/meh feelings (okay, decent, nothing special)

### Relevance Filter
- **include**: Comment is directly about the product experience/opinion
- **exclude**: Comment is off-topic, meme, or unrelated to product

## Data Flow

### Step 1: Data Collection
```
Product Name → Reddit Search → Comment Extraction → Sentiment Classification → JSON Output
```

### Step 2: Processing
```
Classified JSON → Count Sentiments → Aggregate Data → Update Main Files
```

### Step 3: Display
```
Main Data Files → Frontend Components → Evidence Display → User Verification
```

## Evidence Structure
```
src/data/sentiment-evidence/
├── amd-ryzen-7-9800x3d/
│   ├── threads.json     # Thread summaries
│   ├── comments.json    # All classified comments
│   └── summary.json     # Aggregated counts
└── ...
```

## Frontend Evidence Display

### Product Pages Show:
- **Reddit threads analyzed** with comment counts
- **Sentiment breakdown** per thread
- **"Show all analyzed comments"** button
- Direct links to original Reddit threads for verification

### Category Pages Show:
- **Review counts** instead of sentiment scores
- **Recommendation rates** based on positive/negative ratio
- **Evidence links** to verify sources

## Usage Instructions

### For Individual Products:
```bash
# 1. Collect data
python fetch_reddit_working.py --product "AMD Ryzen 7 9800X3D" --output amd-ryzen-7-9800x3d.classified.json

# 2. Count sentiments
python count_comments.py --input amd-ryzen-7-9800x3d.classified.json

# 3. Store evidence
python store_evidence.py --classified-dir ./classified --evidence-dir ../src/data/sentiment-evidence
```

### For All Products:
```bash
# 1. Aggregate all products
python aggregate_comments.py --input-dir ./classified --output aggregated_counts.json

# 2. Update main data files
python update_json_files.py --counts aggregated_counts.json --data-dir ../src/data
```

### Switch Analysis Methods:
```bash
# Switch to whole-thread analysis
python switch_analysis_method.py --method whole --evidence-dir ../src/data/sentiment-evidence

# Switch back to targeted analysis
python switch_analysis_method.py --method targeted --evidence-dir ../src/data/sentiment-evidence
```

## Product Coverage

### CPUs (4 products)
1. AMD Ryzen 7 9800X3D
2. Intel Core Ultra 9 285K
3. AMD Ryzen 7 7800X3D
4. Intel Core Ultra 5 245K

### GPUs (23 products)
- AMD GPUs (11): RX 9070 XT, RX 7700 XT, RX 9060 XT, RX 7900 XTX, RX 7900 XT, RX 7900 GRE, RX 6700 XT, RX 9070, RX 9060 XT 8GB
- NVIDIA GPUs (10): RTX 5070 Ti, RTX 5090, RTX 5080, RTX 4070 Ti Super, RTX 4090, RTX 4060 Ti, RTX 5070, RTX 5060 Ti, RTX 5060 Ti, RTX 5060
- Intel GPUs (3): Arc B580, Arc B570, Arc A750

## Quality Assurance

### Data Validation
- Minimum 40 comments per product
- Balanced sentiment distribution (no artificial bias)
- Real Reddit URLs and thread references
- Proper comment IDs and metadata

### Reliability Measures
- Code-based counting instead of LLM summaries
- Multiple search terms per product
- Error handling and retry logic
- Rate limiting to avoid API blocking

### Transparency Features
- Full comment text displayed to users
- Direct links to original Reddit threads
- Author names and upvote counts
- Thread context and discussion flow

## Benefits Over Original System

### 1. Credibility
- Based on real user opinions, not hallucinations
- Verifiable evidence with source links
- Transparent methodology

### 2. Accuracy
- Code-based sentiment counting
- No artificial distribution requirements
- Real-world sentiment distribution

### 3. Transparency
- Users can see actual Reddit comments
- Direct links to verify sources
- Full evidence trail

### 4. Flexibility
- Switch between analysis methods
- Scale to more products
- Adapt to different sentiment needs

## Future Enhancements

### 1. Advanced Classification
- Machine learning sentiment analysis
- Context-aware classification
- Multi-language support

### 2. Real-time Updates
- Automated Reddit monitoring
- Continuous sentiment tracking
- Trend analysis

### 3. Expanded Sources
- Multiple platforms (Twitter, forums, reviews)
- Cross-platform sentiment comparison
- Broader coverage

## Implementation Checklist

- [x] Update JSON schema for all product files
- [x] Modify frontend components for new display
- [x] Create data collection scripts
- [x] Implement sentiment counting logic
- [x] Build evidence storage system
- [x] Add method switching capability
- [x] Create comprehensive documentation
- [x] Test with sample data
- [ ] Deploy to production
- [ ] Monitor performance and accuracy

## Conclusion

This system provides a robust, transparent, and evidence-based approach to Reddit sentiment analysis for PC hardware products. It replaces unreliable LLM-generated scores with verifiable user opinions, giving users confidence in the recommendations and full access to the underlying evidence.

The modular design allows for easy expansion and adaptation, while the comprehensive documentation ensures maintainability and future development.
