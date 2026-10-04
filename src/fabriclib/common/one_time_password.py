import secrets
import string

KINDS = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "-_")


def one_time_password(length=20):
    """Purpose: a random password for a person (a one-time password at creation or reset) that every password
             policy fabric sets accepts: 389-DS wants 3 of its 4 character kinds (passwordMinCategories,
             00-config.ldif),
             and a plain token_urlsafe misses digits and "-"/"_" together about once in 60.
    Inputs:  length — characters (default 20, at least 12: passwordMinLength).
    Returns: str of URL-safe characters with at least one lower-case letter, one capital, one digit and one of "-_",
             in random order (operating system CSPRNG).
    Fails:   ValueError for a length under 12.
    Feeds:   keycloak/create_person, keycloak/reset_sign_in, setup/create_admin."""
    if length < 12:
        raise ValueError("a person's password needs at least 12 characters")
    every = "".join(KINDS)
    chars = [secrets.choice(kind) for kind in KINDS] + [secrets.choice(every) for _ in range(length - len(KINDS))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
