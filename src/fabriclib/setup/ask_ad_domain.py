from fabriclib.common.console import BOLD, NC, YELLOW
from fabriclib.common.errors import ValidationError
from fabriclib.samba.check_password_policy import POLICY_KEYS, check_password_policy
from fabriclib.samba.suggested_ad_domain import suggested_ad_domain

# what each policy question asks (D89: nothing is preselected)
POLICY_QUESTIONS = [
    ("minimum_length", "Minimum password length (0–64)"),
    ("history", "Previous passwords remembered and refused again (0–24)"),
    ("minimum_age_days", "Days before a new password may be changed again (0 = at once)"),
    ("maximum_age_days", "Days a password is valid (0 = it never expires)"),
    ("lockout_threshold", "Failed sign-ins before an account is locked (0 = never locked)"),
    ("lockout_minutes", "Minutes an account stays locked"),
    ("lockout_window_minutes", "Minutes after which failed sign-ins are forgotten"),
]


def _number(prompt, low, high, current):
    """Purpose: ask for a whole number within a range, again until one is given.
    Inputs:  prompt — the question; low, high — the allowed range; current — the value already set, or None (then
             there is no default: an empty answer asks again). Interactive.
    Returns: int.
    Fails:   EOFError from input().
    Feeds:   ask_windows_domain."""
    hint = f" [{current}]" if current is not None else ""
    while True:
        answer = input(f"    {prompt}{hint}: ").strip()
        if not answer and current is not None:
            return current
        if answer.isdigit() and low <= int(answer) <= high:
            return int(answer)
        print(f"    {YELLOW}a whole number from {low} to {high}{NC}")


def ask_ad_domain(ctx):
    """Purpose: the directory's questions (manual 1.6.3, 2.1.9.8), asked by setup when they are not set: the AD domain
             (D87: chosen once, permanent; a sibling of fabric's domain suggested) and the whole password policy
             (D89: asked, never preselected). Fabric's directory is a Samba AD domain on every install.
    Inputs:  ctx — SetupContext; reads and sets ctx.vars ad_domain, ad_password_policy; domain for the suggestion.
             Interactive.
    Returns: None; ctx.vars set (an empty answer keeps a value already set, and is refused where none is). A policy AD
             would refuse (check_password_policy) is explained and asked again, its answers kept as defaults.
    Fails:   EOFError from input().
    Feeds:   setup/collect_vars."""
    print("\n  fabric's directory is a Samba AD domain (people, groups, devices; Windows and Linux machines may join).")
    domain = str(ctx.vars.get("domain") or "").lower()
    current = str(ctx.vars.get("ad_domain") or "").lower()
    print(f"    The AD domain is {BOLD}permanent{NC}: it cannot be changed once the domain exists.")
    suggestion = current or suggested_ad_domain(domain)
    if suggested_ad_domain(domain):
        where = ("beside fabric's domain, apart from the sites' names" if domain.count(".") >= 2
                 else "under fabric's domain (it has no parent of its own to sit beside)")
        print(f"    Suggested: {suggested_ad_domain(domain)}, {where}; press Enter to take it. "
              f"It cannot be {domain} itself.")
    while True:
        answer = input(f"    AD domain{f' [{suggestion}]' if suggestion else ''}: ").strip().lower()
        chosen = answer or suggestion
        if chosen and chosen != domain and "." in chosen and not domain.endswith("." + chosen):
            ctx.vars["ad_domain"] = chosen
            break
        print(f"    {YELLOW}a domain of two labels or more, not {domain} itself nor a parent of it{NC}")
    print("    The password policy is yours: nothing is preselected (D89).")
    policy = dict(ctx.vars.get("ad_password_policy") or {})
    while True:                           # checked as AD takes it, so a bad pair is asked again here, not at deploy
        for key, question in POLICY_QUESTIONS:
            low, high = POLICY_KEYS[key]
            policy[key] = _number(question, low, high, policy.get(key))
        while True:
            hint = {True: " [y]", False: " [n]"}.get(policy.get("complexity"), "")
            answer = input(f"    Require letters of both cases, digits or symbols (complexity) [y/n]{hint}: ")
            answer = answer.strip().lower()
            if not answer and isinstance(policy.get("complexity"), bool):
                break
            if answer[:1] in ("y", "n"):
                policy["complexity"] = answer.startswith("y")
                break
        try:
            check_password_policy(policy)
            break
        except ValidationError as e:
            print(f"    {YELLOW}{e}{NC}\n    Again (Enter keeps an answer):")
    ctx.vars["ad_password_policy"] = policy
