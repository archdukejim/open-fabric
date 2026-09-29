# fabriclib/vault/common

| File | What |
|---|---|
| `bao_request.py` | One OpenBao API call on its fabric_net address, TLS verified for its host name |
| `approle_login.py` | Log in with a stored AppRole (role_id + secret_id file, root 0400) → short-lived token |
| `write_private_file.py` | Atomically write a file that is never readable by anyone but its owner |
