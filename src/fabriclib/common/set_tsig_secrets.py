from fabriclib.common.paths import SECRETS_FILE
from fabriclib.secrets.save_secrets import save_secrets


def set_tsig_secrets(updates, path=SECRETS_FILE):
    """Purpose: set or remove TSIG secrets wherever fabric's secrets live (the 0600 file, or OpenBao once
             imported), leaving other secrets untouched.
    Inputs:  updates — mapping {key name: secret str} to set, or {key name: None} to remove;
             path — str, the secrets file, default SECRETS_FILE.
    Returns: None.
    Fails:   whatever secrets/save_secrets raises (OSError writing the file; OpenBao errors when secrets are in
             the vault).
    Feeds:   dns/add_tsig_key, dns/remove_tsig_key, dns/replace_tsig_secret."""
    save_secrets({"tsig_secrets": dict(updates)}, path)
