import json
import subprocess


def replication_status(container="samba"):
    """Purpose: how this site's DC replicates with the others (manual 1.8.8.5, 1.8.8.9): every inbound neighbour per
             partition, when it last succeeded and how often it has failed since — AD's own record (`repsFrom`), read
             inside the DC from its database (src/containers/samba/read_replication.py), so a read-only DC shows it
             too.
    Inputs:  container — the DC's container.
    Returns: {"neighbours": [{"partition", "from" (the partner DC's NTDS settings DN), "last_success", "failures"
             (int), "message"}], "error": "" or why the DC could not be asked}.
    Fails:   never (a DC that does not answer gives error and no neighbours).
    Feeds:   federation/federation_overview (the Federation tab)."""
    try:
        res = subprocess.run(["docker", "exec", "-e", "PYTHONDONTWRITEBYTECODE=1", container, "python3",
                              "/fabric/read_replication.py"], capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return {"neighbours": [], "error": (res.stderr.strip().splitlines() or ["the DC did not answer"])[-1]}
        return {"neighbours": json.loads(res.stdout)["neighbours"], "error": ""}
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError) as e:
        return {"neighbours": [], "error": str(e)}
