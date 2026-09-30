# tests/webui

| File | What |
|---|---|
| `test_container.py` | The web UI container against a mock Keycloak (real RS256 tokens) and the real fabric-agent: sign-in gates, sessions, CSRF, RBAC, isolation |
| `test_devserver.py` | The dev preview: every page renders with sample data; production has no dev switch |
