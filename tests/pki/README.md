# tests/pki

| File | What |
|---|---|
| `run.py` | Manual PKI (sign a CSR, generate key + cert, inspect, convert, ledger) and zone TSIG keys against a throwaway CA made with the real Step-CA image, including what must be refused; runs `site_ca.py` at the end |
| `site_ca.py` | Federation site CAs: a site's key and request, signing with the root key (own or brought-in), checking and staging the answer, a leaf from the site CA, Step-CA serving with the encrypted site key; the refusals (wrong name, extra names, weak key, byoc without its root key, wrong password, wrong root, another site's key) |
