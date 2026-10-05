from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.save_registry import save_registry
from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.secrets.save_secrets import save_secrets


def remove_site(actor, site, source="cli", v=None):
    """Purpose: on a site's parent (the root, or the site it is nested under): forget a site that joined here —
             a disposable lab torn down, or one moved elsewhere (manual 1.8.5.1).
    Inputs:  actor — str (audit); site — its name; source — default "cli"; v — fabric vars for OpenBao
             (default: read from vars.yaml).
    Returns: the removed record (dict); its DNS link key (federation_tsig[site]) is deleted too (and an older
             install's directory link secret, federation_replication[site]). The caller applies, so the
             delegation and the secondary zone go.
    Fails:   ValidationError "no site <x> joined here"; OSError / yaml errors from the registry.
    Feeds:   run_federation_command (remove).
    Notes:   the site's CA stays valid until it expires: revocation (a CRL, design F7) is not built yet, so a
             removed site's certificates are still trusted by the organisation. A site invited again under the
             same name gets a new CA. Audited as FED_SITE_REMOVE."""
    with federation_lock():
        registry = load_registry()
        record = registry["sites"].pop(site, None)
        if record is None:
            raise ValidationError(f"no site {site} joined here")
        save_registry(registry)
        stored = load_secrets(v=v)
        update = {}
        for name in ("federation_tsig", "federation_replication"):     # the DNS link (an older install: its directory)
            keys = dict(stored.get(name) or {})
            if keys.pop(site, None) is not None:
                update[name] = keys
        if update:
            save_secrets(update, v=v)
    write_audit(actor, "FED_SITE_REMOVE", f"site={site} ca_serial={record.get('ca_serial', '')}", source)
    return record
