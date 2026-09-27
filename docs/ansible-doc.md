# Ansible Playbooks and Configurations

The `fabric` infrastructure is deployed via a sequential set of Ansible playbooks. The main entry point is `fabric/playbooks/fabric-config.yml`, which imports the individual playbook sections in order.

### Table of Contents
- [Playbook Breakdown](#playbook-breakdown)
- [Ansible Collections](#ansible-collections)
- [`ansible.cfg` Nuances](#ansiblecfg-nuances)
  - [1. Python Interpreter Pinning](#1-python-interpreter-pinning)
  - [2. Disabling Legacy Fact Injection](#2-disabling-legacy-fact-injection)
  - [3. Known Upstream Deprecation Warnings](#3-known-upstream-deprecation-warnings)

## Playbook Breakdown

| Playbook | Purpose |
|----------|---------|
| `00-controller-check.yml` | Validates the controller OS, installs APT dependencies, installs Docker Engine, and loads Docker images if running in offline mode. |
| `01-gen-vars-and-render-jinja.yml` | Idempotent generation of secrets, evaluates state/upgrade flags, and renders Jinja2 templates via Python. |
| `02-target-system-conditioning.yml` | Prepares the target host environment, configures UFW with a LAN allow-list. |
| `03-target-service-accounts.yml` | Creates localized system groups and service users (`nginx`, `bind`, `step`, `ldap`) on the target machine with specific UIDs/GIDs. |
| `04-target-file-structure.yml` | Replicates the directory tree onto the target (`/opt/...`), deploys the rendered configurations (incl. 389-DS seed LDIFs + `seed.py`, webui config, webui image build context and `fabric-agent.service`), systemd wrappers (incl. `webui`, which requires `fabric-agent`), and sets appropriate file ownership/permissions. |
| `05-target-network.yml` | Hardens `systemd-resolved` to prevent port 53 conflicts and performs additional network setup. |
| `06-configure-stepca.yml` | Initializes Step-CA, signs the intermediate CA CSR if deployed via BYOC, and establishes the foundational PKI structure. |
| `07-bootstrap-containers.yml` | Securely bootstraps foundational containers into existence. |
| `08-mint-service-certs.yml` | Uses the running Step-CA container to mint offline TLS certificates for BIND9, core services (incl. `mgr.<domain>`), and any `extra_certs`; installs the 389-DS TLS files (`/opt/dirsrv/data/tls`) and the webui client-CA bundle. |
| `09-start-and-configure.yml` | Starts the full stack via systemd wrappers, seeds 389-DS (`dirsrv.sh seed`), configures Keycloak via `keycloak_bootstrap.py` (realm, LDAP federation, webui client, MFA), then starts `fabric-agent`, builds the webui image (`build --pull`, online only) and starts the `webui` container. |
| `10-deploy-checks-and-cleanup.yml` | Verifies DNS resolution, checks HTTPS health endpoints, verifies LDAP role accounts bind with their generated secrets, plaintext binds are refused and the LDAPS cert verifies, checks the webui socket, the `fabric-agent` socket (mode `0660`, webui gid) and that nginx returns `400` without a client cert, exports startup logs, and cleans up temporary render directories. |

---

## Ansible Collections

The execution heavily relies on standard Ansible collections. These must be present on the controller machine (they are automatically packaged and installed by `offline.sh`).

1. **`community.docker`**
   - **Usage**: ~15+ tasks across the repository.
   - **Playbooks**: Heavily utilized in `00-system-check.yml`, `06-configure-stepca.yml`, `07-bootstrap-containers.yml`, `08-mint-service-certs.yml`, and `09-deploy-checks.yml`.
   - **Purpose**: Managing Docker containers (`docker_container`), Docker networks (`docker_network`), and full Compose stacks (`docker_compose_v2`).

2. **`community.general`**
   - **Usage**: ~8 tasks.
   - **Playbooks**: Utilized exclusively in `05-target-network.yml`.
   - **Purpose**: Manages the host firewall using the `ufw` module to ensure that ports are restricted appropriately based on the user's LAN CIDR configurations.

3. **`ansible.posix`**
   - **Usage**: Required implicitly for advanced Linux state management.
   - **Purpose**: Handling POSIX-specific operations (such as ACLs, SELinux booleans, or advanced file syncing). 

---

## `ansible.cfg` Nuances

The repository ships with its own `ansible.cfg` located in `fabric/playbooks/ansible.cfg`. It enforces several strict modernizations that developers modifying the playbooks must adhere to:

### 1. Python Interpreter Pinning
```ini
interpreter_python = /usr/bin/python3
```
- **Reason**: Suppresses Ansible's Python discovery warnings and ensures it always uses the system Python 3 on Ubuntu 24.04.

### 2. Disabling Legacy Fact Injection
```ini
inject_facts_as_vars = False
```
- **Reason**: Legacy behavior of injecting facts as top-level variables (e.g., `ansible_os_family`) was deprecated in Ansible 2.20 and removed in 2.24.
- **Requirement**: All playbooks in this repository MUST use the modern dictionary syntax to reference facts: `ansible_facts['os_family']`.

### 3. Known Upstream Deprecation Warnings
When running the installer, you may see a deprecation warning regarding `to_native` in `ansible.posix.acl`. 
- **Reason**: `ansible.posix.acl` version `2.1.0` imports from a deprecated path (`ansible.module_utils._text`).
- **Context**: This warning originates from the collection itself, not from the project's code. It cannot be suppressed per-module. It is harmless and will be resolved upstream when the collection is updated to `2.2.0` or higher.
