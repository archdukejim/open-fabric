import os
import subprocess

from fabriclib.common.console import ok, warn
from fabriclib.consent.check_consent import check_consent
from fabriclib.consent.plan_accounts import plan_accounts


def _move_files(dirs, old, new, flag, tool):
    """Purpose: give every file under the folders that belongs to an old id to the new one.
    Inputs:  dirs — folders; old, new — ids (int); flag — "-uid" or "-gid"; tool — "chown" or "chgrp".
    Returns: None.
    Fails:   CalledProcessError from find.
    Feeds:   run."""
    for d in dirs:
        subprocess.run(["find", d, "-xdev", flag, str(old), "-exec", tool, "-h", str(new), "{}", "+"], check=True)


def run(ctx):
    """Purpose: one fabric-* system user and group per service, in fabric's uid band (600-649), so bind-mounted
             files have the right owner; an install that still has the previous accounts (bind, nginx, ... with
             their old ids) is moved to the new ones (design host-consent.md §5). Asks nothing: the `accounts`
             consent was given before the first step.
    Inputs:  ctx — SetupContext: vars.service_users, deploy_base, source_dir (jinja/), config_dir (consent.yaml).
    Returns: None; accounts exist (nologin, no home); files of a previous account belong to its new one, and the
             previous account is removed — unless a process still runs as it (a container not restarted yet):
             then a warning, and the next setup run removes it. Idempotent.
    Fails:   SetupError from plan_accounts (an id taken by another account) or check_consent (not approved);
             CalledProcessError from groupadd/useradd/find.
    Feeds:   setup step `accounts`, run by run_setup via STEPS."""
    actions = plan_accounts(ctx.vars, ctx.deploy_base, os.path.join(ctx.source_dir, "jinja"))
    if not actions:
        ok("service accounts in place")
        return
    check_consent(ctx.config_dir, "accounts", [a["text"] for a in actions])
    for a in actions:
        if a["do"] == "group":
            subprocess.run(["groupadd", "--system", "-g", str(a["gid"]), a["name"]], check=True)
        elif a["do"] == "user":
            subprocess.run(["useradd", "--system", "-u", str(a["uid"]), "-g", str(a["gid"]), "-M", "-d",
                            "/nonexistent", "-s", "/usr/sbin/nologin", a["name"]], check=True)
        elif a["do"] == "move":
            _move_files(a["dirs"], *a["uid"], "-uid", "chown")
            if a["gid"]:
                _move_files(a["dirs"], *a["gid"], "-gid", "chgrp")
        elif a["do"] == "remove":
            res = subprocess.run(["userdel", a["name"]], capture_output=True, text=True)
            if res.returncode != 0:
                warn(f"the old account {a['name']} is still in use ({res.stderr.strip()}); "
                     "the next setup run removes it")
                continue
            if a["group"]:
                subprocess.run(["groupdel", a["name"]], capture_output=True)
        ok(a["text"])
