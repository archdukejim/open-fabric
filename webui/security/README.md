# webui/security

Gates 1–2 and the token's permissions: the client certificate nginx verified, issued directly by the Step-CA intermediate.

| File | What |
|---|---|
| `cert_subject_rfc2253.py` | Read a PEM certificate's subject DN in RFC 2253 form with openssl. |
| `parse_dn.py` | Split an RFC 2253 distinguished name (as nginx's $ssl_client_s_dn / _i_dn gives it) into (attribute, value) pairs, honouring backslash escapes. |
| `token_perms.py` | List the fabric permissions in a verified ID token: every role in the 'roles' claim that starts with 'fabric:', with the prefix removed. |
| `verified_client_cert.py` | Gates 1 and 2: the verified client certificate nginx forwarded, accepted only if it was issued directly by the fabric Step-CA intermediate. |
| `__init__.py` | Empty; makes it a package |
