import os

from samba.dcerpc import security
from samba.ndr import ndr_unpack
from samba.ntacls import dsacl2fsacl
from samba.provision import getpolicypath, set_dir_acl
from samba.samba3 import param as s3param, passdb

import ldb


def set_gpo_acl(samdb, lp, guid):
    """Purpose: the file ACLs of one GPO's SYSVOL folder from its AD object, as Samba's provisioning sets them, instead
             of `samba-tool ntacl sysvolreset`, which needs every GPO's folder: at a site's DC the domain's other GPO
             folders are not there (SYSVOL's files do not replicate: manual 1.9.8.8, S8.4).
    Inputs:  samdb — SamDB (as the system); lp — LoadParm (the SYSVOL path, the realm, smb.conf); guid — "{…}".
    Returns: None.
    Fails:   ldb.LdbError when the GPO has no object; OSError / NTSTATUSError setting an ACL.
    Feeds:   ensure_gpo."""
    domain_dn = str(samdb.domain_dn())
    res = samdb.search(base=f"CN={guid},CN=Policies,CN=System,{domain_dn}", scope=ldb.SCOPE_BASE,
                       attrs=["nTSecurityDescriptor"])
    domsid = security.dom_sid(samdb.get_domain_sid())
    s3conf = s3param.get_context()
    s3conf.load(lp.configfile)
    s3conf.set("passdb backend", f"samba_dsdb:{samdb.url}")
    passdb.reload_static_pdb()
    pdb = passdb.PDB(s3conf.get("passdb backend"))
    acl = ndr_unpack(security.descriptor, res[0]["nTSecurityDescriptor"][0]).as_sddl()
    path = getpolicypath(lp.get("path", "sysvol"), lp.get("realm").lower(), guid)
    os.makedirs(path, exist_ok=True)
    set_dir_acl(path, dsacl2fsacl(acl, domsid), lp, str(domsid), False, passdb=pdb)
