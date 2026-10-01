import os

import yaml

from fabriclib.common.paths import FEDERATION_FILE


def load_registry(path=FEDERATION_FILE):
    """Purpose: this install's federation record: the sites that joined it and, on a site, its upstream.
    Inputs:  path — default FEDERATION_FILE (<fabric>/config/federation.yaml).
    Returns: {"sites": {name: {"domain", "address", "joined", "ca_serial", "ca_not_after", "actor"}},
             "upstream": {...} or None}; both empty when the file is absent (a standalone install).
    Fails:   yaml.YAMLError for a malformed file; OSError reading it.
    Feeds:   create_invitation, accept_join, federation_status, join_upstream (records the upstream).
    Notes:   holds no secrets (invitations live hashed in fabric's secrets)."""
    data = {}
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    return {"sites": data.get("sites") or {}, "upstream": data.get("upstream")}
