import json
import re
import glob
from pathlib import Path

# Load registry
with open('sentiment-analysis/product_registry.json', 'r', encoding='utf-8') as f:
    registry = json.load(f)

print(f"Loaded {len(registry)} products from registry.")

# Build search keywords for each product
product_candidates = []
for slug, info in registry.items():
    name = info['name']
    category = info['category']
    
    # Generate search terms
    terms = [name.lower()]
    
    # Extract model number/distinct name
    # e.g., AMD Ryzen 7 9800X3D -> 9800x3d, 9800 x3d
    # nvidia-rtx-5090-32gb -> rtx 5090, 5090
    name_clean = name.lower()
    
    # Remove brands
    for brand in ['amd ryzen 9', 'amd ryzen 7', 'amd ryzen 5', 'amd radeon rx', 'amd', 'intel core ultra 9', 'intel core ultra 7', 'intel core ultra 5', 'intel core', 'intel arc', 'intel', 'nvidia geforce rtx', 'nvidia rtx', 'nvidia', 'corsair', 'g.skill', 'crucial', 'samsung', 'western digital', 'wd', 'msi', 'asus', 'gigabyte', 'asrock', 'be quiet!', 'noctua', 'thermalright', 'arctic', 'lian li', 'fractal design', 'fractal', 'nzxt', 'montech', 'phanteks']:
        if brand in name_clean:
            name_clean = name_clean.replace(brand, '')
    
    name_clean = name_clean.strip()
    terms.append(name_clean)
    
    # Model numbers: digits followed optionally by letters (e.g. 9800x3d, 285k, 5090, 6700)
    models = re.findall(r'\b\d{3,4}[a-zA-Z0-9]*\b', name.lower())
    for m in models:
        terms.append(m)
        if 'x3d' in m:
            terms.append(m.replace('x3d', ' x3d'))
            
    # For cases and coolers, get distinct model names
    if category.lower() in ['cases', 'coolers', 'motherboards', 'ram', 'ssds', 'psus']:
        # e.g. "torrent", "lancool 216", "peerless assassin"
        parts = [p.strip() for p in name_clean.split('/')]
        terms.extend(parts)
        # Also individual words if they are long
        for p in parts:
            subparts = p.split()
            if len(subparts) > 1:
                terms.append(" ".join(subparts))
                
    # Clean duplicates and empty terms
    unique_terms = []
    for t in terms:
        t_clean = t.strip().lower()
        if t_clean and len(t_clean) > 2 and t_clean not in unique_terms:
            unique_terms.append(t_clean)
            
    product_candidates.append({
        'slug': slug,
        'name': name,
        'category': category,
        'terms': unique_terms
    })

print("Sample product keywords:")
for p in product_candidates[:5]:
    print(f"  {p['name']} ({p['slug']}): {p['terms']}")

# Now let's gather all threads
thread_files = glob.glob('public/sentiment-evidence/**/threads.json', recursive=True)
all_threads = []
for f in thread_files:
    dir_name = Path(f).parent.name
    with open(f, 'r', encoding='utf-8') as f_obj:
        data = json.load(f_obj)
    prod_name = data.get('productName', dir_name)
    for t in data.get('threads', []):
        all_threads.append({
            'current_product_slug': dir_name,
            'current_product_name': prod_name,
            'url': t.get('url'),
            'topComments': t.get('topComments', [])
        })

print(f"Found {len(all_threads)} threads total in database.")

# Test finding candidates for first 5 threads
for idx, t in enumerate(all_threads[:5]):
    title = "No Title"
    body = ""
    if t['topComments']:
        text = t['topComments'][0].get('text', '')
        lines = text.split('\n')
        title = lines[0]
        if len(lines) > 1:
            body = '\n'.join(lines[1:])
            
    full_text = (title + " " + body).lower()
    
    # Match candidate products
    matched = []
    for p in product_candidates:
        # Match any of the terms as word boundaries if possible, or simple substring
        for term in p['terms']:
            if term in full_text:
                matched.append(p)
                break
                
    print(f"\nThread #{idx+1}: {title[:80]}...")
    print(f"  Current product: {t['current_product_name']} ({t['current_product_slug']})")
    print(f"  Matched candidates: {[m['name'] for m in matched[:5]]}")
