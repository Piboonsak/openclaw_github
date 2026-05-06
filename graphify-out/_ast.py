"""Graphify AST extraction for openclaw_github - scoped to src/ only to avoid node_modules."""
from graphify.extract import collect_files, extract
from pathlib import Path
import json

if __name__ == '__main__':
    # Scope to src/ only to avoid node_modules and vendor code
    root = Path('D:/01_gitrepo/openclaw_github/src')
    files = collect_files(root)
    print(f'Code files found: {len(files)}')
    if files:
        result = extract(files)
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f'AST nodes: {len(result.get("nodes", []))}')
        print(f'AST edges: {len(result.get("edges", []))}')
    else:
        Path('graphify-out/.graphify_ast.json').write_text(json.dumps({'nodes': [], 'edges': []}, indent=2), encoding='utf-8')
        print('No code files - AST empty')
