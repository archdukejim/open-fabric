from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step

MFA_FLOW = "fabric-webui-mfa"


def ensure_mfa_flow(kc, realm):
    """Purpose: make sure the "fabric-webui-mfa" browser flow exists (a copy of the stock browser flow) with its
             conditional second-factor sub-flow forced to REQUIRED, OTP REQUIRED and its "user configured" conditions
             DISABLED, so every user must enrol and use TOTP.
    Inputs:  kc — Admin; realm — realm name.
    Returns: str, the flow's id.
    Fails:   SystemExit from Admin.call; StopIteration if the flow is missing after the copy.
    Feeds:   configure_keycloak -> ensure_webui_client, ensure_openbao_client, ensure_adguard_client (browser flow
             override)."""
    _, flows = kc.call("GET", f"/{q(realm)}/authentication/flows")
    if not any(f["alias"] == MFA_FLOW for f in flows):
        kc.call("POST", f"/{q(realm)}/authentication/flows/browser/copy", {"newName": MFA_FLOW})
        step(f"created authentication flow {MFA_FLOW}")
    _, execs = kc.call("GET", f"/{q(realm)}/authentication/flows/{q(MFA_FLOW)}/executions")

    # The stock browser flow ends in a CONDITIONAL "... Conditional OTP/2FA"
    # sub-flow. Make it REQUIRED with OTP REQUIRED (users without TOTP are
    # made to enrol) and switch off its "user configured" conditions.
    in_second_factor = False
    changed = False
    for ex in execs:
        level = ex.get("level", 0)
        if ex.get("authenticationFlow") and "conditional" in ex.get("displayName", "").lower() and level == 1:
            in_second_factor, desired = True, "REQUIRED"
        elif in_second_factor and level >= 2:
            pid = ex.get("providerId", "")
            if pid == "auth-otp-form":
                desired = "REQUIRED"
            elif pid.startswith("conditional-"):
                desired = "DISABLED"
            else:
                continue
        else:
            in_second_factor = False
            continue
        if ex.get("requirement") != desired and desired in ex.get("requirementChoices", [desired]):
            ex["requirement"] = desired
            kc.call("PUT", f"/{q(realm)}/authentication/flows/{q(MFA_FLOW)}/executions", ex)
            changed = True
    if changed:
        step("enforced TOTP in the fabric-webui login flow")
    _, flows = kc.call("GET", f"/{q(realm)}/authentication/flows")
    return next(f["id"] for f in flows if f["alias"] == MFA_FLOW)
