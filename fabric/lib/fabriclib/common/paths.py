"""Well-known paths, derived from where fabric is installed
(<deploy_base>/fabric/lib/fabriclib/common/paths.py)."""
import os

LIB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FABRIC_DIR = os.path.dirname(LIB_DIR)
DEPLOY_BASE_DIR = os.path.dirname(FABRIC_DIR)
VARS_FILE = os.path.join(FABRIC_DIR, "config", "vars.yaml")
VARS_LOCK_FILE = os.path.join(FABRIC_DIR, "config", ".vars.lock")
SECRETS_FILE = os.path.join(FABRIC_DIR, "config", "fabric-secrets.yml")
AUDIT_FILE = os.path.join(FABRIC_DIR, "archive", "audit.log")
ISSUED_CERTS_FILE = os.path.join(FABRIC_DIR, "archive", "issued-certs.jsonl")
BIND_DATA_DIR = os.path.join(DEPLOY_BASE_DIR, "bind9", "data")
