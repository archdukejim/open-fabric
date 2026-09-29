import getpass
import os
import subprocess
import sys

from fabriclib.common.errors import ValidationError
from fabriclib.logs.log_status import log_status

USAGE = """usage: fabricctl logs status                    log forwarding: destinations, sent, retries, errors
       fabricctl logs set-password elastic     the Elasticsearch/OpenSearch password (asked, or on stdin; kept in OpenBao)"""


def run_logs_command(ctx, argv):
    """`fabricctl logs …` (design D20)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    try:
        if cmd == "status" and not args:
            st = log_status(ctx.vars)
            if not st["enabled"]:
                print("log forwarding is off (install_fluentbit: false)")
                return 0
            if not st["reachable"]:
                print(f"Fluent Bit is not answering: {st.get('error', '')}")
                return 1
            if not st["outputs"]:
                print("Fluent Bit runs; no destination configured (log_forwarding in vars.yaml)")
            for name, m in st["outputs"].items():
                print(f"{name:<12} sent {m['sent']}  retries {m['retries']}  errors {m['errors']}  dropped {m['dropped']}")
            return 0
        if cmd == "set-password" and args == ["elastic"]:
            from fabriclib.secrets.save_secrets import save_secrets
            pw = getpass.getpass("Elasticsearch password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
            if not pw:
                raise ValidationError("empty password")
            save_secrets({"log_elastic_password": pw}, ctx.secrets_file)
            if ctx.vars.get("install_fluentbit"):
                from fabriclib.common.jinja_env import jinja_env
                from fabriclib.logs.deploy_fluentbit import deploy_fluentbit
                deploy_fluentbit(ctx.vars, ctx.secrets, jinja_env(os.path.join(ctx.target_dir, "jinja")))
                subprocess.run(["systemctl", "try-restart", "fluentbit"], capture_output=True)
            print("saved in OpenBao" + (" and applied (fluentbit restarted)" if ctx.vars.get("install_fluentbit") else ""))
            return 0
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
