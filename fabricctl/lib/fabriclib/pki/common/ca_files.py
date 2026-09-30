import os


def ca_files(v):
    """(root_ca.crt, intermediate_ca.crt) of this fabric's Step-CA."""
    certs = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs")
    return os.path.join(certs, "root_ca.crt"), os.path.join(certs, "intermediate_ca.crt")
