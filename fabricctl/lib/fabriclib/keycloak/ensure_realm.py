from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step


def ensure_realm(kc, realm, display):
    """Purpose: create the realm if missing and set its login protections (brute-force lockout after 5 failures,
             temporary lockout up to 15 min, no e-mail login, no duplicate e-mails).
    Inputs:  kc — Admin; realm — realm name; display — display name, used only on creation.
    Returns: str, the realm's internal id.
    Fails:   SystemExit from Admin.call on any unexpected status.
    Feeds:   configure_keycloak (the id is the parent of the LDAP federation in ensure_ldap_federation)."""
    status, _ = kc.call("GET", f"/{q(realm)}", allow=(404,))
    if status == 404:
        kc.call("POST", "", {"realm": realm, "enabled": True, "displayName": display})
        step(f"created realm {realm}")
    kc.call("PUT", f"/{q(realm)}", {
        "bruteForceProtected": True, "permanentLockout": False, "failureFactor": 5,
        "maxFailureWaitSeconds": 900, "waitIncrementSeconds": 60,
        "loginWithEmailAllowed": False, "duplicateEmailsAllowed": False,
    })
    return kc.call("GET", f"/{q(realm)}")[1]["id"]
