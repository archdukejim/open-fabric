def upgrade_vars(data, pinned):
    """Adjust an existing install's rendered vars before they are re-rendered
    by a newer fabric:

    image_* keys pinned by digest are what this host runs: they are kept, so
    a fabric upgrade never changes a running image (`fabricctl images
    update` does, design D21). Unpinned refs (`nginx:latest`, from before
    pinning) and the names of local builds are dropped unless the admin set
    them (`pinned`): the release's validated, digest-pinned default applies.
    Returns the list of changes made, for the log."""
    changes = []
    for key in [k for k in data if k.startswith("image_") and k != "image_pins" and k not in pinned]:
        if isinstance(data[key], str) and "@sha256:" in data[key]:
            continue
        del data[key]
        changes.append(f"{key}: use this release's validated image (pinned by digest)")
    return changes
