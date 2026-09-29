import sys

from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import SECRETS_FILE
from fabriclib.common.write_audit import write_audit
from fabriclib.secrets.load_secrets import load_secrets


def _flat(secrets):
    out = {k: v for k, v in secrets.items() if k != "tsig_secrets"}
    out.update({f"tsig/{k}": v for k, v in (secrets.get("tsig_secrets") or {}).items()})
    return out


def run_secrets_command(argv, path=SECRETS_FILE):
    """`fabricctl secrets list` (names only) and `fabricctl secrets show
    <name>` (one value, e.g. keycloak_admin_password or tsig/npm). Reads
    from wherever fabric's secrets live; every `show` is audited."""
    if argv[:1] == ["list"] and len(argv) == 1:
        try:
            names = sorted(_flat(load_secrets(path)))
        except ValidationError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print("\n".join(names) if names else "no secrets")
        return 0
    if argv[:1] == ["show"] and len(argv) == 2:
        try:
            flat = _flat(load_secrets(path))
        except ValidationError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if argv[1] not in flat:
            print(f"error: no secret named {argv[1]!r} (fabricctl secrets list)", file=sys.stderr)
            return 1
        write_audit("root", "SECRET_READ", f"name={argv[1]}", "cli")
        print(flat[argv[1]])
        return 0
    print("usage: fabricctl secrets list | show <name>", file=sys.stderr)
    return 2
