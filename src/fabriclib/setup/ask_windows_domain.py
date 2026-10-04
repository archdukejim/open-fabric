from fabriclib.common.console import BOLD, NC, YELLOW
from fabriclib.deploy.check_samba_settings import POLICY_KEYS

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


def ask_windows_domain(ctx):
    """Purpose: Advanced plan question (manual 2.11.2, 2.1.9.7): the Windows domain — whether to run a Samba AD
             domain controller, its domain (D87: chosen once, permanent) and the whole password policy (D89: asked,
             never preselected).
    Inputs:  ctx — SetupContext; reads and sets ctx.vars install_samba, ad_domain, ad_password_policy; domain for the
             recommendation. Interactive.
    Returns: None; ctx.vars set. Turning it on asks the domain and every policy value (an empty answer keeps a value
             already set, and is refused where none is). A domain cannot change once the DC is provisioned: setup
             shows the one it has.
    Fails:   EOFError from input().
    Feeds:   setup/choose_plan (Advanced)."""
    on = bool(ctx.vars.get("install_samba"))
    answer = input(f"\n  Optional: a Windows domain (Samba AD: domain-joined Windows and Linux machines, Group Policy, "
                   f"PEAP)? [{'Y/n' if on else 'y/N'}] ").strip().lower()
    on = answer.startswith("y") if answer else on
    ctx.vars["install_samba"] = on
    if not on:
        return
    domain = str(ctx.vars.get("domain") or "").lower()
    current = str(ctx.vars.get("ad_domain") or "").lower()
    print(f"    The AD domain is {BOLD}permanent{NC}: it cannot be changed once the domain exists.")
    print(f"    Recommended: ad.{domain} (needed to federate sites or locations later); "
          f"fabric's own domain ({domain}) is not supported yet.")
    while True:
        answer = input(f"    AD domain [{current or 'ad.' + domain}]: ").strip().lower()
        chosen = answer or current or f"ad.{domain}"
        if chosen != domain and "." in chosen:
            ctx.vars["ad_domain"] = chosen
            break
        print(f"    {YELLOW}a domain of two labels or more, not {domain} itself{NC}")
    print("    The password policy is yours: nothing is preselected (D89).")
    policy = dict(ctx.vars.get("ad_password_policy") or {})
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
    ctx.vars["ad_password_policy"] = policy
