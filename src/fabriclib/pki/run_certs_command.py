import sys

from fabriclib.common.errors import ValidationError
from fabriclib.pki.list_issued import list_issued
from fabriclib.pki.publish_crl import REASONS
from fabriclib.pki.revoke_cert import revoke_cert
from fabriclib.setup.renew_service_certs import renew_service_certs

USAGE = """usage: fabricctl certs [--force | --scheduled]        renew the service certificates that are due (2.1.5.4)
       fabricctl certs issued                       certificates issued by hand, client certificates and site CAs,
                                                    with their state (valid, expires soon, expired, revoked)
       fabricctl certs revoke <serial|name> [--reason R]
                                                    revoke one (published in the CRL at once, 2.1.5.10); R one of
                                                    """ + ", ".join(REASONS)


def run_certs_command(ctx, argv):
    """Purpose: route `fabricctl certs …`: renewal, the issued list, revocation.
    Inputs:  ctx — SetupContext (not loaded); argv — list of str after "certs" (--deploy-base and its value removed).
    Returns: exit status: 0 done, 1 a failure (renewal) or a refusal (ValidationError printed), 2 usage.
    Fails:   never raises a ValidationError (printed, exit 1); OSError and subprocess errors propagate.
    Feeds:   cli main (`certs`)."""
    flags = [a for a in argv if a.startswith("--")]
    try:
        if argv[:1] == ["issued"] and len(argv) == 1:
            rows = list_issued(limit=1000)
            for r in rows:
                print(f"{r.get('serial', '?'):<42} {r['status']:<13} {r.get('not_after', ''):<26} "
                      f"{r.get('kind', ''):<8} {r.get('subject', '')}")
            print(f"{len(rows)} certificate(s)" if rows else "nothing issued by hand yet")
            return 0
        if argv[:1] == ["revoke"]:
            rest = list(argv[1:])
            reason = "unspecified"
            if "--reason" in rest:
                i = rest.index("--reason")
                if i + 1 >= len(rest):
                    print(USAGE, file=sys.stderr)
                    return 2
                reason = rest.pop(i + 1)
                rest.pop(i)
            if len(rest) != 1 or rest[0].startswith("--"):
                print(USAGE, file=sys.stderr)
                return 2
            done = revoke_cert(ctx.load_state().vars, "root", rest[0], reason, source="cli")
            print(f"revoked {done['subject']} (serial {done['serial']}, {done['reason']}): in the CRL now")
            return 0
        if argv and not argv[0].startswith("--") or set(flags) - {"--force", "--scheduled"} \
                or {"--force", "--scheduled"} <= set(flags):
            print(USAGE, file=sys.stderr)
            return 2
        return renew_service_certs(ctx, force="--force" in flags, scheduled="--scheduled" in flags)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
