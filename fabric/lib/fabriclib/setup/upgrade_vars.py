def upgrade_vars(data, pinned):
    """Adjust an existing install's rendered vars before they are re-rendered
    by a newer fabric:

    image_* keys are dropped unless `pinned` sets them, so an upgrade picks
    up the new release's images instead of freezing the old ones.
    Returns the list of changes made, for the log."""
    changes = []
    for key in [k for k in data if k.startswith("image_") and k not in pinned]:
        del data[key]
        changes.append(f"{key}: use this release's default")
    return changes
