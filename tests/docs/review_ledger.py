#!/usr/bin/env python3
"""The review ledger (docs/maintenance/review-ledger.tsv): every file in
the repository, when it was last reviewed against the code and docs, and
the git blob hash of the content that was reviewed.

    python3 tests/docs/review_ledger.py                  report; exit 1 if a file was never reviewed
    python3 tests/docs/review_ledger.py --changed        list files changed since their review
    python3 tests/docs/review_ledger.py --mark FILE...   record FILEs as reviewed now, as they are
    python3 tests/docs/review_ledger.py --prune          drop entries of files that no longer exist

A file missing from the ledger fails the docs suite: nothing ships
uninspected. A file changed since its review is reported, not failed —
re-mark it once the change has been reviewed.
"""
import datetime
import os
import subprocess
import sys

from product_code import REPO, tracked_files

LEDGER_PATH = "docs/maintenance/review-ledger.tsv"
LEDGER = os.path.join(REPO, *LEDGER_PATH.split("/"))
HEAD = "# path\tblob (git hash-object of the reviewed content)\treviewed (UTC date)\tnote\n"


def blob(path):
    """Purpose: the git blob hash of a file's current content.
    Inputs:  path — repository-relative.
    Returns: 40-character hex hash (what `git hash-object` prints).
    Fails:   subprocess.CalledProcessError if the file cannot be read.
    Feeds:   check, mark."""
    return subprocess.run(["git", "-C", REPO, "hash-object", "--", path],
                          capture_output=True, text=True, check=True).stdout.strip()


def load():
    """Purpose: the ledger's entries.
    Inputs:  none (reads docs/maintenance/review-ledger.tsv; absent = empty).
    Returns: {path: (blob, date, note)}.
    Fails:   ValueError on a malformed line (fewer than 3 tab-separated fields).
    Feeds:   check, mark, save."""
    out = {}
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                raise ValueError(f"review-ledger.tsv: malformed line: {line!r}")
            out[parts[0]] = (parts[1], parts[2], parts[3] if len(parts) > 3 else "")
    return out


def save(entries):
    """Purpose: write the ledger, sorted by path.
    Inputs:  entries — {path: (blob, date, note)}.
    Returns: None.
    Fails:   OSError if the file cannot be written.
    Feeds:   — (the ledger file)."""
    with open(LEDGER, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEAD)
        for path in sorted(entries):
            b, d, note = entries[path]
            f.write(f"{path}\t{b}\t{d}\t{note}\n")


def check(entries):
    """Purpose: which files were never reviewed, and which changed since.
    Inputs:  entries — load().
    Returns: (never reviewed, changed since review) — two sorted path lists.
    Fails:   as blob.
    Feeds:   main."""
    never, changed = [], []
    for path in tracked_files():
        if path == LEDGER_PATH:                  # the ledger cannot review itself
            continue
        if path not in entries:
            never.append(path)
        elif entries[path][0] != blob(path):
            changed.append(path)
    return never, changed


def main(argv):
    """Purpose: report on, update or prune the ledger.
    Inputs:  argv — [], ["--changed"], ["--mark", files…] or ["--prune"].
    Returns: exit status: 0 fine, 1 files never reviewed (report mode) or a
             --mark of a file that does not exist.
    Fails:   as check/save.
    Feeds:   tests/docs/run.py."""
    entries = load()
    if argv[:1] == ["--mark"]:
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        for path in argv[1:]:
            path = os.path.relpath(os.path.abspath(path), REPO).replace(os.sep, "/")
            if not os.path.isfile(os.path.join(REPO, path)):
                print(f"no such file: {path}")
                return 1
            entries[path] = (blob(path), today, entries.get(path, ("", "", ""))[2])
        save(entries)
        print(f"marked {len(argv) - 1} file(s) reviewed")
        return 0
    if argv[:1] == ["--prune"]:
        live = set(tracked_files())
        gone = sorted(set(entries) - live)
        save({p: e for p, e in entries.items() if p in live})
        print(f"pruned {len(gone)} entr{'y' if len(gone) == 1 else 'ies'}: " + ", ".join(gone))
        return 0
    never, changed = check(entries)
    if "--changed" in argv:
        for p in changed:
            print(p)
        return 0
    for p in never:
        print(f"never reviewed: {p}")
    total = len([p for p in tracked_files() if p != LEDGER_PATH])
    print(f"{total - len(never)}/{total} files reviewed; {len(changed)} changed since their review")
    return 1 if never else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
