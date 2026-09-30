#!/usr/bin/env python3
"""Prove that changes since a git revision touched only documentation:
Python files must have the same syntax tree once docstrings are removed,
shell files the same lines once comment-only lines are removed. For bulk
documentation passes, so they cannot change behaviour by accident.

    python3 tests/docs/docstring_only_diff.py <git-rev> [path ...]
        exit 0: only docstrings/comments changed; 1: code changed (files listed)
"""
import ast
import os
import subprocess
import sys

from product_code import REPO


def _strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def code_of(text, kind):
    """Purpose: a file's content with its documentation removed, comparable across edits.
    Inputs:  text — the file's content; kind — "py" or "sh".
    Returns: Python: the AST dump without docstrings; shell: the lines that
             are not comments or blank, stripped.
    Fails:   SyntaxError if Python text does not parse.
    Feeds:   changed_code."""
    if kind == "py":
        return _strip_docstrings(ast.parse(text))
    return "\n".join(line.strip() for line in text.splitlines()
                     if line.strip() and not line.lstrip().startswith("#"))


def changed_code(rev, paths):
    """Purpose: which files changed code (not just docs) since `rev`.
    Inputs:  rev — a git revision; paths — limit to these (none: all changed files).
    Returns: sorted paths whose code differs, plus new/deleted .py/.sh files.
    Fails:   subprocess.CalledProcessError for an unknown revision.
    Feeds:   main."""
    names = subprocess.run(["git", "-C", REPO, "diff", "--name-only", rev, "--", *paths],
                           capture_output=True, text=True, check=True).stdout.split()
    out = []
    for path in names:
        kind = "py" if path.endswith(".py") else "sh" if path.endswith(".sh") else None
        if not kind:
            continue
        old = subprocess.run(["git", "-C", REPO, "show", f"{rev}:{path}"], capture_output=True, encoding="utf-8")
        new_path = os.path.join(REPO, path)
        if old.returncode != 0 or not os.path.exists(new_path):
            out.append(path)
            continue
        if code_of(old.stdout, kind) != code_of(open(new_path, encoding="utf-8").read(), kind):
            out.append(path)
    return sorted(out)


def main(argv):
    """Purpose: report files whose code changed since a revision.
    Inputs:  argv — [rev, paths…].
    Returns: exit status: 0 documentation-only, 1 code changed, 2 usage.
    Fails:   as changed_code.
    Feeds:   — (run by hand after a documentation pass)."""
    if not argv:
        print(__doc__)
        return 2
    changed = changed_code(argv[0], argv[1:])
    for p in changed:
        print(f"code changed: {p}")
    print("documentation-only changes" if not changed else f"{len(changed)} file(s) with code changes")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
