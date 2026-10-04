# src/webui/routes

Every page (GET) and action (POST) behind the gates; each takes the request handler for send / redirect / deny.

| File | What |
|---|---|
| `bind9_page.py` | Render the BIND9 tab: forward zone records, generated reverse zones or TSIG keys. |
| `dirsrv_page.py` | Render the 389-DS tab: devices, one device, roles, one role, or people. |
| `dirsrv_post.py` | Devices, device roles and people: each form maps to one fabric-agent call. |
| `get_page.py` | Route a signed-in GET to its page. |
| `openbao_page.py` | Render the OpenBao tab: status, unlock methods and their add/rotate/remove forms, secrets, disk encryption. |
| `post_action.py` | Route a signed-in, CSRF-checked POST to its action. |
| `kea_post.py` | The Kea tab's changes: reservations, subnets (name, VLAN, notes, pools), options, client classes |
| `radius_post.py` | RADIUS clients: add, new shared secret, remove — saved and applied at once; a secret is shown once on its own page, never in a URL. |
| `saved_and_applied.py` | Run a change that fabric-agent saves and applies at once, and go back to its tab with the outcome. |
| `stepca_page.py` | Render the Step-CA tab for one sub-view, with the CA summary, linkable devices and the issued list where needed. |
| `stepca_post.py` | Manual PKI: each Step-CA form maps to one fabric-agent operation. |
| `tsig_post.py` | TSIG keys: create, rotate, delete (Apply publishes them to BIND9). |
| `vault_post.py` | Change the vault's unlock methods: rotate the key, test or remove a method, or add a USB stick, security key or KMIP HSM — each one fabric-agent call after a recent sign-in and the host name typed as confirmation. |
| `zone_post.py` | DNS records: add one to a zone, or delete one (published by the next Apply). |
| `__init__.py` | Empty; makes it a package |
