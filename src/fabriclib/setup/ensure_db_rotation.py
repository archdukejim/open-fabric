import subprocess

from fabriclib.common.console import ok
from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import SECRETS_FILE
from fabriclib.common.wait_healthy import wait_healthy
from fabriclib.deploy.apply_deployment import apply_deployment
from fabriclib.setup.errors import SetupError
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import SETUP_CREDS
from fabriclib.vault.rotate_db_password import KC_ROLE, ROLE, rotate_db_password

PG_ADMIN = "fabric_admin"                     # Postgres's own admin, apart from Keycloak's role
BOOTSTRAP = "keycloak"                        # the role Postgres was made with (POSTGRES_USER): locked once moved off
DB = "keycloak"


def _psql(sql, user, container):
    """Purpose: SQL in the Postgres container over its local socket, on stdin (a password in it never reaches a
             command line).
    Inputs:  sql — str; user — the role to connect as; container — Postgres's container.
    Returns: subprocess.CompletedProcess (text).
    Fails:   never raises for a failed statement (returncode != 0); OSError without docker.
    Feeds:   _ensure_roles, _lock_bootstrap."""
    return subprocess.run(["docker", "exec", "-i", container, "psql", "-q", "-v", "ON_ERROR_STOP=1", "-U", user,
                           "-d", DB], input=sql, capture_output=True, text=True, timeout=60)


def _ensure_roles(password, container):
    """Purpose: Postgres's roles for 2.1.7.4: its own admin (fabric_admin, a superuser, which OpenBao uses) and
             Keycloak's own role (keycloak_db, no superuser) owning Keycloak's database and everything in it. The role
             Postgres was created with (`keycloak`, from POSTGRES_USER) is its bootstrap superuser, which Postgres 16+
             never lets lose that attribute: Keycloak moves off it instead, and _lock_bootstrap locks it afterwards.
    Inputs:  password — postgres_admin_password; container — Postgres's container.
    Returns: None.
    Fails:   SetupError with psql's message.
    Feeds:   configure_db_engine."""
    user = PG_ADMIN if _psql("SELECT 1;", PG_ADMIN, container).returncode == 0 else BOOTSTRAP   # before the first
    quoted = password.replace("'", "''")
    res = _psql(f"""DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PG_ADMIN}') THEN CREATE ROLE {PG_ADMIN}; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{KC_ROLE}') THEN CREATE ROLE {KC_ROLE}; END IF;
END $$;
ALTER ROLE {PG_ADMIN} WITH LOGIN SUPERUSER PASSWORD '{quoted}';
ALTER ROLE {KC_ROLE} WITH LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB;
ALTER DATABASE {DB} OWNER TO {KC_ROLE};
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT format('ALTER %s %I.%I OWNER TO {KC_ROLE}',
                         CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                                        ELSE 'TABLE' END, n.nspname, c.relname) AS q
             FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_roles o ON o.oid = c.relowner
            WHERE o.rolname = '{BOOTSTRAP}' AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'
              AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a', 'i'))
            ORDER BY c.relkind = 'S'
  LOOP EXECUTE r.q; END LOOP;
END $$;
""", user, container)
    if res.returncode != 0:
        raise SetupError(f"Postgres's roles: {res.stderr.strip()[-300:]}")


def _lock_bootstrap(container):
    """Purpose: once Keycloak runs as its own role, the bootstrap superuser it was created with signs in no more (no
             login, no password): only fabric_admin administers Postgres.
    Inputs:  container — Postgres's container.
    Returns: None.
    Fails:   SetupError with psql's message.
    Feeds:   configure_db_engine."""
    res = _psql(f"ALTER ROLE {BOOTSTRAP} WITH NOLOGIN PASSWORD NULL;", PG_ADMIN, container)
    if res.returncode != 0:
        raise SetupError(f"Postgres's bootstrap role: {res.stderr.strip()[-300:]}")


def _call(v, token, method, path, body=None):
    """Purpose: one OpenBao call that must succeed.
    Inputs:  v — settings; token — fabric-setup's; method, path, body — as bao_request.
    Returns: the answer's data (dict).
    Fails:   SetupError with OpenBao's errors.
    Feeds:   configure_db_engine."""
    status, data = bao_request(v, method, path, token=token, body=body)
    if status not in (200, 204):
        raise SetupError(f"OpenBao {method} {path}: {data.get('errors') or status}")
    return data


