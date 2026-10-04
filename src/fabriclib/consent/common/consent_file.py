import os


def consent_file(config_dir):
    """Purpose: where an install records its answers to the host-change questions (manual 2.7.1.4).
    Inputs:  config_dir — the install's config folder.
    Returns: "<config_dir>/consent.yaml" (str).
    Fails:   never.
    Feeds:   load_consent, save_consent, allowed_to_change."""
    return os.path.join(config_dir, "consent.yaml")
