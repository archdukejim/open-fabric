import subprocess


def missing_packages(pkgs):
    """Purpose: which of the given Debian packages are not installed.
    Inputs:  pkgs — package names (list of str).
    Returns: the names (in order) that dpkg-query does not report as "install ok installed".
    Fails:   FileNotFoundError without dpkg-query; unknown packages count as missing.
    Feeds:   setup/condition_host, consent/plan_packages."""
    res = subprocess.run(["dpkg-query", "-W", "-f=${Package} ${Status}\\n", *pkgs], capture_output=True, text=True)
    installed = {x.split()[0] for x in res.stdout.splitlines() if x.endswith("install ok installed")}
    return [p for p in pkgs if p not in installed]
