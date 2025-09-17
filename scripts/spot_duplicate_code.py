import ast
import difflib
import hashlib
import os
import sys
from collections import defaultdict

TEST_DIRS = [
    'tests',
    'quickscale',
]

def find_py_files():
    py_files = []
    for test_dir in TEST_DIRS:
        if not os.path.isdir(test_dir):
            continue
        for root, _, files in os.walk(test_dir):
            for f in files:
                if f.endswith('.py'):
                    py_files.append(os.path.join(root, f))
    return py_files

def extract_test_functions(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except Exception:
        return []
    test_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            body_src = ast.get_source_segment(source, node)
            # Extract docstring if present
            docstring = ast.get_docstring(node)
            # Extract first N lines (excluding decorator and def line)
            if body_src:
                body_lines = body_src.splitlines()
                # Remove decorator lines and def line
                first_body_line = 0
                for idx, line in enumerate(body_lines):
                    if line.strip().startswith('def '):
                        first_body_line = idx + 1
                        break
                first_n_lines = '\n'.join(body_lines[first_body_line:first_body_line+5])
                last_n_lines = '\n'.join(body_lines[-5:])
                short_body = '\n'.join(body_lines[first_body_line:])
            else:
                first_n_lines = ''
                last_n_lines = ''
                short_body = ''
            test_funcs.append((node.name, body_src, docstring, first_n_lines, last_n_lines, short_body))
    return test_funcs



def main():

    enable_similarity = '--similarity' in sys.argv
    enable_first_lines = True
    enable_docstring = True
    enable_short_bodies = True

    name_map = defaultdict(list)
    body_hash_map = defaultdict(list)
    body_list = []  # (func_name, file_path, body_src)
    first_lines_map = defaultdict(list)
    docstring_map = defaultdict(list)
    short_body_map = defaultdict(list)

    py_files = find_py_files()
    for file_path in py_files:
        for tup in extract_test_functions(file_path):
            func_name, body_src, docstring, first_n_lines, last_n_lines, short_body = tup
            name_map[func_name].append(file_path)
            if body_src:
                body_hash = hashlib.md5(body_src.strip().encode('utf-8')).hexdigest()
                body_hash_map[body_hash].append((func_name, file_path))
                body_list.append((func_name, file_path, body_src.strip()))
            if enable_first_lines and first_n_lines.strip():
                first_lines_hash = hashlib.md5(first_n_lines.strip().encode('utf-8')).hexdigest()
                first_lines_map[first_lines_hash].append((func_name, file_path))
            if enable_docstring and docstring:
                docstring_hash = hashlib.md5(docstring.strip().encode('utf-8')).hexdigest()
                docstring_map[docstring_hash].append((func_name, file_path))
            if enable_short_bodies and short_body:
                # Only consider short bodies (<= 3 lines after def)
                lines = [line for line in short_body.splitlines() if line.strip() and not line.strip().startswith('"""')]
                if 0 < len(lines) <= 3:
                    short_body_hash = hashlib.md5(short_body.strip().encode('utf-8')).hexdigest()
                    short_body_map[short_body_hash].append((func_name, file_path))

    print('# TODO: Review and Fix Duplicated/Overlapping Tests')

    print('\n## Duplicate Test Function Names')
    for name, files in name_map.items():
        if len(files) > 1:
            file_list = ', '.join(files)
            print(f'- [ ] Duplicate function name `{name}` in: {file_list}')

    print('\n## Identical Test Function Bodies')
    for h, entries in body_hash_map.items():
        if len(entries) > 1:
            locations = ', '.join([f'`{func_name}` in {file_path}' for func_name, file_path in entries])
            print(f'- [ ] Identical body ({h}): {locations}')

    if enable_first_lines:
        print('\n## Same First 5 Lines of Test Body')
        for h, entries in first_lines_map.items():
            if len(entries) > 1:
                locations = ', '.join([f'`{func_name}` in {file_path}' for func_name, file_path in entries])
                print(f'- [ ] Same first 5 lines ({h}): {locations}')

    if enable_docstring:
        print('\n## Same Docstring in Test Functions')
        for h, entries in docstring_map.items():
            if len(entries) > 1:
                locations = ', '.join([f'`{func_name}` in {file_path}' for func_name, file_path in entries])
                print(f'- [ ] Same docstring ({h}): {locations}')

    if enable_short_bodies:
        print('\n## Short Test Functions with Identical Bodies (<=3 lines)')
        for h, entries in short_body_map.items():
            if len(entries) > 1:
                locations = ', '.join([f'`{func_name}` in {file_path}' for func_name, file_path in entries])
                print(f'- [ ] Short identical body ({h}): {locations}')

    if enable_similarity:
        print('\n[WARNING] Near-duplicate similarity check enabled. This may take several minutes on large codebases.')
        print('\n## Near-Duplicate Test Function Bodies (Similarity > 90%)')
        reported = set()
        for i in range(len(body_list)):
            name1, file1, body1 = body_list[i]
            for j in range(i+1, len(body_list)):
                name2, file2, body2 = body_list[j]
                if (file1, name1, file2, name2) in reported or (file2, name2, file1, name1) in reported:
                    continue
                # Skip if already identical (already reported)
                if hashlib.md5(body1.encode('utf-8')).hexdigest() == hashlib.md5(body2.encode('utf-8')).hexdigest():
                    continue
                sm = difflib.SequenceMatcher(None, body1, body2)
                ratio = sm.ratio()
                if ratio > 0.9:
                    print(f'- [ ] Near-duplicate ({ratio:.2%}): `{name1}` in {file1} <-> `{name2}` in {file2}')
                    reported.add((file1, name1, file2, name2))


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print("""
spot_duplicate_tests.py [OPTIONS]

Detect duplicate and near-duplicate test functions in your codebase.

By default, the following fast checks are always enabled:
  - Flag test functions with identical first 5 lines
  - Flag test functions with identical docstrings
  - Flag short test functions (<=3 lines) with identical bodies

Options:
  --similarity      Enable slow, full-body similarity check (>90%)
  -h, --help        Show this help message and exit
""")
        sys.exit(0)
    main()
