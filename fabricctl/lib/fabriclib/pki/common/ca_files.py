import os


def ca_files(v):
    """Purpose: Paths of this fabric's Step-CA root and intermediate certificates.
    Inputs:  v — fabric vars: deploy_base_dir.
    Returns: (root_path, intermediate_path): <deploy_base_dir>/stepca/data/certs/root_ca.crt and
             intermediate_ca.crt; existence is not checked.
    Fails:   KeyError if deploy_base_dir is missing.
    Feeds:   ca_summary, common/ca_chain_pem, convert_cert, inspect_pem, radius/radius_guides.
    """
    certs = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs")
    return os.path.join(certs, "root_ca.crt"), os.path.join(certs, "intermediate_ca.crt")
