# fabriclib/pki

Certificates from fabric's Step-CA.

| File | What |
|---|---|
| `needs_renewal.py` | True if a cert is missing, expires within 30 days, or lacks a required name |
| `mint_cert.py` | Issue a cert from the running step-ca (JWK provisioner), chain includes the intermediate |
| `install_cert.py` | Copy chain/key/root CA into a service's cert dir with the right owner and modes |
