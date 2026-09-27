import os

from fabriclib.common.console import ok
from fabriclib.pki.mint_extra_cert import extra_cert_paths, mint_extra_cert
from fabriclib.pki.needs_renewal import needs_renewal


def mint_extra_certs(ctx):
    """Every extra_certs entry in vars: minted when its file is missing,
    expires within 30 days or lacks a name; otherwise left alone."""
    certs = ctx.path("stepca", "data", "certs")
    ca = (os.path.join(certs, "root_ca.crt"), os.path.join(certs, "intermediate_ca.crt"))
    for entry in ctx.vars.get("extra_certs") or []:
        crt, _, _ = extra_cert_paths(entry)
        names = [] if entry.get("is_ca") else [entry["cn"], *(entry.get("sans") or [])]
        if not needs_renewal(crt, names, ca):
            ok(f"{entry['cn']} (extra): current")
            continue
        ok(f"{entry['cn']} (extra): issued -> {mint_extra_cert(ctx.vars, entry)}")
