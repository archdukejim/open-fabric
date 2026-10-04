from fabriclib.common.console import BLUE, BOLD, GREEN, NC, YELLOW
from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import VARS_FILE


def print_vars(path=VARS_FILE):
    """Purpose: `fabricctl --print`: list the top-level settings of vars.yaml.
    Inputs:  path — vars.yaml (default this install's).
    Returns: None; one numbered line per key (dicts and lists shown as "(complex structure)"), or a notice when the
             file is missing or empty.
    Fails:   OSError / yaml.YAMLError reading it.
    Feeds:   interactive.py --print (cli.py --print)."""
    data = load_vars(path)
    if not data:
        print(f"{YELLOW}No custom variables found in {path}{NC}")
        return
    print(f"{BOLD}Custom Variables ({path}):{NC}\n")
    for idx, (k, v) in enumerate(data.items(), 1):
        shown = "(complex structure)" if isinstance(v, (dict, list)) else str(v)
        print(f"  {idx}) {BLUE}{k}{NC}: {GREEN}{shown}{NC}")
    print("")
