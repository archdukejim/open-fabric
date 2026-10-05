import json
import subprocess

from fabriclib.common.errors import ValidationError


def domain_id_blocks(container="samba"):
    """Purpose: every site's uid/gid block as this site's DC holds it (manual 1.6.3.9, D97): read inside the DC from its
             own database (src/containers/samba/read_id_blocks.py), so a block handed out anywhere in the domain is
             seen, not only those this site's registry records.
    Inputs:  container — this site's DC.
    Returns: list of str "first-last".
    Fails:   ValidationError when the DC does not answer (a new block must never be guessed).
    Feeds:   federation/next_id_block."""
    try:
        res = subprocess.run(["docker", "exec", "-e", "PYTHONDONTWRITEBYTECODE=1", container, "python3",
                              "/fabric/read_id_blocks.py"], capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            return list(json.loads(res.stdout)["blocks"])
        why = (res.stderr.strip().splitlines() or ["no answer"])[-1]
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError) as e:
        why = str(e)
    raise ValidationError(f"the domain's id blocks could not be read from this site's DC: {why}")
