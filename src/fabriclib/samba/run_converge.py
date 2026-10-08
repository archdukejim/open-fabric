import json
import subprocess

from fabriclib.common.errors import ValidationError


def run_converge(state, container="samba"):
    """Purpose: hand a wanted state to the converge code inside a running DC (src/containers/samba/converge.py) on
             stdin — it holds service-account passwords, so never a command line — and return what it changed.
    Inputs:  state — dict, converge.py's state; container — the DC's container.
    Returns: list of str, what changed.
    Fails:   ValidationError "the Windows domain could not be converged: <the converge code's last line>" (or "the DC
             is not running"); subprocess.TimeoutExpired after 10 minutes.
    Feeds:   converge_domain (this site), prepare_site (a joining site, at the root)."""
    res = subprocess.run(["docker", "exec", "-i", "-e", "PYTHONDONTWRITEBYTECODE=1", container,
                          "python3", "/fabric/converge.py"],
                         input=json.dumps(state), capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise ValidationError("the Windows domain could not be converged: "
                              + ((res.stderr or res.stdout).strip().splitlines() or ["the DC is not running"])[-1])
    return json.loads(res.stdout)["changed"]
