from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.to_pem import to_pem


def ca_chain_pem(v):
    """Purpose: The fabric CA chain (intermediate + root) as one PEM bundle, to append after a leaf.
    Inputs:  v — fabric vars: deploy_base_dir (via ca_files). Reads stepca/data/certs/intermediate_ca.crt
             and root_ca.crt.
    Returns: str: the first certificate of the intermediate file followed by the first of the root file.
    Fails:   OSError if a CA file is missing or unreadable; ValidationError from to_pem if a file holds no
             certificate; IndexError if a file is empty.
    Feeds:   convert_cert, issue_key_pair, sign_csr.
    Notes:   the intermediate file may already carry the root (bring-your-own chain); only its first
             certificate is used, so the root is never duplicated.
    """
    root, intermediate = ca_files(v)
    with open(intermediate) as f:
        inter = to_pem(f.read(), "cert")[0]
    with open(root) as f:
        return inter + to_pem(f.read(), "cert")[0]
