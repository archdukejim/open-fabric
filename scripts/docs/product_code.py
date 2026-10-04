"""The product code the docs suite inspects: every tracked (or new, not
ignored) file under fabricctl/, src/webui/ and packaging/, and every function
in it — Python top-level functions and class methods (nested helpers are
documented by the function that holds them) and shell functions — with
its structured docstring parsed.

Structured docstring (Python: the docstring; shell: the comment block right
above `name() {`), five sections, each a label at the start of a line and
text that may continue on the following, indented lines:

    Purpose: what it is for
    Inputs:  each argument: type, constraints ("none" if it takes none)
    Returns: the result on success
    Fails:   each way it fails and what the caller sees ("never" + why)
    Feeds:   which functions use the result ("—" if none)
    Notes:   optional — background worth keeping (why it works this way)
"""
import ast
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRODUCT = ("src", "packaging", "scripts/install-from-checkout.sh")
SECTIONS = ("Purpose", "Inputs", "Returns", "Fails", "Feeds")
OPTIONAL = ("Notes",)                      # background worth keeping; shown, not required
_LABEL = re.compile(r"^\s*(?:#\s*)?(" + "|".join(SECTIONS + OPTIONAL) + r"):\s?(.*)$")
_SHELL_FN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{")


def tracked_files(*paths):
    """Purpose: the repository's files as git sees them (tracked, plus new
             files that are not ignored), deleted-but-unstaged ones skipped.
    Inputs:  paths — folders or files to limit to (none: the whole repository).
    Returns: sorted repository-relative paths (str).
    Fails:   subprocess.CalledProcessError if git fails (not a checkout).
    Feeds:   product_files, review_ledger, check_consistency."""
    out = subprocess.run(["git", "-C", REPO, "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                          "--", *paths], capture_output=True, text=True, check=True).stdout
    return sorted({p for p in out.split("\0") if p and os.path.exists(os.path.join(REPO, p))})


def product_files():
    """Purpose: the product's source files (Python and shell) to document.
    Inputs:  none.
    Returns: [(path, kind)] with kind "py" or "sh"; shell = *.sh plus
             extension-less scripts whose first line is a shell shebang.
    Fails:   as tracked_files.
    Feeds:   functions."""
    out = []
    for p in tracked_files(*PRODUCT):
        if p.endswith(".py"):
            out.append((p, "py"))
        elif p.endswith(".sh"):
            out.append((p, "sh"))
        elif "." not in os.path.basename(p):
            with open(os.path.join(REPO, p), errors="replace") as f:
                if re.match(r"#!\s*/bin/(ba)?sh", f.readline()):
                    out.append((p, "sh"))
    return out


def parse_sections(text):
    """Purpose: split a structured docstring into its five sections.
    Inputs:  text — a docstring or a shell comment block (str or None).
    Returns: {section: text} for the sections present (continuation lines
             joined with spaces); {} if text is empty.
    Fails:   never (unknown lines before the first label are ignored).
    Feeds:   functions, check_docstrings, gen_lib_doc."""
    found, current = {}, None
    for line in (text or "").splitlines():
        m = _LABEL.match(line)
        if m:
            current = m.group(1)
            found[current] = m.group(2).strip()
        elif current:
            extra = re.sub(r"^\s*#?\s*", "", line).strip()
            if extra:
                found[current] = (found[current] + " " + extra).strip()
    return found


def _python_functions(path):
    tree = ast.parse(open(os.path.join(REPO, path), encoding="utf-8").read(), filename=path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node, None
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{sub.name}", sub, node.name


def _signature(node):
    return "(" + ast.unparse(node.args) + ")"


def _shell_functions(path):
    lines = open(os.path.join(REPO, path), encoding="utf-8", errors="replace").read().splitlines()
    for i, line in enumerate(lines):
        m = _SHELL_FN.match(line)
        if not m:
            continue
        block, j = [], i - 1
        while j >= 0 and lines[j].lstrip().startswith("#"):
            block.insert(0, lines[j])
            j -= 1
        yield m.group(1), i + 1, "\n".join(block)


def functions():
    """Purpose: every documented unit of the product code.
    Inputs:  none.
    Returns: [{path, kind, name, qualname, signature, line, doc, sections,
             node}] — node is the ast node (Python) or None (shell).
    Fails:   SyntaxError if a Python file does not parse.
    Feeds:   check_docstrings, gen_lib_doc, call_graph."""
    out = []
    for path, kind in product_files():
        if kind == "py":
            for qual, node, cls in _python_functions(path):
                doc = ast.get_docstring(node) or ""
                out.append({"path": path, "kind": kind, "name": node.name, "qualname": qual, "class": cls,
                            "signature": _signature(node), "line": node.lineno, "doc": doc,
                            "sections": parse_sections(doc), "node": node})
        else:
            for name, line, block in _shell_functions(path):
                out.append({"path": path, "kind": kind, "name": name, "qualname": name, "class": None,
                            "signature": "()", "line": line, "doc": block,
                            "sections": parse_sections(block), "node": None})
    return out
