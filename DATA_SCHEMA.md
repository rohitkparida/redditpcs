# Data Schema Specification

## File Structure
Each category is a JSON file in `/src/data/{slug}.json`

## JSON Schema

```json
{
  "category": "Graphics Cards",
  "slug": "gpus",
  "updated": "2024-05-04T00:00:00Z",
  "description": "Best GPUs according to r/buildapc and r/hardware",
  "productCount": 10,
  "products": [
    {
      "rank": 1,
      "name": "NVIDIA GeForce RTX 4070 Super",
      "brand": "NVIDIA",
      "model": "RTX 4070 Super",
      "priceRange": "$599-$649",
      "mentions": 1247,
      "sentimentScore": 0.91,
      "redditQuotes": [
        {
          "quote": "Best price to performance this generation. 4070 Super hits the sweet spot for 1440p gaming.",
          "sourceUrl": "https://www.reddit.com/r/buildapc/comments/xyz123/comment/abc456/",
          "subreddit": "buildapc",
          "upvotes": 856
        },
        {
          "quote": "Upgraded from 3070 to 4070 Super, totally worth it for DLSS 3 alone.",
          "sourceUrl": "https://www.reddit.com/r/nvidia/comments/abc789/comment/def012/",
          "subreddit": "nvidia",
          "upvotes": 423
        }
      ],
      "affiliateLinks": {
        "amazon": "https://amazon.com/...",
        "newegg": "https://newegg.com/...",
        "bestbuy": "https://bestbuy.com/..."
      },
      "specs": {
        "memory": "12GB GDDR6X",
        "tdp": "220W"
      }
    }
  ]
}
```

## Field Definitions

### Category Object
| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Human-readable category name |
| `slug` | string | URL-friendly identifier (lowercase, hyphens) |
| `updated` | ISO8601 | Last data refresh timestamp |
| `description` | string | SEO meta description and intro text |
| `productCount` | integer | Number of ranked products |
| `products` | array | Ranked list of products |

### Product Object
| Field | Type | Description |
|-------|------|-------------|
| `rank` | integer | Position in ranking (1 = best) |
| `name` | string | Full product name |
| `brand` | string | Manufacturer |
| `model` | string | Specific model identifier |
| `priceRange` | string | Price range with dollar sign |
| `mentions` | integer | Reddit mention count |
| `sentimentScore` | float | 0.0 to 1.0 positivity score |
| `redditQuotes` | array | 2-5 real Reddit comments |
| `affiliateLinks` | object | Buy links per retailer |
| `specs` | object | Key specs object (varies by category) |

### RedditQuote Object
| Field | Type | Description |
|-------|------|-------------|
| `quote` | string | Exact quote from Reddit (trimmed) |
| `sourceUrl` | string | Direct link to comment |
| `subreddit` | string | Source subreddit name |
| `upvotes` | integer | Comment upvote count |

## Category-Specific Spec Fields

### GPUs
- `memory` (VRAM amount)
- `tdp` (power draw)

### CPUs
- `cores`
- `baseClock`
- `socket`

### Motherboards
- `socket`
- `formFactor`
- `chipset`

### RAM
- `capacity`
- `speed`
- `type`

### SSDs
- `capacity`
- `interface`
- `formFactor`

### Power Supplies
- `wattage`
- `efficiency`
- `modular`

### CPU Coolers
- `type` (air/AIO)
- `tdp`

### PC Cases
- `formFactor`
- `dimensions`

## Validation Rules
1. `rank` must be sequential starting from 1
2. `sentimentScore` between 0.0 and 1.0
3. `redditQuotes` minimum 2, maximum 5 per product
4. `sourceUrl` must be valid Reddit permalink
5. All affiliate links must use proper tracking IDs (placeholder for now)
