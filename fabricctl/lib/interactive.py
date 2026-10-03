#!/usr/bin/env python3
"""`fabricctl --interactive | --print | --apply` (the vars editor, listing the settings, applying them): the code is
in fabriclib/menu/. Kept as an entry point because system/apply_changes (the web UI's Apply) runs
`interactive.py --apply` as its own process under the vars lock."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from fabriclib.menu.apply_and_report import apply_and_report  # noqa: E402
from fabriclib.menu.print_vars import print_vars  # noqa: E402
from fabriclib.menu.run_vars_menu import run_vars_menu  # noqa: E402

MODES = {"--print": print_vars, "--interactive": run_vars_menu, "--apply": apply_and_report}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        print("Usage: interactive.py [--print | --interactive | --apply]")
        sys.exit(1)
    MODES[sys.argv[1]]()
