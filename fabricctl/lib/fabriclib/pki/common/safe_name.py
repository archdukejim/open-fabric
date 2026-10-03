import re


def safe_name(cn):
    """Purpose: A download file name derived from a certificate name.
    Inputs:  cn — str (a CN, SAN or subject fragment).
    Returns: str: cn with every character outside A-Z a-z 0-9 . _ - replaced by "-", leading and trailing
             "." / "-" stripped; "certificate" when nothing is left.
    Fails:   never — pure string work on a str.
    Feeds:   convert_cert, issue_key_pair, sign_csr (the "name" the web UI uses for downloads).
    """
    return re.sub(r"[^A-Za-z0-9._-]", "-", cn).strip(".-") or "certificate"
