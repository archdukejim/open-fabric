import os

from fabriclib.common.console import ok
from fabriclib.pki.mint_extra_cert import extra_cert_paths, mint_extra_cert
from fabriclib.pki.needs_renewal import needs_renewal


def mint_extra_certs(ctx):
    """Purpose: keep every `extra_certs` entry in vars issued: minted when its file is missing, expires within
             30 days, lacks a name or is not from this CA; otherwise left alone.
    Inputs:  ctx — SetupContext: vars.extra_certs (entries with cn, sans, is_ca, output paths), Step-CA certs.
    Returns: None; prints each entry as current or issued (with its path).
    Fails:   ValidationError from pki.mint_extra_cert for an invalid entry or a failed issue (propagates);
             KeyError for an entry without cn.
    Feeds:   mint_service_certs.run (part of the `certs` step and `fabricctl certs`)."""
    certs = ctx.path("stepca", "data", "certs")
    ca = (os.path.join(certs, "root_ca.crt"), os.path.join(certs, "intermediate_ca.crt"))
    for entry in ctx.vars.get("extra_certs") or []:
        crt, _, _ = extra_cert_paths(entry)
        names = [] if entry.get("is_ca") else [entry["cn"], *(entry.get("sans") or [])]
        if not needs_renewal(crt, names, ca):
            ok(f"{entry['cn']} (extra): current")
            continue
        ok(f"{entry['cn']} (extra): issued -> {mint_extra_cert(ctx.vars, entry)}")
