import os

PARENTS = "ca_parents.crt"


def ca_parents_pem(v):
    """Purpose: the CA certificates between this site's intermediate and the root — empty for the root site and
             for flat sites, the parent site's CA (and its parents) for a nested site (design federation.md §6).
    Inputs:  v — fabric vars: deploy_base_dir.
    Returns: str PEM of zero or more certificates (stepca/data/certs/ca_parents.crt), "" when there is none.
    Fails:   OSError when the file exists but cannot be read.
    Feeds:   ca_chain_pem, mint_offline_cert, issue_client_cert, sign_site_ca, publish/verify helpers."""
    path = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", PARENTS)
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        text = f.read().strip()
    return text + "\n" if text else ""
