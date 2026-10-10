def password_meets_policy(password, user, policy):
    """Purpose: why the domain would refuse a password a person chose, checked as AD checks it (2.1.6.13), so setup
             can ask again at once instead of failing when the person is created.
    Inputs:  password — str; user — their user name; policy — ad_password_policy (minimum_length, complexity).
    Returns: None when AD would take it; otherwise why not (str). Complexity is AD's: three of upper case, lower
             case, digits and other characters, and not the user name (when it is 3 characters or more).
    Fails:   KeyError when the policy lacks minimum_length or complexity.
    Feeds:   setup/ask_first_admin."""
    if len(password) < max(int(policy["minimum_length"]), 1):
        return f"at least {policy['minimum_length']} characters"
    if policy["complexity"]:
        kinds = sum(any(test(c) for c in password)
                    for test in (str.isupper, str.islower, str.isdigit, lambda c: not c.isalnum()))
        if kinds < 3:
            return "three of: upper case, lower case, digits, other characters (the domain asks for complexity)"
        if len(user) >= 3 and user.lower() in password.lower():
            return "not containing your user name (the domain asks for complexity)"
    return None
