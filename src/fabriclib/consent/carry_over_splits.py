from fabriclib.consent.groups import SPLITS


def carry_over_splits(groups, plan):
    """Purpose: carry an answer given before a group was split into the groups it covered (manual 2.1.2.14): 0.6.1's
             `firewall` answers 0.6.2's `ports` and `firewall`; a group that is new (`own_rules`) is left to be asked.
    Inputs:  groups — the recorded answers ({group: {"answer", "changes", "when", "by"}}, from load_consent);
             plan — {group: [change, ...]} about to be asked (plan_host_changes).
    Returns: the names of the groups whose answer was carried over ([] when none); groups is updated in place, each
             carried answer covering exactly the changes now planned, with when/by of the original answer and
             "carried_from" naming it.
    Fails:   never.
    Feeds:   ask_consent."""
    carried = []
    for old, split in SPLITS.items():
        rec = groups.get(old) or {}
        if split["marker"] in groups or rec.get("answer") not in ("yes", "no") or rec.get("carried_from"):
            continue
        for group in split["covered"]:
            if group in plan:
                groups[group] = {"answer": rec["answer"], "changes": list(plan[group]), "when": rec.get("when"),
                                 "by": rec.get("by"), "carried_from": f"{old} (before {split['release']})"}
                carried.append(group)
    return carried
