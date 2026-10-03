from fabriclib.consent.load_consent import load_consent


def allowed_to_change(config_dir, group, changes, unasked_install=False):
    """Purpose: whether fabric may make these host changes now: the group was approved and every change was among
             the approved ones (manual 2.7.1.4, step 4). Never asks.
    Inputs:  config_dir — the install's config folder; group — a consent group (groups.GROUPS); changes — the
             changes about to be made (list of str, as the group's plan words them); unasked_install — what to
             answer for an install that has no consent.yaml at all (set up before consent existed): apply, the
             agent and the timers pass True so such an install keeps converging until its next setup asks.
    Returns: True when there is nothing to change, or every change was approved; False otherwise (declined,
             never asked, or a change that was not part of what was approved).
    Fails:   yaml.YAMLError / OSError from load_consent.
    Feeds:   the setup steps and deploy parts that change the host (check_consent), apply."""
    if not changes:
        return True
    groups = load_consent(config_dir)
    if groups is None:
        return unasked_install
    record = groups.get(group) or {}
    return record.get("answer") == "yes" and set(changes) <= set(record.get("changes") or [])
