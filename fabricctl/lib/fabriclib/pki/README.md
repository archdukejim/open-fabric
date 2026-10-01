# fabriclib/pki

Certificates from fabric's Step-CA.

| File | What |
|---|---|
| `needs_renewal.py` | True if a cert is missing, expires within 30 days, lacks a required DNS/IP name, or is not from the current CA |
| `mint_cert.py` | Issue a service cert from the running step-ca (JWK provisioner `admin`, RSA 4096); chain includes the intermediate |
| `install_cert.py` | Copy chain/key/root CA into a service's cert dir with its owner (chain/root 0644, key 0600) |
| `mint_offline_cert.py` | Sign a leaf or subordinate-CA cert directly with the intermediate key (step-ca need not run); RSA size or EC/OKP curve; used for extra, client and generated certs |
| `export_p12.py` | Bundle cert + key + CA chain into a password-protected `.p12` (password via a temp file, never argv) |
| `issue_client_cert.py` | Web UI client certificate for a user (CN = Keycloak username) as `<user>.p12` with a generated password |
| `mint_extra_cert.py` | One `extra_certs` entry → `.crt`/`.key` in its `out_dir` (or the sudo user's home); `extra_cert_paths` names them; used by setup and `--mint-certs` |
| `hand_out_client_cert.py` | `fabricctl client-cert <user>`: client `.p12` into the sudo user's `~/fabric-admin` |
| `describe_csr.py` | Decode a CSR (PEM/DER/base64) and judge it against the signing policy (signature, key strength, name types) |
| `sign_csr.py` | Sign a device's CSR as a leaf with the intermediate (validity capped by `pki_manual_max_days`); optional device link; ledger + audit |
| `issue_key_pair.py` | Generate a key + leaf cert for a device that cannot make a CSR; key returned once (PEM + `.p12`), never kept; ledger + audit |
| `inspect_pem.py` | Decode certificates or a CSR for reading; says whether this fabric issued them; refuses private keys |
| `convert_cert.py` | Certificate → PEM, DER, full chain (`.pem`, `.p7b`) and, with its key, a `.p12` (audited; key not kept) |
| `list_issued.py` | Hand-issued certificates from the ledger, newest first, with valid / expires soon / expired |
| `ca_summary.py` | Root and intermediate CA details, the certs page URL and the manual validity cap |
| `make_site_ca_request.py` | Federation: a joining site's intermediate key (stays here, encrypted) and its signing request |
| `sign_site_ca.py` | Federation: sign a site's intermediate with the root key (path length 0, never outliving the root); ledger + audit |
| `replace_site_ca.py` | Federation: switch a re-parented site's Step-CA files to its new CA (old ones kept) |
| `stage_site_ca.py` | Federation: check the root site's answer (pinned root, chain, path length, our key) and lay it out for the bring-your-own-CA path |
| `publish_ca_certs.py` | Root + intermediate for every system on `certs.<domain>` (PEM `.crt`/`.pem`, DER `.cer`/`.der`, chain `.pem`/`.p7b`, fingerprints JSON); trust them on this host |
| `common/` | Helpers shared by the operations above (see its README) |
