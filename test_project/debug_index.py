"""Debug indexing to see what's happening."""

import sys
import ast
sys.path.insert(0, 'C:/Users/santa/Desktop/TheAuditor')

from pathlib import Path
from theauditor.indexer.extractors.python import PythonExtractor
from theauditor.ast_parser import ASTParser

# Read the test file
test_file = Path('test_cfg.py')
content = test_file.read_text()

# Parse with AST
ast_parser = ASTParser()
tree = ast_parser.parse_file(test_file)

print(f"Parsed AST: {tree is not None}")
print(f"Tree type: {type(tree)}")
if tree:
    print(f"Tree keys: {tree.keys() if isinstance(tree, dict) else 'not a dict'}")
    if isinstance(tree, dict) and 'tree' in tree:
        print(f"Tree.tree type: {type(tree['tree'])}")

# Create extractor
extractor = PythonExtractor(Path('.'), ast_parser)

# Extract data
file_info = {
    'path': 'test_cfg.py',
    'ext': '.py',
    'sha256': 'dummy',
    'bytes': len(content),
    'loc': len(content.splitlines())
}

result = extractor.extract(file_info, content, tree)

print(f"\nExtracted data keys: {result.keys()}")
print(f"CFG data: {len(result.get('cfg', []))} functions")

if result.get('cfg'):
    for cfg in result['cfg']:
        print(f"\nFunction: {cfg['function_name']}")
        print(f"  Blocks: {len(cfg['blocks'])}")
        print(f"  Edges: {len(cfg['edges'])}")
        for block in cfg['blocks'][:3]:  # Show first 3 blocks
            print(f"    - {block['type']} (id={block['id']}, lines {block['start_line']}-{block['end_line']})")