# fabriclib/pki

Certificates from fabric's Step-CA.

| File | What |
|---|---|
| `needs_renewal.py` | True if a cert is missing, expires within 30 days, lacks a required name, or is not from the current CA |
| `mint_cert.py` | Issue a cert from the running step-ca (JWK provisioner), chain includes the intermediate |
| `install_cert.py` | Copy chain/key/root CA into a service's cert dir with the right owner and modes |
| `mint_offline_cert.py` | Sign a leaf or subordinate-CA cert directly with the intermediate key (step-ca need not run); used for extra and client certs |
| `export_p12.py` | Bundle cert + key + CA chain into a password-protected `.p12` (password via a 0600 temp file) |
| `issue_client_cert.py` | Web UI client certificate for a user (CN = Keycloak username) as `<user>.p12` with a generated password |
| `mint_extra_cert.py` | One `extra_certs` entry → `<cn>.crt`/`.key` in its `out_dir` (or the sudo user's home); used by setup and `--mint-certs` |
| `hand_out_client_cert.py` | `fabricctl client-cert <user>`: client `.p12` into the sudo user's `~/fabric-admin` |
