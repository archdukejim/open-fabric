import os
import subprocess
import sys
import time

from fabriclib.common.errors import ValidationError
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.setup.check_export_dir import check_export_dir
from fabriclib.setup.context import SetupContext
from fabriclib.setup.export_install import export_install
from fabriclib.setup.uninstall import uninstall

USAGE = """usage: fabricctl uninstall                      asks: export first? where? remove the package too?
       fabricctl uninstall --yes (--export DIR | --no-export) [--purge-package]"""


def _opt(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _package_installed():
    res = subprocess.run(["dpkg-query", "-W", "-f=${Status}", "fabricctl"], capture_output=True, text=True)
    return res.returncode == 0 and "install ok installed" in res.stdout


def run_uninstall_command(args, deploy_base):
    """`fabricctl uninstall`: offers to export all of fabric's data to a
    folder you choose (nothing is left in /var or anywhere else), removes
    fabric, and optionally the fabricctl package too (apt purge, which then
    finds nothing left to do). Every question is asked before anything is
    touched. Unattended (--yes) the export choice must be explicit."""
    ctx = SetupContext(deploy_base=deploy_base).load_state()
    export, purge = _opt(args, "--export"), "--purge-package" in args
    try:
        if "--yes" in args or "-y" in args:
            if not export and "--no-export" not in args:
                raise ValidationError("with --yes, choose --export DIR or --no-export")
        else:
            print(f"This removes fabric from this host: every service, its data, the CA and the vault "
                  f"({ctx.deploy_base}, /etc/fabric/openbao). Docker and other containers are not touched.")
            if not export and "--no-export" not in args:
                if input("Export all of fabric's data first (config, secrets, CA, directory, vault + key)? "
                         "[Y/n] ").strip().lower() in ("", "y", "yes"):
                    default = os.path.join(sudo_owner()[1], f"fabric-export-{time.strftime('%Y%m%d-%H%M%S')}")
                    export = input(f"Export folder [{default}]: ").strip() or default
            if export:
                export = check_export_dir(ctx, export)         # refuse before anything is touched
            if not purge and _package_installed():
                purge = input("Also remove the fabricctl package (apt purge)? [y/N] ").strip().lower() in ("y", "yes")
            if input("Type 'yes' to remove fabric: ").strip().lower() != "yes":
                print("nothing changed")
                return 1
        if export:
            export_install(ctx, check_export_dir(ctx, export))
        uninstall(ctx)
    except ValidationError as exc:
        print(f"error: {exc}\n{USAGE}", file=sys.stderr)
        return 1
    if purge and _package_installed():
        res = subprocess.run(["apt-get", "purge", "-y", "-q", "fabricctl"],
                             env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"})
        print("fabricctl package removed" if res.returncode == 0 else "apt purge failed: sudo apt purge fabricctl")
    if export:
        print(f"Your data is in {export} (root only). It holds your CA and opens your vault: move it offline.")
    return 0
