from fabriclib.directory.common.read_directory import read_directory


def list_roles(v, directory=None):
    """Purpose: Device roles, lowest priority number first, with their member devices.
    Inputs:  v — fabric vars (used only when directory is not given); directory — optional read_directory
             result, default a fresh read.
    Returns: read_directory's role dicts sorted by (priority, name).
    Fails:   read_directory's /
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired) when it reads.
    Feeds:   device_overview.
    """
    directory = directory or read_directory(v)
    return sorted(directory["roles"], key=lambda r: (r["priority"], r["name"]))
