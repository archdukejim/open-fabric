import base64
import secrets
import string

ALNUM = string.ascii_letters + string.digits


def random_secret(nbytes=32, alnum=False):
    """Purpose: a new random secret from the operating system's CSPRNG.
    Inputs:  nbytes — random bytes for the base64 form (default 32); alnum — True: 32 letters and digits instead
             (safe unquoted in LDIF, JSON and every switch CLI).
    Returns: str — base64 text (44 characters for 32 bytes), or 32 alphanumeric characters.
    Fails:   never.
    Feeds:   deploy/generate_missing_secrets, deploy/merge_tsig_keys, deploy/merge_radius_clients."""
    if alnum:
        return "".join(secrets.choice(ALNUM) for _ in range(32))
    return base64.b64encode(secrets.token_bytes(nbytes)).decode()
