from fabriclib.dns_filter.common.dnslog_psql import DB, ROLE, dnslog_psql

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    at timestamptz NOT NULL, client inet NOT NULL, port int NOT NULL, view text NOT NULL, name text NOT NULL,
    qtype text NOT NULL, action text, zone text, blocked boolean NOT NULL DEFAULT false);
CREATE INDEX IF NOT EXISTS queries_at ON queries (at);
CREATE INDEX IF NOT EXISTS queries_client_at ON queries (client, at);
CREATE INDEX IF NOT EXISTS queries_name ON queries (name);
CREATE TABLE IF NOT EXISTS stats_hourly (
    hour timestamptz NOT NULL, zone text NOT NULL, queries int NOT NULL, blocked int NOT NULL,
    PRIMARY KEY (hour, zone));
CREATE TABLE IF NOT EXISTS stats_blocked (
    day date NOT NULL, name text NOT NULL, zone text NOT NULL, count int NOT NULL, PRIMARY KEY (day, name, zone));
"""


def ensure_dnslog_db():
    """Purpose: the DNS query log's database (manual 1.12.2.13): the role fabric_dnslog, the database dnslog it owns
             (no other role may connect: CONNECT revoked from PUBLIC), and its tables. Idempotent.
    Inputs:  none (fabric's Postgres container, through dnslog_psql).
    Returns: True when the database was created now, False when it existed.
    Fails:   ValidationError from dnslog_psql (Postgres not running, a statement refused).
    Feeds:   dns_filter/ingest_dns_log (every run: cheap when all is there)."""
    exists = dnslog_psql(f"SELECT 1 FROM pg_database WHERE datname = '{DB}';", as_admin=True, db="postgres").strip()
    if not exists:
        dnslog_psql(f"""DO $$ BEGIN
                          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                              CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
                          END IF;
                        END $$;
                        CREATE DATABASE {DB} OWNER {ROLE};
                        REVOKE CONNECT ON DATABASE {DB} FROM PUBLIC;
                        GRANT CONNECT ON DATABASE {DB} TO {ROLE};""", as_admin=True, db="postgres")
    dnslog_psql(SCHEMA)
    return not exists
