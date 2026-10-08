# tests/pki

| File | What |
|---|---|
| `run.py` | Manual PKI (sign a CSR, generate key + cert, inspect, convert, ledger) and zone TSIG keys against a throwaway CA made with the real Step-CA image, including what must be refused; runs `site_ca.py` and `renewal.py` at the end |
| `site_ca.py` | Federation site CAs: a site's key and request, signing with the root key (own or brought-in), checking and staging the answer, a leaf from the site CA, Step-CA serving with the encrypted site key; the refusals (wrong name, extra names, weak key, byoc without its root key, wrong password, wrong root, another site's key) |
| `renewal.py` | Certificate renewal without containers (2.1.5.4–2.1.5.7): when a certificate is due (age, lifetime, CA, names), the lifetime settings and their refusals, the reload table, the run's record, `fabricctl certs`' flags, the warnings for status, doctor and the web console, the CA's lifetime (the Advanced question; a change refused on an existing CA) |
