import glob
import os
import sys
import traceback

from fabriclib.common.console import BLUE, BOLD, GREEN, NC, RED, YELLOW
from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import DEPLOY_BASE_DIR, FABRIC_DIR, SECRETS_FILE, VARS_FILE
from fabriclib.deploy.apply_deployment import apply_deployment


def apply_and_report():
    """Purpose: `fabricctl --apply`: run the deploy engine on vars.yaml and report which settings changed and which
             services it restarted.
    Inputs:  none; this install's vars.yaml and secrets (sets env CUSTOM_VARS_PATH, SECRETS_FILE_OVERRIDE,
             DEPLOY_BASE_DIR for the engine); the newest <fabric>/archive/*-vars.yaml (what was deployed before) and
             /tmp/fabric-render/vars.yaml (what was deployed now).
    Returns: None; progress printed.
    Fails:   sys.exit(<code>) with "Error deploying configurations!" when the engine exits; sys.exit(1) with a
             traceback on any other exception.
    Feeds:   interactive.py --apply (cli.py --apply; system/apply_changes for the web UI, under the vars lock);
             run_vars_menu (apply); edit_dns_zone (live and forced updates).
    Notes:   the engine restarts and reloads what changed itself; this only reports (it used to restart each of those
             services a second time)."""
    print(f"{BOLD}Applying changes natively...{NC}")
    archives = glob.glob(os.path.join(FABRIC_DIR, "archive", "*-vars.yaml"))
    old_vars = load_vars(max(archives)) if archives else load_vars(VARS_FILE)
    print(f"  {BLUE}[1/2]{NC} Rendering and deploying configurations...")
    os.environ.update({"CUSTOM_VARS_PATH": VARS_FILE, "SECRETS_FILE_OVERRIDE": SECRETS_FILE,
                       "DEPLOY_BASE_DIR": DEPLOY_BASE_DIR})
    try:
        restarted = apply_deployment() or set()
    except SystemExit as e:
        print(f"{RED}Error deploying configurations! Exit code {e.code}{NC}")
        sys.exit(e.code)
    except Exception:                       # report anything the engine raises, with where
        print(f"{RED}Exception during deployment!{NC}")
        traceback.print_exc()
        sys.exit(1)

    new_vars = load_vars("/tmp/fabric-render/vars.yaml")
    changed = [k for k, v in new_vars.items() if old_vars.get(k, object()) != v] + \
              [k for k in old_vars if k not in new_vars]
    if not changed:
        print(f"{GREEN}No variables have changed. System is up to date.{NC}")
        return
    print(f"Changed variables: {YELLOW}{', '.join(changed)}{NC}")
    print(f"  {BLUE}[2/2]{NC} Services restarted or reloaded: {', '.join(sorted(restarted)) or 'none'}")
    print(f"\n{BOLD}{GREEN}Apply complete!{NC}")
