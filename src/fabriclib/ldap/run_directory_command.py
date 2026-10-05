import os

from fabriclib.common.paths import FEDERATION_FILE
from fabriclib.federation.configure_directory_links import configure_directory_links
from fabriclib.ldap.ensure_posix_identities import ensure_posix_identities
from fabriclib.ldap.people_written_here import people_written_here
from fabriclib.secrets.load_secrets import load_secrets

USAGE = """usage: fabricctl directory sync [--quiet]
  sync   give every person without one a POSIX identity (uidNumber from the users range, primary group users,
         /home/<uid>; where people are written) and keep the federation's directory replication as the federation
         says (a first copy that did not complete is started again); runs every 5 minutes by itself
         (fabric-directory-sync.timer). The address plan lives in the domain: convergence writes it"""


def run_directory_command(v, args):
    """Purpose: `fabricctl directory sync`: 389-DS upkeep on this install — POSIX identities and replication links
             (both leave with 389-DS in S7; the address plan moved to the domain in S4, manual 2.2.2.8).
    Inputs:  v — fabric vars; args — the words after `directory`: sync [--quiet].
    Returns: exit status: 0, 2 for usage.
    Fails:   ValidationError / RuntimeError from ensure_posix_identities or configure_directory_links.
    Feeds:   cli.py (`directory`), fabric-directory-sync.service."""
    if args[:1] != ["sync"]:
        print(USAGE)
        return 2
    quiet = "--quiet" in args
    if people_written_here():
        done = ensure_posix_identities(v)
        if done["added"] or not quiet:
            print(f"POSIX identities: {len(done['added'])} added"
                  + (f" ({', '.join(done['added'])})" if done["added"] else ""))
        if done["skipped"]:
            print("skipped (not a safe login name): " + ", ".join(done["skipped"]))
    elif not quiet:
        print("POSIX identities: people come from the upstream site here, with theirs")
    if os.path.exists(FEDERATION_FILE):
        linked = configure_directory_links(v, load_secrets(v=v), FEDERATION_FILE)
        if linked or not quiet:
            print("directory replication: " + (", ".join(linked) or "as the federation says"))
    return 0
