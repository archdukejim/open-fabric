"""Who calls whom in the product's Python code, statically: calls by name
within a file, calls of names imported with `from fabriclib... import f`
(or `from webui import m` / `import m as x` then `x.f`), and `self.f()`
within a class. Dynamic calls (a function taken from a table, like setup's
STEPS) are not seen: the Feeds section of each docstring covers those.
"""
import ast
import os

from product_code import REPO


def _module_of(path):
    """src/fabriclib/dns/add_record.py -> fabriclib.dns.add_record;
    src/webui/views.py -> webui.views; other files: their path without .py."""
    p = path[:-3]
    if p.startswith("src/"):
        p = p[len("src/"):]
    elif p.startswith("src/containers/freeradius/"):
        p = p[len("src/containers/freeradius/"):]
    return p.replace("/", ".").removesuffix(".__init__")


def call_graph(fns):
    """Purpose: the static callers of every Python product function.
    Inputs:  fns — product_code.functions().
    Returns: {(path, qualname): sorted ["module.caller", …]} for Python
             functions; a function nobody calls statically maps to [].
    Fails:   SyntaxError if a file does not parse (functions() fails first).
    Feeds:   gen_lib_doc."""
    by_module = {}                     # module -> {top-level name: (path, qualname)}
    for fn in fns:
        if fn["kind"] == "py" and fn["class"] is None:
            by_module.setdefault(_module_of(fn["path"]), {})[fn["name"]] = (fn["path"], fn["qualname"])
    callers = {(fn["path"], fn["qualname"]): set() for fn in fns if fn["kind"] == "py"}
    for path in sorted({fn["path"] for fn in fns if fn["kind"] == "py"}):
        module = _module_of(path)
        tree = ast.parse(open(os.path.join(REPO, path), encoding="utf-8").read())
        names = dict((n, (module, n)) for n in by_module.get(module, {}))   # local name -> (module, name)
        aliases = {}                                                          # local alias -> module
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    target = f"{node.module}.{a.name}"
                    if target in by_module:                                   # from webui import views
                        aliases[a.asname or a.name] = target
                    elif a.name in by_module.get(node.module, {}):            # from x.y import f
                        names[a.asname or a.name] = (node.module, a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in by_module:
                        aliases[a.asname or a.name.split(".")[0]] = a.name
        scopes = [(n.name, None, n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        scopes += [(f"{c.name}.{m.name}", c.name, m) for c in tree.body if isinstance(c, ast.ClassDef)
                   for m in c.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
        scopes.append(("<module>", None, tree))
        for caller, cls, scope in scopes:
            nodes = ast.walk(scope) if caller != "<module>" else (
                x for top in tree.body if not isinstance(top, (ast.FunctionDef, ast.ClassDef))
                for x in ast.walk(top))
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue
                f, target = node.func, None
                if isinstance(f, ast.Name) and f.id in names:
                    target = names[f.id]
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    if f.value.id in aliases and f.attr in by_module.get(aliases[f.value.id], {}):
                        target = (aliases[f.value.id], f.attr)
                    elif f.value.id == "self" and cls:
                        key = (path, f"{cls}.{f.attr}")
                        if key in callers:
                            callers[key].add(f"{module}.{caller}")
                        continue
                if target:
                    key = by_module[target[0]][target[1]]
                    if key in callers and not (key == (path, caller)):
                        callers[key].add(f"{module}.{caller}")
    return {k: sorted(v) for k, v in callers.items()}