def configure_db_engine(v, token, admin_password, apply, container="postgres", secrets_file=SECRETS_FILE):
    """Purpose: converge Postgres and OpenBao for Keycloak's rotated password (decision 2.1.7.4): Postgres's own admin,
             Keycloak's user no superuser, OpenBao's database engine (database/) connected as that admin to Postgres's
             alias on fabric_net (its certificate verified), and Keycloak's password as its static role.
    Inputs:  v — settings (OpenBao's); token — an OpenBao token allowed fabric-setup's paths; admin_password —
             postgres_admin_password; apply — rotate_db_password's apply (re-render and restart Keycloak);
             container — Postgres's container; secrets_file — where fabric's secrets live.
    Returns: "converged" (nothing new) or "taken over" (the static role was made: it rotated the password, and
             Keycloak was applied with it).
    Fails:   SetupError from Postgres or OpenBao; ValidationError from rotate_db_password.
    Feeds:   run; tests/openbao/db_rotation.py."""
    _ensure_roles(admin_password, container)
    if "database/" not in _call(v, token, "GET", "sys/mounts"):
        _call(v, token, "POST", "sys/mounts/database", {"type": "database",
                                                        "description": "Keycloak's database password (2.1.7.4)"})
    _call(v, token, "POST", "database/config/postgres", {
        "plugin_name": "postgresql-database-plugin", "allowed_roles": [ROLE], "verify_connection": True,
        "connection_url": f"postgresql://{{{{username}}}}:{{{{password}}}}@postgres:5432/{DB}"
                          "?sslmode=verify-full&sslrootcert=/openbao/certs/root_ca.crt",
        "username": PG_ADMIN, "password": admin_password})
    status, _ = bao_request(v, "GET", f"database/static-roles/{ROLE}", token=token)
    if status == 200:
        _lock_bootstrap(container)            # Keycloak runs as its own role since the take-over
        return "converged"
    # fabric rotates it on its monthly timer; OpenBao's own period is only a backstop far beyond that
    _call(v, token, "POST", f"database/static-roles/{ROLE}", {"db_name": "postgres", "username": KC_ROLE,
                                                             "rotation_period": "87600h"})
    rotate_db_password(v, token, actor="setup", source="cli", rotate=False, apply=apply, secrets_file=secrets_file)
    _lock_bootstrap(container)
    return "taken over"


def _redeploy(ctx):
    """Purpose: the re-render and restart rotate_db_password asks for, inside setup: setup's own deploy engine in this
             process (`fabricctl --apply` would be a second deploy while setup runs), then Keycloak healthy.
    Inputs:  ctx — SetupContext (its cached secrets are dropped: the password changed).
    Returns: callable(actor, source) -> (ok: bool, why: str).
    Fails:   the callable: SystemExit from apply_deployment when a step is refused.
    Feeds:   run."""
    def apply(actor, source):
        apply_deployment(start_services=True)
        ctx._secrets = None
        return wait_healthy("keycloak", timeout=600)
    return apply


def run(ctx):
    """Purpose: Keycloak's database password rotated by OpenBao (decision 2.1.7.4, manual 1.7.1), as a setup step.
             Postgres never needs OpenBao to start (the password lives in Postgres).
    Inputs:  ctx — SetupContext: vars (install_keycloak), secrets (postgres_admin_password), secrets_file. Postgres
             and OpenBao running (after the vault step).
    Returns: None.
    Fails:   SetupError from configure_db_engine (a ValidationError becomes one).
    Feeds:   setup step `dbrotation`, run by run_setup via STEPS."""
    v = ctx.vars
    if not v.get("install_keycloak"):
        return
    try:
        state = configure_db_engine(v, approle_login(v, SETUP_CREDS), ctx.secrets["postgres_admin_password"],
                                    _redeploy(ctx), secrets_file=ctx.secrets_file)
    except ValidationError as exc:
        raise SetupError(f"Keycloak's database password: {exc}")
    ok("Keycloak's database password: " + ("now OpenBao's, rotated monthly (Postgres has its own admin)"
                                           if state == "taken over" else "OpenBao rotates it monthly"))
