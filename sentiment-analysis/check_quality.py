import json
from pathlib import Path
from collections import defaultdict

product_stats = defaultdict(lambda: {'include': 0, 'exclude': 0, 'null': 0, 'bad': []})

for f in Path('batches').rglob('*.json'):
    product = f.parent.name
    data = json.loads(f.read_text(encoding='utf-8'))

    def scan(nodes):
        for n in nodes:
            if n.get('classifyThis', True):
                r = n.get('relevance')
                if r == 'include':
                    product_stats[product]['include'] += 1
                elif r == 'exclude':
                    product_stats[product]['exclude'] += 1
                elif r is None:
                    product_stats[product]['null'] += 1
                else:
                    product_stats[product]['bad'].append(f'{f.name}:{r}')
            scan(n.get('replies', []))

    scan(data.get('comments', []))

print(f"{'Product':<45} {'Inc':>5} {'Exc':>5} {'Null':>5} {'Rate':>6}  Bad?")
print('-' * 80)
for p, s in sorted(product_stats.items()):
    total = s['include'] + s['exclude']
    rate = f"{s['include']/total:.0%}" if total > 0 else 'N/A'
    bad = str(s['bad'][:2]) if s['bad'] else ''
    print(f"{p:<45} {s['include']:>5} {s['exclude']:>5} {s['null']:>5} {rate:>6}  {bad}")
