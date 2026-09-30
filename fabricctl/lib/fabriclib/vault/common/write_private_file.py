import os


def write_private_file(path, data, uid=0, gid=0, mode=0o400):
    """Purpose: create or replace a file atomically so its content is never readable by anyone but its owner.
    Inputs:  path — target path (its folder must exist); data — str or bytes; uid, gid — owner (default 0:0);
             mode — final mode (default 0o400).
    Returns: None.
    Fails:   OSError: folder missing or not writable, chown not permitted (not root), or a leftover
             <path>.tmp-<pid> already exists (O_EXCL). The temporary file is removed on any failure.
    Feeds:   slots/local, slots/usb, slots/pkcs11.save_pin, add_kmip_slot, write_slot_store, write_seal_config,
             configure_openbao, unlock_vault; setup/setup_openbao, secrets/export_secrets.
    Notes:   the temporary file is created 0600 and gets its owner and mode before the rename, so there is no
             moment in which the content is group- or world-readable.
    """
    tmp = f"{path}.tmp-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb" if isinstance(data, bytes) else "w") as f:
            f.write(data)
        os.chown(tmp, uid, gid)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
