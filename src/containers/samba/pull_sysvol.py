"""Group Policy between sites (manual 1.9.8.15, 2.1.6.16 revised, S8.4): Samba replicates GPO objects but not their
SYSVOL folders, so every DC copies the folders it does not own from the DC that does, over SMB as its own machine
account.
    docker exec samba python3 /fabric/pull_sysvol.py
Run by the DC's entrypoint every 5 minutes. Prints one line per GPO copied or refused; exit 0 unless it could not
start (the DC's database or SYSVOL unreadable)."""
import fcntl
import os
import re
import shutil
import sys

import ldb
from samba.credentials import MUST_USE_KERBEROS, Credentials
from samba.netcmd.gpo import copy_directory_remote_to_local, smb_connection

from open_samdb import open_samdb
from set_gpo_acl import set_gpo_acl

CONF = "/data/etc/smb.conf"
LOCK = "/run/samba/pull_sysvol.lock"     # one pull at a time (the entrypoint's round, or one run by hand)
LINK = re.compile(r"\[LDAP://cn=(\{[0-9a-f-]+\}),cn=policies,cn=system,[^;\]]*;\d+\]", re.I)


def _version(text):
    """Purpose: the version a GPT.INI states.
    Inputs:  text — str, the file's content.
    Returns: int, or -1 when it states none.
    Fails:   never.
    Feeds:   pull_sysvol."""
    m = re.search(r"^\s*Version\s*=\s*(\d+)", text, re.M | re.I)
    return int(m.group(1)) if m else -1


def _site_of(dn, sites):
    """Purpose: the fabric site that owns a link target: the nearest site OU at or above it (sites nest, 2.1.6.20).
    Inputs:  dn — str, the OU (or the domain) a GPO is linked to; sites — {lower-case site OU DN: site name}.
    Returns: str site name, or None (the domain, OU=Domain Controllers, anything outside OU=sites).
    Fails:   never.
    Feeds:   _owners."""
    parts = [p.strip() for p in dn.split(",")]
    for i in range(len(parts)):
        name = sites.get(",".join(parts[i:]).lower())
        if name:
            return name
    return None


def _owners(samdb, sites, root):
    """Purpose: each GPO's owning site: the site its link is in, the root for the domain's own and unlinked ones.
    Inputs:  samdb — SamDB; sites — {site OU DN (lower case): name}; root — the root site's name.
    Returns: {guid "{…}" upper case: site name}.
    Fails:   ldb.LdbError from a search.
    Feeds:   pull_sysvol."""
    owners = {}
    for res in samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE, expression="(gPLink=*)",
                            attrs=["gPLink"]):
        site = _site_of(str(res.dn), sites)
        for guid in LINK.findall(str(res["gPLink"][0])):
            if site or guid.upper() not in owners:        # a site's own link wins over the domain's
                owners[guid.upper()] = site or owners.get(guid.upper(), root)
    return owners


def _writable_dc(samdb, site, parents, root):
    """Purpose: the DC that holds a site's GPO folders: a writable DC in the site's own AD site, else its nearest
             ancestor's (an RODC site, or one with no DC, has its GPOs written there: manual 1.9.8.14).
    Inputs:  samdb — SamDB; site — str; parents — {site: parent site}; root — the root site.
    Returns: (dnsHostName str, NTDS Settings DN str) or None.
    Fails:   ldb.LdbError from a search.
    Feeds:   pull_sysvol."""
    config = str(samdb.get_config_basedn())
    seen = set()
    while site and site not in seen:
        seen.add(site)
        try:
            found = samdb.search(base=f"CN=Servers,CN={site},CN=Sites,{config}", scope=ldb.SCOPE_SUBTREE,
                                 expression="(objectClass=nTDSDSA)", attrs=["objectCategory"])
        except ldb.LdbError:
            found = []
        for ntds in sorted(found, key=lambda r: str(r.dn)):
            if "NTDS-DSA-RO" in str(ntds["objectCategory"][0]).upper():
                continue
            server = samdb.search(base=str(ntds.dn.parent()), scope=ldb.SCOPE_BASE, attrs=["dNSHostName"])[0]
            if "dNSHostName" in server:
                return str(server["dNSHostName"][0]), str(ntds.dn)
        site = parents.get(site) or (root if site != root else None)
    return None


