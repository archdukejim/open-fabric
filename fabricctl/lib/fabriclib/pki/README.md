# fabriclib/pki

Certificates from fabric's Step-CA.

| File | What |
|---|---|
| `needs_renewal.py` | True if a cert is missing, expires within 30 days, lacks a required name, or is not from the current CA |
| `mint_cert.py` | Issue a cert from the running step-ca (JWK provisioner), chain includes the intermediate |
| `install_cert.py` | Copy chain/key/root CA into a service's cert dir with the right owner and modes |
| `mint_offline_cert.py` | Sign a leaf or subordinate-CA cert directly with the intermediate key (step-ca need not run); RSA size or EC curve; used for extra, client and generated certs |
| `export_p12.py` | Bundle cert + key + CA chain into a password-protected `.p12` (password via a 0600 temp file) |
| `issue_client_cert.py` | Web UI client certificate for a user (CN = Keycloak username) as `<user>.p12` with a generated password |
| `mint_extra_cert.py` | One `extra_certs` entry → `<cn>.crt`/`.key` in its `out_dir` (or the sudo user's home); used by setup and `--mint-certs` |
| `hand_out_client_cert.py` | `fabricctl client-cert <user>`: client `.p12` into the sudo user's `~/fabric-admin` |
| `describe_csr.py` | Decode a CSR (PEM/DER/base64) and judge it against the signing policy (signature, key strength, name types) |
| `sign_csr.py` | Sign a device's CSR as a leaf with the intermediate (validity capped by `pki_manual_max_days`); ledger + audit |
| `issue_key_pair.py` | Generate a key + leaf cert for a device that cannot make a CSR; key returned once (PEM + `.p12`), never kept |
| `inspect_pem.py` | Decode certificates or a CSR for reading; says whether this fabric issued them; refuses private keys |
| `convert_cert.py` | Certificate → PEM, DER, full chain (`.pem`, `.p7b`) and, with its key, a `.p12` |
| `list_issued.py` | Hand-issued certificates from the ledger, newest first, with valid / expires soon / expired |
| `ca_summary.py` | Root and intermediate CA details, the certs page URL and the manual validity cap |
| `common/` | Helpers shared by the operations above (see its README) |
| `publish_ca_certs.py` | Root + intermediate for every system on `certs.<domain>` (PEM `.crt`/`.pem`, DER `.cer`/`.der`, chain `.pem`/`.p7b`, fingerprints JSON); trust them on this host |
