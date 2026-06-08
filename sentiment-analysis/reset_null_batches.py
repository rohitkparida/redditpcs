"""
Reset batches that have classifyThis=True comments with relevance=None
so they get re-classified on the next run.
"""
import json
from pathlib import Path

reset = 0
for f in Path('batches').rglob('*.json'):
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        continue

    has_null = False

    def check(nodes):
        global has_null
        for n in nodes:
            if n.get('classifyThis', True) and n.get('relevance') is None:
                has_null = True
            check(n.get('replies', []))

    check(data.get('comments', []))

    if has_null:
        # Reset ALL classifyThis=True nodes in this batch so it gets fully re-done
        def reset_nodes(nodes):
            for n in nodes:
                if n.get('classifyThis', True):
                    n['relevance'] = None
                    n['relevanceReasoning'] = None
                    n['sentiment'] = None
                    n['sentimentReasoning'] = None
                reset_nodes(n.get('replies', []))

        reset_nodes(data.get('comments', []))
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        reset += 1
        print(f'  Reset: {f.name}')

print(f'\nTotal reset: {reset} batch files')
