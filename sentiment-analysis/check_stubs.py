import json
from pathlib import Path

raw_dir = Path('raw_comments')
stubs = [f for f in raw_dir.glob('raw_*.json') if f.stat().st_size <= 5000]
for f in sorted(stubs[:4]):
    data = json.loads(f.read_text(encoding='utf-8'))
    keys = list(data.keys())
    comments = data.get('comments', None)
    n = len(comments) if comments is not None else 'NO_KEY'
    print(f.name, '->', n, 'comments, keys:', keys)
