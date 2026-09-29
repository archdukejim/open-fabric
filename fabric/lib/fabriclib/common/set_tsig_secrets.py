from fabriclib.common.paths import SECRETS_FILE
from fabriclib.secrets.save_secrets import save_secrets


def set_tsig_secrets(updates, path=SECRETS_FILE):
    """Set ({name: secret}) or remove ({name: None}) TSIG secrets wherever
    fabric's secrets live (the 0600 file, or OpenBao once imported). Other
    secrets are untouched."""
    save_secrets({"tsig_secrets": dict(updates)}, path)
