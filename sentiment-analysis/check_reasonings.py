import json
from pathlib import Path

examples = {'include': [], 'exclude': []}

for f in sorted(Path('batches/amd-radeon-rx-7900-xt').glob('*.json'))[:15]:
    data = json.loads(f.read_text(encoding='utf-8'))

    def scan(nodes):
        for n in nodes:
            if n.get('classifyThis', True) and n.get('relevance') in ('include', 'exclude'):
                r = n['relevance']
                if len(examples[r]) < 5:
                    examples[r].append({
                        'text': n.get('text', '')[:130],
                        'relevance': r,
                        'reason': n.get('relevanceReasoning', ''),
                        'sentiment': n.get('sentiment'),
                        'sentReason': n.get('sentimentReasoning', '')
                    })
            scan(n.get('replies', []))

    scan(data.get('comments', []))

print("=== INCLUDED (on-topic, opinionated) ===\n")
for e in examples['include']:
    print(f"TEXT:       {e['text']}")
    print(f"REL REASON: {e['reason']}")
    print(f"SENTIMENT:  {e['sentiment']} | {e['sentReason']}")
    print()

print("=== EXCLUDED (off-topic/generic) ===\n")
for e in examples['exclude']:
    print(f"TEXT:       {e['text']}")
    print(f"REL REASON: {e['reason']}")
    print()
