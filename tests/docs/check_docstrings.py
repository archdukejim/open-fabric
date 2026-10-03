#!/usr/bin/env python3
"""Every product function has a structured docstring: Purpose, Inputs,
Returns, Fails and Feeds, none empty or a placeholder.

    python3 tests/docs/check_docstrings.py            report, exit 1 if any is missing
    python3 tests/docs/check_docstrings.py --summary  counts per folder only
"""
import collections
import re
import sys

from product_code import SECTIONS, functions

PLACEHOLDER = re.compile(r"^(todo|tbd|fixme|\.\.\.|xxx|\?+)$", re.I)


def problems(fn):
    """Purpose: what is wrong with one function's structured docstring.
    Inputs:  fn — one entry of product_code.functions().
    Returns: list of problems (str); empty when the docstring is complete.
    Fails:   never.
    Feeds:   main."""
    missing = [s for s in SECTIONS if not fn["sections"].get(s)]
    placeholders = [s for s in SECTIONS if PLACEHOLDER.match(fn["sections"].get(s, "x"))]
    out = []
    if missing:
        out.append("missing " + ", ".join(missing))
    if placeholders:
        out.append("placeholder in " + ", ".join(placeholders))
    return out


def main(argv):
    """Purpose: run the check over the whole product and report.
    Inputs:  argv — ["--summary"] for counts only.
    Returns: exit status: 0 all documented, 1 otherwise.
    Fails:   SyntaxError from product_code if a file does not parse.
    Feeds:   tests/docs/run.py."""
    fns = functions()
    per_folder = collections.defaultdict(lambda: [0, 0])
    bad = []
    for fn in fns:
        folder = fn["path"].rsplit("/", 1)[0]
        per_folder[folder][0] += 1
        issue = problems(fn)
        if issue:
            per_folder[folder][1] += 1
            bad.append(f"{fn['path']}:{fn['line']} {fn['qualname']}: {'; '.join(issue)}")
    if "--summary" not in argv:
        for line in bad:
            print(line)
    for folder, (total, missing) in sorted(per_folder.items()):
        if missing or "--summary" in argv:
            print(f"  {folder:<52} {total - missing:>4}/{total} documented")
    print(f"{len(fns) - len(bad)}/{len(fns)} functions have a complete structured docstring")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
