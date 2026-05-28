import json

with open('classified/amd-ryzen-7-9800x3d.template.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Product Name:", data.get('productName'))
print("Total root comments in template:", len(data['comments']))

total_comments = 0
def count_nodes(node):
    global total_comments
    total_comments += 1
    for r in node.get('replies', []):
        count_nodes(r)

for root in data['comments']:
    count_nodes(root)

print("Total recursive comments in template:", total_comments)
