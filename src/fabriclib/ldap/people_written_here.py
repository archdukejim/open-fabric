import os

from fabriclib.common.paths import FEDERATION_FILE
from fabriclib.federation.common.load_registry import load_registry


def people_written_here(registry_path=FEDERATION_FILE):
    """Purpose: whether people are created and changed on this install (a standalone install or the root site), or
             arrive read-only from an upstream site (federation M5).
    Inputs:  registry_path — the federation registry (default this install's config/federation.yaml).
    Returns: True when this install has no upstream site.
    Fails:   yaml/OSError from load_registry for a malformed registry.
    Feeds:   setup/start_services and setup/create_admin (POSIX identities), run_directory_command (sync)."""
    if not os.path.exists(registry_path):
        return True
    return not load_registry(registry_path).get("upstream")
