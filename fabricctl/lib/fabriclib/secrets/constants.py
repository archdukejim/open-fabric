"""Where fabric keeps its own secrets."""
VAULT_PATH = "fabric/secrets"          # KV v2 entry (API: fabric/data/secrets, fabric/metadata/secrets)
MARKER = "secrets.openbao"             # in the config dir: OpenBao is the source of truth (never secret itself)
