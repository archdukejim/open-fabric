#!/usr/bin/env python3
"""fabricctl setup — install or re-converge fabric on this host.

  sudo fabricctl setup                      interactive
  sudo fabricctl setup --file vars.yaml     answers from a file (asks only for what is missing)
  sudo fabricctl setup --file vars.yaml --non-interactive --yes   fully unattended
  sudo fabricctl setup --step certs         run one step (see --list)
  sudo fabricctl doctor                     run only the end-to-end checks
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fabriclib.common.console import BOLD, NC, err, heading, ok  # noqa: E402
from fabriclib.setup.choose_plan import choose_plan  # noqa: E402
from fabriclib.setup.collect_vars import collect_vars  # noqa: E402
from fabriclib.setup.context import SetupContext  # noqa: E402
from fabriclib.setup.errors import SetupError  # noqa: E402
from fabriclib.setup.steps import STEPS  # noqa: E402
from fabriclib.setup.verify_install import run as verify  # noqa: E402

NEEDS_INPUT = {"preflight", "host", "docker", "deploy"}   # before the rendered vars exist


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fabricctl setup", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="vars file (fabric.yaml / custom-vars.yaml)")
    ap.add_argument("--deploy-base", default="/opt", help="install root (default /opt)")
    ap.add_argument("--offline", action="store_true", help="never download; images and packages must be present")
    ap.add_argument("--non-interactive", action="store_true", help="never prompt; fail on missing values")
    ap.add_argument("--yes", "-y", action="store_true", help="accept the plan without the Proceed prompt")
    ap.add_argument("--step", action="append", help="run only this step (repeatable)")
    ap.add_argument("--list", action="store_true", help="list the steps and exit")
    ap.add_argument("--doctor", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.list:
        for name, _, desc in STEPS:
            print(f"  {name:10} {desc}")
        return 0

    ctx = SetupContext(deploy_base=args.deploy_base, user_vars_file=args.file, offline=args.offline,
                       non_interactive=args.non_interactive, assume_yes=args.yes)
    try:
        if args.doctor:
            ctx.load_state()
            heading("fabric doctor")
            verify(ctx)
            return 0

        selected = args.step or [name for name, _, _ in STEPS]
        unknown = set(selected) - {n for n, _, _ in STEPS}
        if unknown:
            raise SetupError(f"unknown step(s): {', '.join(sorted(unknown))} (see --list)")
        if any(s in NEEDS_INPUT for s in selected):
            heading("fabric setup")
            collect_vars(ctx)
            if args.step is None:
                choose_plan(ctx)
        else:
            ctx.load_state()

        start = time.time()
        for name, step, desc in STEPS:
            if name not in selected:
                continue
            heading(f"[{name}] {desc}")
            step(ctx)
            if name == "deploy":
                ctx.load_state()
        heading(f"{BOLD}fabric is ready{NC} ({time.time() - start:.0f}s)")
        if ctx.vars.get("install_webui"):
            ok(f"web UI: https://{ctx.vars.get('hostname_mgr')}  (login kit: ~/fabric-admin/README.txt)")
        ok("checks any time: sudo fabricctl doctor")
        return 0
    except SetupError as e:
        err(str(e))
        return 1
    except KeyboardInterrupt:
        err("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
