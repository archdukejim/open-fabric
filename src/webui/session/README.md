# src/webui/session

Gates 3–4 and sign-in: the session bound to the certificate, token renewal, the Keycloak code flow, the page context.

| File | What |
|---|---|
| `find_session.py` | Gates 3 and 4: the signed-in session for this request, bound to the presented certificate, renewing its ID token shortly before it expires. |
| `finish_login.py` | Finish a Keycloak sign-in: check the attempt, verify the tokens, check the person against the certificate and their fabric roles, and create the session. |
| `page_context.py` | The page context every view needs: who is signed in, the CSRF token, their permissions and the installed version. |
| `renew_session.py` | Replace a session's ID token with a fresh one from Keycloak, picking up the person's current roles; end the session if Keycloak refuses. |
| `start_login.py` | Start a Keycloak sign-in: remember the attempt (bound to this certificate) and send the browser to Keycloak. |
| `__init__.py` | Empty; makes it a package |
