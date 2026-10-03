import os

import yaml

from fabriclib.consent.common.consent_file import consent_file


def save_consent(config_dir, groups):
    """Purpose: record the answers to the host-change groups (root-only, 0600).
    Inputs:  config_dir — the install's config folder (created if missing); groups — {group: record} as
             load_consent returns it.
    Returns: None; consent.yaml written atomically.
    Fails:   OSError.
    Feeds:   ask_consent."""
    os.makedirs(config_dir, exist_ok=True)
    path = consent_file(config_dir)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("# fabric: answers to the host-change questions (manual 2.7.1). Change them with\n"
                "# `sudo fabricctl setup --approve GROUP` / `--decline GROUP`, not here.\n")
        yaml.safe_dump({"groups": groups}, f, sort_keys=False)
    os.replace(tmp, path)
