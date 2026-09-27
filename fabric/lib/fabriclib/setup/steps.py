"""Ordered setup steps. Each is idempotent and can run alone:
`fabricctl setup --step <name>`."""
from fabriclib.setup import (condition_host, configure_firewall, configure_network, create_accounts, create_admin,
                             deploy_config,
                             harden_docker, init_pki, migrate_from_core, mint_service_certs, preflight,
                             start_bootstrap, start_services, verify_install)

STEPS = [
    ("preflight", preflight.run, "check architecture, OS, RAM, cgroup memory controller, ports"),
    ("migrate", migrate_from_core.run, "move a core-template install to fabric (no-op otherwise)"),
    ("host", condition_host.run, "host packages and Docker Engine"),
    ("docker", harden_docker.run, "harden the Docker daemon"),
    ("deploy", deploy_config.run, "render and deploy configuration; install the fabricctl command"),
    ("accounts", create_accounts.run, "service users and groups"),
    ("network", configure_network.run, "docker network fabric_net; host resolver"),
    ("firewall", configure_firewall.run, "host firewall + LAN-only Docker-published ports"),
    ("pki", init_pki.run, "initialise Step-CA; publish and trust the CA"),
    ("bootstrap", start_bootstrap.run, "start bind9 and step-ca; check zones"),
    ("certs", mint_service_certs.run, "issue/renew service certificates"),
    ("start", start_services.run, "start everything; seed 389-DS; configure Keycloak; web UI"),
    ("admin", create_admin.run, "first web UI admin: LDAP user, client certificate, login kit"),
    ("verify", verify_install.run, "end-to-end checks (same as fabricctl doctor)"),
]
