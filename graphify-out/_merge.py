"""Graphify merge step: combines AST + semantic chunks into extract.json"""
import json
from pathlib import Path

def read_json(path):
    for enc in ('utf-8-sig', 'utf-16', 'utf-8'):
        try:
            return json.loads(Path(path).read_bytes().decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise RuntimeError(f'Cannot decode {path}')

ast = read_json('graphify-out/.graphify_ast.json')
semantic = read_json('graphify-out/.graphify_semantic_chunk1.json')

nodes = ast.get('nodes', []) + semantic.get('nodes', [])
edges = ast.get('edges', []) + semantic.get('edges', [])

result = {
    'nodes': nodes,
    'edges': edges,
    'input_tokens': semantic.get('input_tokens', 0),
    'output_tokens': semantic.get('output_tokens', 0),
}
Path('graphify-out/.graphify_extract.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(f'Merged: {len(nodes)} nodes, {len(edges)} edges')
