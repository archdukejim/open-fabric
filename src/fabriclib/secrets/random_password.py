import secrets
import string

CLASSES = (string.ascii_uppercase, string.ascii_lowercase, string.digits)


def random_password(length=64):
    """Purpose: a new random password that any password policy fabric allows accepts (manual 1.6.3.8): letters of
             both cases and digits, each at least once, and as long as the longest minimum length allowed (64).
    Inputs:  length — int, at least 3 (default 64).
    Returns: str of `length` letters and digits, from the operating system's CSPRNG.
    Fails:   ValueError if length is below 3.
    Feeds:   deploy/generate_missing_secrets (the domain's Administrator)."""
    if length < 3:
        raise ValueError("a password needs room for every character class")
    alphabet = "".join(CLASSES)
    chars = [secrets.choice(c) for c in CLASSES] + [secrets.choice(alphabet) for _ in range(length - len(CLASSES))]
    # place the guaranteed characters at random positions
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)