def pull_sysvol():
    """Purpose: bring this DC's copy of every GPO folder it does not own up to its object's version.
    Inputs:  none (the DC's database and smb.conf, its machine account's Kerberos credentials).
    Returns: list of str, one per GPO copied or refused.
    Fails:   ldb.LdbError / RuntimeError opening the database; a folder that cannot be copied is reported, never
             half written (a copy goes into a new folder that replaces the old one only once complete).
    Feeds:   this script's main."""
    samdb, lp = open_samdb(CONF)
    base, realm = str(samdb.domain_dn()), lp.get("realm").lower()
    me = str(samdb.get_dsServiceName()).lower()
    sites, parents, root = {}, {}, None
    for res in samdb.search(base=f"OU=sites,{base}", scope=ldb.SCOPE_SUBTREE, expression="(objectClass=fabricSiteInfo)",
                            attrs=["ou"]):
        sites[str(res.dn).lower()] = str(res["ou"][0])
    for dn, name in sites.items():
        above = dn.split(",", 1)[1]
        if above in sites:                  # a site nested in its parent's OU (2.1.6.20)
            parents[name] = sites[above]
    # the root site's OU is the one holding OU=organisation (manual 1.6.3.4)
    for res in samdb.search(base=f"OU=sites,{base}", scope=ldb.SCOPE_SUBTREE, expression="(ou=organisation)",
                            attrs=["dn"]):
        root = sites.get(str(res.dn).split(",", 1)[1].lower(), root)
    owners = _owners(samdb, sites, root)
    policies = os.path.join(lp.get("path", "sysvol"), realm, "Policies")
    creds = None
    conns, out = {}, []
    for gpo in samdb.search(base=f"CN=Policies,CN=System,{base}", scope=ldb.SCOPE_ONELEVEL,
                            expression="(objectClass=groupPolicyContainer)", attrs=["cn", "versionNumber"]):
        guid = str(gpo["cn"][0]).upper()
        want = int(str(gpo.get("versionNumber", ["0"])[0]))
        folder = os.path.join(policies, guid)
        ini = os.path.join(folder, "GPT.INI")
        have = _version(open(ini, encoding="utf-8", errors="replace").read()) if os.path.exists(ini) else -1
        if have == want:
            continue
        holder = _writable_dc(samdb, owners.get(guid, root), parents, root)
        if holder is None or holder[1].lower() == me:
            continue                    # this DC owns it (its own writes keep it current), or nobody holds it
        host = holder[0]
        try:
            if host not in conns:
                if creds is None:
                    creds = Credentials()
                    creds.guess(lp)
                    creds.set_machine_account(lp)
                    creds.set_kerberos_state(MUST_USE_KERBEROS)
                conns[host] = smb_connection(host, "sysvol", lp, creds)
            conn = conns[host]
            remote = f"{realm}\\Policies\\{guid}"
            theirs = _version(conn.loadfile(remote + "\\GPT.INI").decode("utf-8", "replace"))
            if theirs != want:
                out.append(f"{guid}: not copied from {host}: its files are version {theirs}, the object {want} "
                           f"(changed away from its owner, or still being written)")
                continue
            os.makedirs(policies, exist_ok=True)       # a joined DC may have no Policies folder yet
            tmp = os.path.join(policies, f".fabric-pull-{guid}")
            shutil.rmtree(tmp, ignore_errors=True)
            copy_directory_remote_to_local(conn, remote, tmp)
            if _version(open(os.path.join(tmp, "GPT.INI"), encoding="utf-8", errors="replace").read()) != want:
                shutil.rmtree(tmp, ignore_errors=True)
                out.append(f"{guid}: not copied from {host}: it changed during the copy (next round)")
                continue
            old = os.path.join(policies, f".fabric-old-{guid}")
            shutil.rmtree(old, ignore_errors=True)
            if os.path.exists(folder):
                os.rename(folder, old)
            os.rename(tmp, folder)
            shutil.rmtree(old, ignore_errors=True)
            set_gpo_acl(samdb, lp, guid)
            out.append(f"{guid}: version {want} copied from {host}")
        except Exception as e:          # one owner unreachable never stops the others
            out.append(f"{guid}: not copied from {host}: {type(e).__name__}: {e}")
    return out


if __name__ == "__main__":
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for line in pull_sysvol():
            print(f"pull_sysvol: {line}", flush=True)
    except Exception as e:                  # reported in the DC's log; the DC keeps running
        print(f"pull_sysvol: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
