from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.secrets.save_secrets import save_secrets


def revoke_invitation(v, actor, which, source="cli"):
    """Purpose: withdraw an open invitation before it is used.
    Inputs:  v — fabric vars (for OpenBao); actor — str (audit); which — the invitation id or the site name it
             was made for; source — default "cli".
    Returns: the number of invitations withdrawn (>= 1).
    Fails:   ValidationError "no open invitation for <which>"; ValidationError from load_secrets/save_secrets;
             OSError.
    Feeds:   run_federation_command (revoke).
    Notes:   audited as FED_INVITE_REVOKE."""
    with federation_lock():
        invites = load_secrets(v=v).get("federation_invitations") or {}
        gone = [i for i, e in invites.items() if which in (i, e.get("site"))]
        if not gone:
            raise ValidationError(f"no open invitation for {which}")
        save_secrets({"federation_invitations": {i: e for i, e in invites.items() if i not in gone}}, v=v)
    write_audit(actor, "FED_INVITE_REVOKE", f"which={which} ids={','.join(gone)}", source)
    return len(gone)
