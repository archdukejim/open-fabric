from fabriclib.common.one_time_password import one_time_password


def people_password(v):
    """Purpose: a one-time password for a person that the domain's policy accepts (2.1.6.13, manual 1.6.3.8): every
             character kind (so complexity is met) and at least as long as the policy's minimum (20 at least).
    Inputs:  v — fabric vars (ad_password_policy.minimum_length).
    Returns: str.
    Fails:   never for a policy fabric accepted (its minimum is at most 64).
    Feeds:   directory/create_person, directory/reset_sign_in, setup/create_admin."""
    minimum = int((v.get("ad_password_policy") or {}).get("minimum_length") or 0)
    return one_time_password(max(20, minimum))
