# Design Specification

## Visual Identity

### Color Palette
- **Primary:** `#FF4500` (Reddit Orange) - CTAs, links, rank badges
- **Background:** `#FFFFFF` (White) - Page background
- **Surface:** `#F6F7F8` - Cards, section backgrounds
- **Border:** `#E5E5E5` - Dividers, card borders
- **Text Primary:** `#1A1A1B` - Headlines, body text
- **Text Secondary:** `#787C7E` - Meta info, timestamps
- **Text Muted:** `#878A8C` - Captions, helper text

### Typography
- **Headlines:** Inter, 600-700 weight
- **Body:** Inter, 400 weight
- **Meta/Captions:** Inter, 400 weight, smaller size

### Spacing
- Page max-width: 1200px
- Section padding: 64px vertical
- Card gap: 24px
- Card padding: 24px
- Mobile padding: 16px

## Page Designs

### Homepage (`/`)

#### Hero Section
- Full width, white background
- Tagline: "PC building recommendations from real Redditors"
- Subtext: "No sponsored reviews. No fake ratings. Just honest opinions from r/buildapc and beyond."
- Simple search bar (visual only for v1)

#### Category Grid
- 4-column grid on desktop, 2 on tablet, 1 on mobile
- Cards link to category pages
- Each card: icon, category name, product count
- Hover: subtle shadow lift

**Category Card Structure:**
```
┌─────────────────────────┐
│  [Icon]                 │
│  Graphics Cards         │
│  10 products reviewed   │
└─────────────────────────┘
```

#### Footer
- "Updated weekly with fresh Reddit data"
- About link
- Disclosure statement

### Category Page (`/[category]`)

#### Header
- Breadcrumb: Home > Category
- Category name (H1)
- Description text
- "Last updated: May 4, 2024" timestamp

#### Product Rankings
- Vertical list, numbered
- Each product as full-width card

**Product Card Structure:**
```
┌────────────────────────────────────────────────────────────┐
│ ┌────┐ ┌───────────────────────────────────────────────┐ │
│ │ 1  │ │ Product Name                                  │ │
│ │    │ │ Brand • Price Range                           │ │
│ └────┘ └───────────────────────────────────────────────┘ │
│                                                            │
│  "Reddit quote goes here..." — u/username, r/buildapc      │
│  "Second quote here..." — u/username, r/hardware           │
│                                                            │
│  [Buy on Amazon]  [Buy on Newegg]                          │
│                                                            │
│  Mentioned 1,247 times • 91% positive sentiment           │
└────────────────────────────────────────────────────────────┘
```

#### Quote Display
- Italic text, in quotes
- Source: "— u/username, r/subreddit"
- Upvote count badge (optional)
- Source links to Reddit comment

#### Affiliate Buttons
- Two columns: Amazon | Newegg
- Primary style (orange background, white text)
- Full width on mobile
- "Check Price on {Store}" text

### About Page (`/about`)

#### Content Sections
1. **How It Works** - Data from Reddit, AI analysis, human review
2. **Data Sources** - r/buildapc, r/hardware, r/pcmasterrace, etc.
3. **Affiliate Disclosure** - Clear statement about commission earnings
4. **Update Schedule** - Weekly refresh cadence

## Responsive Breakpoints
- Desktop: 1024px+
- Tablet: 768px - 1023px
- Mobile: < 768px

## Animations (Minimal)
- Card hover: translateY(-2px) + shadow increase
- Duration: 200ms
- Easing: ease-out

## SEO Requirements
- Semantic HTML (article, nav, main, footer)
- Meta description per page
- Open Graph tags
- Structured data for products (JSON-LD)
- Sitemap.xml generation

## Accessibility
- WCAG 2.1 AA compliance
- Focus states on all interactive elements
- Alt text on images
- Sufficient color contrast (4.5:1 minimum)
