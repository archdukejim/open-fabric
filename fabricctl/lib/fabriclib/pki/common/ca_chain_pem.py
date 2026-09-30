from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.to_pem import to_pem


def ca_chain_pem(v):
    """Intermediate + root as one PEM bundle (the intermediate file may
    already carry the root; only its first certificate is used)."""
    root, intermediate = ca_files(v)
    with open(intermediate) as f:
        inter = to_pem(f.read(), "cert")[0]
    with open(root) as f:
        return inter + to_pem(f.read(), "cert")[0]
