import os
import shutil

from fabriclib.common.console import ok


def adopt_stray_records(stray, archive):
    """Purpose: records that builds before 0.6.4 wrote next to the package's read-only copy (setup ran from it and its
             default paths followed: the audit log, issued certificates, the last rotation) moved into the install's
             archive, then the stray folder removed, so nothing is lost and dpkg can remove its folder on purge.
    Inputs:  stray — <package copy>/archive; archive — the install's archive folder.
    Returns: None. Logs (*.log, *.jsonl): lines the install lacks are appended. A last-run record (*.json) or any other
             file: kept from whichever copy is newer. Idempotent: no stray folder, nothing to do.
    Fails:   OSError on files.
    Feeds:   setup/deploy_config (from the package)."""
    if not os.path.isdir(stray):
        return
    os.makedirs(archive, mode=0o750, exist_ok=True)
    for name in sorted(os.listdir(stray)):
        src, dst = os.path.join(stray, name), os.path.join(archive, name)
        if not os.path.isfile(src):
            continue
        if name.endswith((".log", ".jsonl")) and os.path.exists(dst):
            have = set(open(dst).read().splitlines())
            missing = [line for line in open(src).read().splitlines() if line and line not in have]
            if missing:
                with open(dst, "a") as f:
                    f.write("\n".join(missing) + "\n")
        elif not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
            shutil.copy2(src, dst)
    shutil.rmtree(stray)
    ok(f"records an earlier build left in {stray} moved to {archive}")
