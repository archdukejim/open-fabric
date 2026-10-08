import subprocess


def list_conflicts(container="samba"):
    """Purpose: the objects AD renamed `CNF:` after the same name was made on two DCs while they were apart (manual
             1.9.8.5, Q12): one of each pair is a duplicate for an admin to resolve. Read from this DC's own database.
    Inputs:  container — the DC's container.
    Returns: list of str, the DNs (empty when there are none or the DC does not answer).
    Fails:   never.
    Feeds:   federation/federation_overview (the Federation tab)."""
    try:
        res = subprocess.run(["docker", "exec", container, "ldbsearch", "-H", "/data/private/sam.ldb",
                              "(name=*CNF:*)", "dn"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line[4:] for line in res.stdout.splitlines() if line.startswith("dn: ")]
