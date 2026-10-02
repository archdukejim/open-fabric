#!/usr/bin/env python3
"""fabricctl setup — install or re-converge fabric on this host.

  sudo fabricctl setup                      interactive
  sudo fabricctl setup --file vars.yaml     answers from a file (asks only for what is missing)
  sudo fabricctl setup --file vars.yaml --non-interactive --yes --approve all   fully unattended
  sudo fabricctl setup --step certs         run one step (see --list)
  sudo fabricctl doctor                     run only the end-to-end checks
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fabriclib.common.console import BOLD, NC, err, heading, ok  # noqa: E402
from fabriclib.consent.ask_consent import ask_consent  # noqa: E402
from fabriclib.consent.plan_host_changes import plan_host_changes  # noqa: E402
from fabriclib.consent.planned_vars import planned_vars  # noqa: E402
from fabriclib.setup.choose_plan import choose_plan  # noqa: E402
from fabriclib.setup.collect_vars import collect_vars  # noqa: E402
from fabriclib.setup.context import SetupContext  # noqa: E402
from fabriclib.setup.errors import SetupError  # noqa: E402
from fabriclib.setup.read_join_invitation import read_join_invitation  # noqa: E402
from fabriclib.setup.steps import STEPS  # noqa: E402
from fabriclib.setup.verify_install import run as verify  # noqa: E402

NEEDS_INPUT = {"preflight", "host", "docker", "join", "deploy"}   # before the rendered vars exist


def main(argv=None):
    """Purpose: `fabricctl setup` / `fabricctl doctor`: parse options, collect settings, show the plan and run
             the selected steps of STEPS in order.
    Inputs:  argv — option list (None: sys.argv[1:]): --file, --deploy-base (default /opt), --offline,
             --non-interactive, --yes/-y, --approve GROUPS / --decline GROUPS (host changes, repeatable),
             --step NAME (repeatable), --join [@FILE|-] (join an upstream fabric; read_join_invitation),
             --list, --doctor (hidden, used by doctor).
    Returns: exit status: 0 done (or --list printed), 1 a SetupError (message printed), 130 interrupted.
             A full run leaves the install converged; the steps before deploy (preflight, host, docker,
             deploy) collect vars first, and the plan is shown only when no --step is given. Before the first
             step every change outside fabric's own tree is asked about, by group (consent; --yes approves none).
    Fails:   SystemExit(2) from argparse on bad options; SystemExit("setup cancelled") when Quit is chosen in the
             plan; any exception other than SetupError/KeyboardInterrupt from a step (CalledProcessError,
             CommandError, ValidationError, OSError) propagates as a traceback.
    Feeds:   cli main (`setup`, `doctor`) and this file's `__main__`."""
    ap = argparse.ArgumentParser(prog="fabricctl setup", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="vars file (fabric.yaml / custom-vars.yaml)")
    ap.add_argument("--deploy-base", default="/opt", help="install root (default /opt)")
    ap.add_argument("--offline", action="store_true", help="never download; images and packages must be present")
    ap.add_argument("--non-interactive", action="store_true", help="never prompt; fail on missing values")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="accept the plan without the Proceed prompt (approves no host change: see --approve)")
    ap.add_argument("--approve", action="append", metavar="GROUPS",
                    help="allow these host changes without asking: packages, runtime, services, accounts, resolver, "
                         "firewall, trust, time (comma-separated, repeatable) or all")
    ap.add_argument("--decline", action="append", metavar="GROUPS",
                    help="refuse these host changes (recommended ones are then left unmanaged and shown in status)")
    ap.add_argument("--step", action="append", help="run only this step (repeatable)")
    ap.add_argument("--join", metavar="@FILE", nargs="?", const="",
                    help="join an upstream fabric as a new site (a fresh install): paste the invitation from "
                         "`fabricctl federation invite` at the prompt, or give @FILE or - (stdin)")
    ap.add_argument("--list", action="store_true", help="list the steps and exit")
    ap.add_argument("--doctor", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.list:
        for name, _, desc in STEPS:
            print(f"  {name:10} {desc}")
        return 0

    try:
        invitation = read_join_invitation(args.join, args.non_interactive)
    except SetupError as e:
        err(str(e))
        return 1
    ctx = SetupContext(deploy_base=args.deploy_base, user_vars_file=args.file, offline=args.offline,
                       non_interactive=args.non_interactive, assume_yes=args.yes, join_invitation=invitation)
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
        planned = planned_vars(ctx) if any(s in NEEDS_INPUT for s in selected) else ctx.vars
        ask_consent(ctx.config_dir, plan_host_changes(planned, ctx.deploy_base, ctx.config_dir,
                                                      os.path.join(ctx.source_dir, "jinja"), selected),
                    interactive=not ctx.non_interactive, approve=args.approve, decline=args.decline)

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
