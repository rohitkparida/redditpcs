# RedditPCs - Agent Context

## Project Overview
Build a static affiliate product recommendation site called **RedditPCs**.

**Stack:** Astro + Tailwind CSS + static JSON data files
**Deploy target:** GitHub Pages (static output)
**Domain:** redditpcs.com (future)

## Core Purpose
Display PC part rankings based on Reddit community sentiment. Users get honest recommendations from real builders, not paid reviews.

## Site Structure

### Pages
1. **Homepage** (`/`) - Category grid showing all PC part types
2. **Category Page** (`/[category]`) - Ranked list of products in that category
3. **About Page** (`/about`) - How it works, data sources, disclosure

### Categories (v1)
- GPUs (Graphics Cards)
- CPUs (Processors)
- Motherboards
- RAM
- SSDs
- Power Supplies
- CPU Coolers
- PC Cases

## Key Features
- Static site generation at build time
- JSON data files for each category
- Reddit quotes with source links on every product
- Affiliate buy buttons (Amazon, Newegg)
- "Updated on" timestamp per category
- Clean, fast, SEO-friendly

## Data Flow
1. Data stored in `/src/data/*.json` files
2. Astro pages read JSON at build time
3. Static HTML generated for each route
4. Deploy to GitHub Pages

## Monetization
Affiliate links. Full disclosure on about page.

## Success Metrics
- Page speed < 1s
- Mobile responsive
- SEO optimized for "best [part] reddit" queries
