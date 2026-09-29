from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def remove_reservation(actor, mac, source="cli"):
    """Remove the reservation of `mac` from vars.yaml (applied by the next
    apply; the client then gets a pool address at its next renewal)."""
    mac = str(mac).strip().lower().replace("-", ":")
    with vars_lock():
        data = load_vars()
        for s in (data.get("dhcp") or {}).get("subnets") or []:
            kept = [r for r in s.get("reservations") or [] if r.get("mac", "").lower() != mac]
            if len(kept) != len(s.get("reservations") or []):
                s["reservations"] = kept
                save_vars(data)
                break
        else:
            raise ValidationError(f"no reservation for {mac}")
    write_audit(actor, "DHCP_UNRESERVE", f"mac={mac}", source)
