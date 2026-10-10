import os

from fabriclib.dns_filter.common.resolver_paths import resolver_paths


def resolver_tls_pending(v):
    """Purpose: whether the DNS name's certificate is now in the resolver's folder but its configuration was rendered
             without DoT and DoH (manual 1.12.2.16): setup deploys before it issues certificates, so a first install
             renders once more before the resolver starts.
    Inputs:  v — rendered vars (install_resolver, deploy_base_dir).
    Returns: bool; False with the resolver off.
    Fails:   OSError reading named.conf other than its absence.
    Feeds:   setup/start_services."""
    if not v.get("install_resolver"):
        return False
    paths = resolver_paths(v)
    if not all(os.path.exists(os.path.join(paths["tls"], f)) for f in ("fullchain.pem", "privkey.pem")):
        return False
    try:
        with open(os.path.join(paths["config"], "named.conf")) as f:
            return 'tls "clients"' not in f.read()
    except FileNotFoundError:
        return True
