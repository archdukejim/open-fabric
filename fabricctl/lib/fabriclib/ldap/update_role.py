from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_role_fields import check_role_fields
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_UPDATE = r'''
r = IN
c.modify_s("cn=%s,%s" % (r["name"], ROLES), [
    (ldap.MOD_REPLACE, "description", [r["description"].encode()] if r["description"] else None),
    (ldap.MOD_REPLACE, "fabricPermission", [p.encode() for p in r["permissions"]] or None),
    (ldap.MOD_REPLACE, "fabricVlan", [str(r["vlan"]).encode()] if r["vlan"] else None),
    (ldap.MOD_REPLACE, "fabricPriority", [str(r["priority"]).encode()])])
out({"ok": True})
'''


def update_role(v, actor, name, fields, source="web"):
    """Purpose: Replace a device role's description, permissions, VLAN and priority; members are managed
             from each device.
    Inputs:  v — fabric vars; actor — str, for the audit; name — ROLE_NAME_RE; fields — as add_role
             (check_role_fields); source — default "web".
    Returns: None.
    Fails:   ValidationError "invalid role name: ..."; check_role_fields' messages; "no such entry" (no
             such role);
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/roles/<name>) -> webui agentclient.save_role.
    Notes:   audited as ROLE_UPDATE.
    """
    if not ROLE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid role name: {name!r}")
    f = check_role_fields(fields)
    run_dirsrv(v, _UPDATE, {"name": name, **f})
    write_audit(actor, "ROLE_UPDATE", f"role={name} permissions={','.join(f['permissions']) or '-'} "
                                      f"vlan={f['vlan'] or '-'} priority={f['priority']}", source)
