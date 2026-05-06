"""Graphify build step: builds graph, analyzes, generates GRAPH_REPORT.md"""
import json
from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.analyze import god_nodes, surprising_connections
from graphify.report import generate
from pathlib import Path
from networkx.readwrite import json_graph

def read_json(path):
    for enc in ('utf-8-sig', 'utf-16', 'utf-8'):
        try:
            return json.loads(Path(path).read_bytes().decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise RuntimeError(f'Cannot decode {path}')

detection_result = read_json('graphify-out/.graphify_detect.json')
extraction = read_json('graphify-out/.graphify_extract.json')
G = build_from_json(extraction)
communities = cluster(G)
gods = god_nodes(G)
surprises = surprising_connections(G, communities)
graph_data = json_graph.node_link_data(G)
Path('graphify-out/graph.json').write_text(json.dumps(graph_data, indent=2), encoding='utf-8')
analysis = {
    'communities': {str(k): v for k, v in communities.items()},
    'cohesion': {},
    'god_nodes': gods,
    'surprises': surprises,
}
Path('graphify-out/.graphify_analysis.json').write_text(json.dumps(analysis, indent=2), encoding='utf-8')
print(f'Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities')
token_cost = {
    'input_tokens': extraction.get('input_tokens', 0),
    'output_tokens': extraction.get('output_tokens', 0),
}
report = generate(G, communities, {}, {}, gods, surprises, detection_result, token_cost, 'D:/01_gitrepo/openclaw_github')
Path('graphify-out/GRAPH_REPORT.md').write_text(report, encoding='utf-8')
print('GRAPH_REPORT.md written')
