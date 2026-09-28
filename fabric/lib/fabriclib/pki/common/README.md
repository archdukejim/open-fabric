# fabriclib/pki/common

Helpers shared by the manual PKI operations.

| File | What |
|---|---|
| `openssl.py` | Run openssl with stdin data; failures become a `ValidationError` with openssl's message |
| `to_pem.py` | Pasted/uploaded PEM, DER or bare base64 → list of PEM blocks of one kind (cert, CSR, key) |
| `describe_cert.py` | Subject, issuer, SANs, key, validity, usages, SHA-256 fingerprint of a PEM certificate |
| `ca_files.py` | Paths of the Step-CA root and intermediate certificates |
| `ca_chain_pem.py` | Intermediate + root as one PEM bundle |
| `valid_days.py` | Validate a requested validity against `pki_manual_max_days` |
| `record_issued.py` | Append a manually issued certificate (never its key) to the issued-certificate ledger |
| `run_step.py` | Run the step CLI from the pinned Step-CA image as the step user, CA data at `/home/step`, no network |
| `artifacts_dir.py` | The step user's scratch directory `stepca/data/artifacts` |
| `valid_san.py` | Classify a subject alternative name as DNS / IP / e-mail, or reject it |
| `safe_name.py` | Download file name from a certificate name |
