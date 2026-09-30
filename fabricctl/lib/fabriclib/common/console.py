import os
import sys

_TTY = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
BOLD, BLUE, GREEN, YELLOW, RED, NC = (("\033[1m", "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[0m")
                                      if _TTY else ("",) * 6)


def heading(text):
    print(f"\n{BOLD}{text}{NC}", flush=True)


def info(text):
    print(f"  {BLUE}·{NC} {text}", flush=True)


def ok(text):
    print(f"  {GREEN}✓{NC} {text}", flush=True)


def warn(text):
    print(f"  {YELLOW}!{NC} {text}", flush=True)


def err(text):
    print(f"  {RED}✗{NC} {text}", file=sys.stderr, flush=True)
