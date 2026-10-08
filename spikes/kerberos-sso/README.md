# spikes/kerberos-sso

Spike K1 (manual 2.3.6.2.7, outcome in 2.3.6.2.8): Kerberos sign-in (SPNEGO) to Keycloak with a keytab exported from
fabric's Samba DC. Throwaway; never merged into `src/`.

| File | What |
|---|---|
| `run.py` | Against the keycloak suite's kept containers: the SSO service account, its SPNs and AES keys, its keytab in Keycloak, a domain client's `curl --negotiate` by name and through a CNAME |
