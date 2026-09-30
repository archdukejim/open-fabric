#!/usr/bin/env python3
"""Cross-checks between the docs and the code — the facts a reader relies
on that drift silently otherwise:

  readmes      every folder has a README.md naming each of its files and subfolders
  vars         every setting in vars.yaml.j2 is in docs/vars.md, and vars.md names no setting that is gone
  cli          every `fabricctl` command and subcommand is in the docs
  api          fabric-agent's routes = the permission table = the list in docs/webui.md
  permissions  every permission is explained in docs/webui.md
  suites       every test suite in tests/run-all.sh has a folder or file and is in tests/README.md
  steps        every setup step is in docs/install.md
  links        every relative Markdown link points at something that exists

    python3 tests/docs/check_consistency.py [check ...]     exit 1 if any check finds a problem
"""
import ast
import os
import re
import sys

from product_code import REPO, tracked_files

SKIP_README = {"__init__.py", "README.md"}     # a README need not list itself or package markers


def _read(path):
    return open(os.path.join(REPO, path), encoding="utf-8").read()


def check_readmes():
    """Purpose: each folder's README.md names every file and subfolder in it.
    Inputs:  none (the repository's files; hidden folders, the repository
             root and generated docs/lib-doc/ are exempt).
    Returns: problems (str), one per missing README or unlisted entry.
    Fails:   never (unreadable READMEs count as missing).
    Feeds:   main."""
    folders = {}
    for p in tracked_files():
        parts = p.split("/")
        if len(parts) < 2 or any(x.startswith(".") for x in parts[:-1]) or p.startswith("docs/lib-doc/"):
            continue
        folder = "/".join(parts[:-1])
        folders.setdefault(folder, set()).add(parts[-1])
        for i in range(1, len(parts) - 1):                    # the subfolder, in its parent's README
            parent = "/".join(parts[:i])
            if not parent.startswith("docs/lib-doc"):
                folders.setdefault(parent, set()).add(parts[i] + "/")
    out = []
    for folder, entries in sorted(folders.items()):
        readme = os.path.join(REPO, folder, "README.md")
        if not os.path.exists(readme):
            out.append(f"{folder}/: no README.md")
            continue
        text = open(readme, encoding="utf-8").read()
        for name in sorted(entries - SKIP_README):
            bare = name.rstrip("/")
            if not re.search(r"[`\[(/ ]" + re.escape(bare) + r"(/|`|\]|\)|\b)", text):
                out.append(f"{folder}/README.md does not mention {name}")
    return out


def _vars_template_keys():
    keys = set()
    for line in _read("fabricctl/jinja/vars.yaml.j2").splitlines():
        m = re.match(r"^([a-z][a-z0-9_]*):", line)
        if m:
            keys.add(m.group(1))
    return keys


