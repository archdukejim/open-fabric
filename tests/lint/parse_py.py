"""Parse every Python file of the product with the interpreter this runs on (the lint suite runs it on the oldest
supported Python, 3.10 for Ubuntu 22.04: decision 2.1.1.43), so syntax only newer Pythons accept cannot ship. ruff
cannot check this: it parses with the newest grammar whatever its target-version.
    python3 tests/lint/parse_py.py <dir> ...
"""
import ast
import pathlib
import sys

bad = 0
for root in sys.argv[1:]:
    for path in sorted(pathlib.Path(root).rglob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError as e:
            bad += 1
            print(f"{path}:{e.lineno}: {e.msg}")
print(f"Python {sys.version.split()[0]}: {bad} file(s) it cannot parse")
sys.exit(1 if bad else 0)
