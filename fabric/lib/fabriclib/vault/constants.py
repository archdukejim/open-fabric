"""OpenBao paths and names fabric uses."""
KEY_FILE = "unseal.key"                    # in openbao_key_dir (default /etc/fabric/openbao)
SETUP_CREDS = "setup-approle.json"         # AppRole for fabricctl setup (root 0400)
AGENT_CREDS = "agent-approle.json"         # AppRole for fabric-agent (root 0400)
BOOTSTRAP_TOKEN = "bootstrap-root-token"   # initial root token, only until configure succeeds and revokes it
KV_MOUNTS = {"fabric/": "fabric's own secrets", "apps/": "secrets for your applications"}

# Policies written by configure_openbao (HCL). fabric-setup administers
# fabric's configuration; fabric-agent only reads status for the web UI.
POLICIES = {
    "fabric-setup": """
path "sys/mounts"          { capabilities = ["read"] }
path "sys/mounts/*"        { capabilities = ["create", "read", "update"] }
path "sys/auth"            { capabilities = ["read"] }
path "sys/auth/*"          { capabilities = ["create", "read", "update", "sudo"] }
path "sys/policies/acl/*"  { capabilities = ["create", "read", "update", "list"] }
path "auth/approle/role/*" { capabilities = ["create", "read", "update", "list"] }
path "fabric/*"            { capabilities = ["create", "read", "update", "delete", "list"] }
""",
    "fabric-agent": """
path "sys/mounts" { capabilities = ["read"] }
path "sys/auth"   { capabilities = ["read"] }
path "apps/metadata/*" { capabilities = ["list"] }
""",
}
