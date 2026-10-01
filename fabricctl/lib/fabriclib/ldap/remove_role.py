from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_REMOVE = r'''
dn = "cn=%s,%s" % (IN["name"], ROLES)
c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["cn"])                    # NO_SUCH_OBJECT if missing
members = c.search_s(DEV, ldap.SCOPE_ONELEVEL,
                     "(fabricRoleName=%s)" % ldap.filter.escape_filter_chars(IN["name"]), ["cn"])
if members:
    raise Refused("role %s still has %d device(s); take them out first" % (IN["name"], len(members)))
c.delete_s(dn)
out({"ok": True})
'''


def remove_role(v, actor, name, source="web"):
    """Purpose: Delete a device role, refused while any of this install's devices still names it
             (fabricRoleName) so no device silently loses (or keeps) access.
    Inputs:  v — fabric vars; actor — str, for the audit; name — ROLE_NAME_RE; source — default "web".
    Returns: None.
    Fails:   ValidationError "invalid role name: ..."; "role <name> still has <n> device(s); take them out
             first"; "no such entry";
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/server.py Handler.directory (POST /v1/roles/<name>/delete) -> webui agentclient.delete_role.
    Notes:   audited as ROLE_REMOVE.
    """
    if not ROLE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid role name: {name!r}")
    run_dirsrv(v, _REMOVE, {"name": name})
    write_audit(actor, "ROLE_REMOVE", f"role={name}", source)
