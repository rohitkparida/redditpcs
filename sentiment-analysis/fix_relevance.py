import json
from pathlib import Path

fixed = 0
for f in Path('batches').rglob('*.json'):
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        continue
    changed = False

    def fix(nodes):
        global changed
        for n in nodes:
            r = n.get('relevance')
            if r == 0 or r == '0':
                n['relevance'] = 'exclude'
                changed = True
            elif r == 1 or r == '1':
                n['relevance'] = 'include'
                changed = True
            fix(n.get('replies', []))

    fix(data.get('comments', []))
    if changed:
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        fixed += 1

print(f'Fixed {fixed} files')
