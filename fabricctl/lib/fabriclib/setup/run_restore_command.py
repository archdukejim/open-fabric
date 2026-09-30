import os
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.setup.context import SetupContext
from fabriclib.setup.restore_install import restore_install

USAGE = "usage: fabricctl restore <export folder> [--yes]   (a folder written by `fabricctl uninstall --export`)"


def run_restore_command(args, deploy_base, cli):
    """`fabricctl restore <folder>`: bring back a fabric that was removed
    with `fabricctl uninstall --export` (or `apt purge`): its data goes back
    in place with owners and modes, then setup runs on it — the same CA,
    directory, Keycloak, DNS and vault (its key comes back with it).
    Refused while fabric is installed here. `cli` is this fabricctl's
    cli.py, which setup is run with (the packaged, newest code)."""
    folder = next((a for a in args if not a.startswith("-")), None)
    ctx = SetupContext(deploy_base=deploy_base)
    try:
        if not folder:
            raise ValidationError("which export folder?")
        folder = os.path.realpath(folder)
        if not (os.path.isfile(os.path.join(folder, "README.txt"))
                and os.path.isfile(os.path.join(folder, "fabric", "config", "vars.yaml"))):
            raise ValidationError(f"{folder} is not a fabric export (no README.txt / fabric/config/vars.yaml)")
        if os.path.exists(ctx.vars_file):
            raise ValidationError(f"fabric is installed here ({ctx.vars_file}): run `sudo fabricctl uninstall` first")
    except ValidationError as exc:
        print(f"error: {exc}\n{USAGE}", file=sys.stderr)
        return 1
    if "--yes" not in args and "-y" not in args:
        if input(f"Restore fabric from {folder} and set it up. Type 'yes' to continue: ").strip().lower() != "yes":
            print("nothing changed")
            return 1
    restore_install(ctx, folder)
    os.execv(sys.executable, [sys.executable, cli, "setup", "--yes", "--non-interactive",
                              *[a for a in args if a.startswith("--deploy-base") or a == "--no-color"]])
