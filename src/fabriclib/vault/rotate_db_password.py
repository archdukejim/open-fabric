import datetime
import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import DB_ROTATION_FILE, SECRETS_FILE
from fabriclib.common.wait_healthy import wait_healthy
from fabriclib.common.write_audit import write_audit
from fabriclib.secrets.save_secrets import save_secrets
from fabriclib.system.apply_changes import apply_changes
from fabriclib.vault.common.bao_request import bao_request

ROLE = "keycloak"                             # OpenBao's static role for Keycloak's database password
KC_ROLE = "keycloak_db"                       # Keycloak's own role in Postgres (no superuser)


def _record(path, ok, actor, detail):
    """Purpose: the last rotation, for doctor and status.
    Inputs:  path — DB_ROTATION_FILE; ok — bool; actor — str; detail — str.
    Returns: None.
    Fails:   OSError writing the file.
    Feeds:   rotate_db_password."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"when": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "ok": ok,
                   "actor": actor, "detail": detail}, f)


def _apply_and_wait(actor, source):
    """Purpose: the default re-render and restart: `fabricctl --apply` (Keycloak's settings changed), then Keycloak
             healthy again.
    Inputs:  actor, source — the audit's.
    Returns: (ok: bool, output or why: str).
    Fails:   subprocess.TimeoutExpired from apply_changes.
    Feeds:   rotate_db_password."""
    done, output = apply_changes(actor, source)
    if not done:
        return False, output
    return wait_healthy("keycloak", timeout=600)


def rotate_db_password(v, token, actor="root", source="cli", rotate=True, apply=_apply_and_wait,
                       record=DB_ROTATION_FILE, secrets_file=SECRETS_FILE):
    """Purpose: Keycloak's database password, rotated by OpenBao's database engine (decision 2.1.7.4, manual 1.7.1):
             OpenBao sets a new one in Postgres, fabric keeps it in its secrets, renders Keycloak's settings and
             restarts it (about a minute; connections it holds keep working meanwhile).
    Inputs:  v — settings; token — an OpenBao token of fabric-setup; actor, source — the audit's; rotate — False only
             right after the static role was made (making it rotated the password); apply — the re-render and
             restart, callable(actor, source) -> (ok, why), Keycloak healthy when ok (default `fabricctl --apply`;
             setup and tests pass their own); record — where the last run is kept; secrets_file — fabric's secrets.
    Returns: {"ok": True}.
    Fails:   ValidationError: OpenBao refused the rotation (the old password keeps working); the new password could
             not be read or saved, or Keycloak did not come back with it (Keycloak's open connections keep working;
             run it again: `fabricctl vault rotate-db`). Each outcome is recorded and audited.
    Feeds:   vault/run_vault_command (`fabricctl vault rotate-db`, the monthly fabric-db-rotate timer),
             setup/ensure_db_rotation (configure_db_engine)."""
    try:
        if rotate:
            status, data = bao_request(v, "POST", f"database/rotate-role/{ROLE}", token=token)
            if status not in (200, 204):
                raise ValidationError(f"OpenBao did not rotate it ({data.get('errors') or status}); the old password "
                                      "keeps working")
        status, data = bao_request(v, "GET", f"database/static-creds/{ROLE}", token=token)
        if status != 200:
            raise ValidationError(f"the new password could not be read from OpenBao ({data.get('errors') or status})")
        save_secrets({"keycloak_db_user": KC_ROLE, "keycloak_db_password": data["data"]["password"]},
                     path=secrets_file, v=v)
        done, why = apply(actor, source)
        if not done:
            raise ValidationError("Keycloak did not come back with its new password: " + str(why).strip()[-300:])
    except ValidationError as exc:
        _record(record, False, actor, str(exc))
        write_audit(actor, "DB_ROTATE", f"role={ROLE} failed: {exc}", source)
        raise
    _record(record, True, actor, "rotated" if rotate else "taken over by OpenBao")
    write_audit(actor, "DB_ROTATE", f"role={ROLE} " + ("rotated" if rotate else "taken over"), source)
    return {"ok": True}
