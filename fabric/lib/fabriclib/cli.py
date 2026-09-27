#!/usr/bin/env python3
"""fabricctl lifecycle commands (routing only; each command lives in fabriclib/setup/).

  fabricctl setup [options]      install or re-converge (fabricctl setup --help)
  fabricctl doctor               end-to-end checks of the running install
  fabricctl certs [--force]      renew service certificates that need it (--force: all)
  fabricctl tsig list|add|remove  TSIG keys for RFC2136 updates (fabricctl tsig add --help)
  fabricctl client-cert <user> [--days N]
                                 web UI client certificate (.p12) into ~/fabric-admin
  fabricctl uninstall [--yes]    remove fabric from this host
  fabricctl reinstall [--yes]    uninstall + setup, keeping config, secrets, the CA and certificates
"""
import json
import os
import sys

# Run as a script, Python puts fabriclib/ itself first on sys.path, where its
# folders (dns/, ldap/, keycloak/) would shadow real packages. Use fabric/lib.
sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from fabriclib.dns.run_tsig_command import run_tsig_command  # noqa: E402
from fabriclib.pki.hand_out_client_cert import hand_out_client_cert  # noqa: E402
from fabriclib.pki.mint_extra_cert import mint_extra_cert  # noqa: E402
from fabriclib.setup import run_setup  # noqa: E402
from fabriclib.setup.backup_install import backup_install  # noqa: E402
from fabriclib.setup.context import SetupContext  # noqa: E402
from fabriclib.setup.renew_service_certs import renew_service_certs  # noqa: E402
from fabriclib.setup.restore_install import restore_install  # noqa: E402
from fabriclib.setup.stage_source import stage_source  # noqa: E402
from fabriclib.setup.uninstall import uninstall  # noqa: E402


def _base(args):
    return args[args.index("--deploy-base") + 1] if "--deploy-base" in args else "/opt"


def _confirm(prompt, args):
    if "--yes" in args or "-y" in args:
        return True
    return input(f"{prompt} Type 'yes' to continue: ").strip().lower() == "yes"


def main(argv):
    if os.geteuid() != 0:
        sys.exit("Run as root (sudo fabricctl ...)")
    cmd, args = (argv[0], argv[1:]) if argv else ("help", [])
    if cmd == "setup":
        return run_setup.main(args)
    if cmd == "doctor":
        return run_setup.main(["--doctor", *args])
    if cmd == "certs":
        renew_service_certs(SetupContext(deploy_base=_base(args)), force="--force" in args)
        return 0
    if cmd == "client-cert" and args and not args[0].startswith("-"):
        days = int(args[args.index("--days") + 1]) if "--days" in args else 365
        p12, password = hand_out_client_cert(SetupContext(deploy_base=_base(args)).load_state().vars, args[0], days)
        print(f"client certificate for '{args[0]}': {p12}")
        print(f".p12 password (shown once): {password}")
        return 0
    if cmd == "tsig":
        return run_tsig_command(args)
    if cmd == "extra-cert" and args:        # internal: fabricctl --mint-certs (certs.sh) -> one JSON entry
        print(mint_extra_cert(SetupContext(deploy_base=_base(args)).load_state().vars, json.loads(args[0])))
        return 0
    if cmd == "uninstall":
        ctx = SetupContext(deploy_base=_base(args))
        if not _confirm(f"This removes fabric, its data and its CA from {ctx.deploy_base}.", args):
            return 1
        uninstall(ctx)
        return 0
    if cmd == "reinstall":
        ctx = SetupContext(deploy_base=_base(args))
        if not _confirm("Reinstall fabric (config, secrets, CA and certificates are kept).", args):
            return 1
        saved = backup_install(ctx)
        source = stage_source(ctx)          # uninstall deletes an installed copy
        uninstall(ctx)
        restore_install(ctx, saved)
        cli = os.path.join(source, "lib", "fabriclib", "cli.py")
        os.execv(sys.executable, [sys.executable, cli, "setup", "--yes",
                                  *[a for a in args if a not in ("--yes", "-y")]])
    print(__doc__)
    return 0 if cmd in ("help", "--help", "-h") else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
