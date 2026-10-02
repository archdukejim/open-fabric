from fabriclib.common.console import warn
from fabriclib.consent.allowed_to_change import allowed_to_change
from fabriclib.consent.groups import GROUPS
from fabriclib.setup.errors import SetupError


def check_consent(config_dir, group, changes):
    """Purpose: the check a setup step makes before changing the host: go ahead, skip with a warning, or stop.
    Inputs:  config_dir — the install's config folder; group — a consent group; changes — what the step is about
             to change (list of str, worded as the group's plan words them).
    Returns: True — approved (or nothing to change): go ahead; False — not approved and the group is not
             required: the step leaves the host as it is (a warning says what that means).
    Fails:   SetupError when a required or choice group is not approved (the message says how to answer).
    Feeds:   setup steps host, docker, deploy, accounts, network, firewall, pki."""
    if allowed_to_change(config_dir, group, changes):
        return True
    g = GROUPS[group]
    how = f"`sudo fabricctl setup --step {g['step']}` asks again (or --approve {group})"
    if g["level"] != "recommended":
        raise SetupError(f"{g['title']}: not approved, so {g['declined']}. {how}.")
    warn(f"{g['title']}: not approved — left as it is; {g['declined']}. {how}.")
    return False
