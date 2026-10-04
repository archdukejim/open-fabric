from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_role_fields import check_role_fields
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_ADD = r'''
r = IN
attrs = {"objectClass": [b"top", b"groupOfNames", b"fabricRole"], "cn": [r["name"].encode()],
         "fabricPriority": [str(r["priority"]).encode()]}
if r["description"]:
    attrs["description"] = [r["description"].encode()]
if r["permissions"]:
    attrs["fabricPermission"] = [p.encode() for p in r["permissions"]]
if r["vlan"]:
    attrs["fabricVlan"] = [str(r["vlan"]).encode()]
c.add_s("cn=%s,%s" % (r["name"], ROLES), list(attrs.items()))
out({"ok": True})
'''


def add_role(v, actor, name, fields, source="web"):
    """Purpose: Create a device role: the permissions it grants its member devices, an optional VLAN and a
             priority (the lower number wins when roles set different VLANs).
    Inputs:  v — fabric vars; actor — str, for the audit; name — stripped, lower-cased, ROLE_NAME_RE;
             fields — {permissions, vlan, priority, description} (check_role_fields); source — default "web".
    Returns: the normalised role name.
    Fails:   ValidationError "role name: lowercase letters, digits, '-' and '_'"; check_role_fields'
             messages; "that name is already taken";
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/roles) -> webui agentclient.save_role.
    Notes:   audited as ROLE_ADD.
    """
    name = str(name).strip().lower()
    if not ROLE_NAME_RE.match(name):
        raise ValidationError("role name: lowercase letters, digits, '-' and '_'")
    f = check_role_fields(fields)
    run_dirsrv(v, _ADD, {"name": name, **f})
    write_audit(actor, "ROLE_ADD", f"role={name} permissions={','.join(f['permissions']) or '-'} "
                                   f"vlan={f['vlan'] or '-'} priority={f['priority']}", source)
    return name