def check_vars():
    """Purpose: vars.yaml.j2 and docs/vars.md name the same settings.
    Inputs:  none.
    Returns: problems: settings without docs, and documented settings
             (### `x` headings, first table cells) that do not exist.
    Fails:   OSError if either file is missing.
    Feeds:   main."""
    keys = _vars_template_keys()
    doc = _read("docs/vars.md")
    documented = set(re.findall(r"^###\s+`([a-z][a-z0-9_]*)`", doc, re.M))
    documented |= set(re.findall(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|", doc, re.M))
    # a setting read only where it is used (`x | default(...)` in a template, v.get("x") in code) is real too
    code = "\n".join(_read(p) for p in tracked_files("fabricctl", "webui")
                     if p.endswith((".j2", ".py", ".sh")) and not p.endswith("vars.yaml.j2"))
    used = {k for k in documented - keys
            if re.search(rf"(\{{\{{-?\s*{k}\b|\b{k}\s*\||get\(\s*['\"]{k}['\"]|\[['\"]{k}['\"]\])", code)}
    out = [f"vars.yaml.j2 setting `{k}` is not in docs/vars.md" for k in sorted(keys) if f"`{k}`" not in doc]
    out += [f"docs/vars.md documents `{k}`, which nothing reads" for k in sorted(documented - keys - used)]
    return out


def _cli_commands():
    """(command, subcommand or None) pairs from cli.py's docstring, manage.sh's
    router and every `fabricctl <cmd> <sub>` in a USAGE string."""
    cmds = set()
    doc = ast.get_docstring(ast.parse(_read("fabricctl/lib/fabriclib/cli.py"))) or ""
    for m in re.finditer(r"^\s+fabricctl ([a-z][a-z-]*)(?: ([a-z|-]+))?", doc, re.M):
        subs = [s for s in (m.group(2) or "").split("|") if s and not s.startswith("-")]
        cmds.add((m.group(1), None))
        cmds.update((m.group(1), s) for s in subs)
    for path in tracked_files("fabricctl/lib/fabriclib"):
        if path.endswith(".py"):
            for usage in re.findall(r'USAGE = """(.*?)"""', _read(path), re.S):
                for m in re.finditer(r"fabricctl ([a-z][a-z-]*) ([a-z][a-z-]*)", usage):
                    cmds.add((m.group(1), m.group(2)))
    return cmds


def check_cli():
    """Purpose: every fabricctl command and subcommand appears in the docs.
    Inputs:  none (cli.py, the USAGE strings; docs/*.md, README.md).
    Returns: problems, one per command not mentioned as `fabricctl <cmd> [<sub>]`.
    Fails:   OSError if cli.py is missing.
    Feeds:   main."""
    docs = "\n".join(_read(p) for p in tracked_files("docs", "README.md") if p.endswith(".md")
                     and not p.startswith("docs/lib-doc/"))
    out = []
    for cmd, sub in sorted(_cli_commands(), key=lambda c: (c[0], c[1] or "")):
        pattern = rf"fabricctl {re.escape(cmd)}" + (rf"(?: [^\n`]*?)?[ |]{re.escape(sub)}\b" if sub else r"\b")
        if not re.search(pattern, docs):
            out.append(f"`fabricctl {cmd}{' ' + sub if sub else ''}` is not in the docs")
    return out


def _routes_in_table():
    src = ast.parse(_read("fabricctl/lib/fabriclib/rbac/required_permission.py"))
    routes = set()
    for node in src.body:
        if isinstance(node, ast.Assign) and node.targets[0].id in ("GET", "POST"):
            for key in ast.literal_eval(node.value):
                routes.add((node.targets[0].id, "/".join(key)))
    return routes


def check_api():
    """Purpose: fabric-agent's permission table and docs/webui.md list the same routes.
    Inputs:  none.
    Returns: problems: routes the table has but the docs do not, and routes
             the docs list that the table does not (so they would be refused).
    Fails:   OSError if a file is missing.
    Feeds:   main."""
    table = {r for _, r in _routes_in_table()}
    doc = _read("docs/webui.md")
    listed = set()
    for m in re.finditer(r"`(/v1/[^`]+)`", doc):
        path = m.group(1)[len("/v1/"):]
        brace = re.match(r"(.*)\{([^}]*)\}(.*)", path)                     # /v1/x/{a,b} -> x/a, x/b
        variants = [brace.group(1) + v + brace.group(3) for v in brace.group(2).split(",")] if brace else [path]
        for v in variants:
            listed.add(re.sub(r"<[^>]+>", "*", v))
    out = [f"agent route /v1/{r} is not in docs/webui.md" for r in sorted(table - listed)]
    out += [f"docs/webui.md lists /v1/{r}, which fabric-agent refuses (not in the permission table)"
            for r in sorted(listed - table)]
    return out


def check_permissions():
    """Purpose: every permission in rbac/permissions.py is explained in docs/webui.md.
    Inputs:  none.
    Returns: problems, one per permission not mentioned as `area:action`.
    Fails:   OSError / SyntaxError if permissions.py is unreadable.
    Feeds:   main."""
    src = ast.parse(_read("fabricctl/lib/fabriclib/rbac/permissions.py"))
    perms = next(ast.literal_eval(n.value) for n in src.body
                 if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PERMISSIONS")
    doc = _read("docs/webui.md")
    return [f"permission `{p}` is not in docs/webui.md" for p in sorted(perms) if f"`{p}`" not in doc]


def check_suites():
    """Purpose: every suite run-all.sh knows exists and is described in tests/README.md.
    Inputs:  none.
    Returns: problems: suites with no tests/<suite> folder or script, or not in tests/README.md.
    Fails:   OSError if run-all.sh is missing.
    Feeds:   main."""
    suites = re.findall(r"^\s+([a-z0-9]+)\)\s+run ", _read("tests/run-all.sh"), re.M)
    readme = _read("tests/README.md") if os.path.exists(os.path.join(REPO, "tests/README.md")) else ""
    out = []
    for s in suites:
        if not any(os.path.exists(os.path.join(REPO, "tests", c)) for c in (s, f"{s}.py", f"{s}_test.py", f"{s}_check.sh")):
            out.append(f"suite {s}: no tests/{s} folder or script")
        if f"`{s}`" not in readme:
            out.append(f"suite {s} is not in tests/README.md")
    return out


def check_steps():
    """Purpose: every setup step (setup/steps.py) is described in docs/install.md.
    Inputs:  none.
    Returns: problems, one per step name not mentioned as `name`.
    Fails:   OSError if a file is missing.
    Feeds:   main."""
    steps = re.findall(r'^\s+\("([a-z]+)", ', _read("fabricctl/lib/fabriclib/setup/steps.py"), re.M)
    doc = _read("docs/install.md")
    return [f"setup step `{s}` is not in docs/install.md" for s in steps if f"`{s}`" not in doc]


def check_links():
    """Purpose: relative links in Markdown files resolve.
    Inputs:  none (every tracked .md; http(s), mailto and pure #anchors are skipped).
    Returns: problems, one per broken link (file and target).
    Fails:   never.
    Feeds:   main."""
    out = []
    for path in tracked_files():
        if not path.endswith(".md"):
            continue
        for target in re.findall(r"\]\(([^)\s]+)\)", _read(path)):
            if re.match(r"(https?:|mailto:|#)", target):
                continue
            rel = target.split("#", 1)[0]
            if rel and not os.path.exists(os.path.normpath(os.path.join(REPO, os.path.dirname(path), rel))):
                out.append(f"{path}: broken link {target}")
    return out


CHECKS = {"readmes": check_readmes, "vars": check_vars, "cli": check_cli, "api": check_api,
          "permissions": check_permissions, "suites": check_suites, "steps": check_steps, "links": check_links}


def main(argv):
    """Purpose: run the checks and report.
    Inputs:  argv — names of checks to run (none: all).
    Returns: exit status: 0 all clean, 1 any problem, 2 unknown check name.
    Fails:   as the individual checks.
    Feeds:   tests/docs/run.py."""
    names = argv or list(CHECKS)
    unknown = [n for n in names if n not in CHECKS]
    if unknown:
        print("unknown check: " + ", ".join(unknown))
        return 2
    bad = 0
    for name in names:
        problems = CHECKS[name]()
        bad += len(problems)
        for p in problems:
            print(f"[{name}] {p}")
        print(f"{'FAIL' if problems else 'PASS'} {name}: {len(problems)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
