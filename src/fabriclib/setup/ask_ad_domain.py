import re

from fabriclib.common.console import BOLD, NC, YELLOW
from fabriclib.samba.check_password_policy import POLICY_KEYS, check_password_policy
from fabriclib.samba.suggested_ad_domain import suggested_ad_domain

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")    # as check_samba_settings takes them

# what each policy question asks (2.1.6.13: nothing is preselected)
POLICY_QUESTIONS = [
    ("minimum_length", "Minimum password length (0–64)"),
    ("history", "Previous passwords remembered and refused again (0–24)"),
    ("minimum_age_days", "Days before a new password may be changed again (0 = at once)"),
    ("maximum_age_days", "Days a password is valid (0 = it never expires)"),
    # the lockout as one story, each answer building on the last (the owner was misled by the old order, 2026-10-08)
    ("lockout_threshold", "Lock an account after how many failed sign-ins in a row (0 = never lock)"),
    ("lockout_window_minutes", "  ...counting the failures over how many minutes (older ones are forgotten)"),
    ("lockout_minutes", "  ...then keep it locked for how many minutes (at least the minutes above; "
                        "0 = until an admin unlocks it)"),
]


def _number(prompt, low, high, current, rule=None):
    """Purpose: ask for a whole number within a range, again until one is given that the range and rule accept.
    Inputs:  prompt — the question; low, high — the allowed range; current — the value already set, or None (then
             there is no default: an empty answer asks again); rule — None, or a function of the number returning why
             it is refused (str) or None. Interactive.
    Returns: int.
    Fails:   EOFError from input().
    Feeds:   ask_ad_domain."""
    hint = f" [{current}]" if current is not None else ""
    while True:
        answer = input(f"    {prompt}{hint}: ").strip()
        value = current if not answer and current is not None else int(answer) if answer.isdigit() else None
        if value is None or not low <= value <= high:
            print(f"    {YELLOW}a whole number from {low} to {high}{NC}")
            continue
        refused = rule(value) if rule else None
        if not refused:
            return value
        print(f"    {YELLOW}{refused}{NC}")


def _rule(key, policy):
    """Purpose: the rule between one policy answer and those before it (as check_password_policy checks them), so a
             bad pair is refused at the question that makes it, not after the whole policy (the owner was misled by
             "Again", 2026-10-09).
    Inputs:  key — the question's POLICY_KEYS key; policy — the answers so far.
    Returns: None, or a function of the number returning why it is refused (str) or None.
    Fails:   never.
    Feeds:   ask_ad_domain."""
    if key == "maximum_age_days":
        least = policy["minimum_age_days"]
        return lambda n: (f"must be above {least} (the days before a change), or 0" if n and n <= least else None)
    if key == "lockout_minutes":
        window = policy["lockout_window_minutes"]
        return lambda n: (f"at least {window} (failed sign-ins are counted that long), or 0" if n and n < window
                          else None)
    return None


def ask_ad_domain(ctx):
    """Purpose: the directory's questions (manual 1.6.3, 1.1.9.8), asked by setup when they are not set: the AD domain
             (2.1.6.11: chosen once, permanent; a sibling of fabric's domain suggested) and the whole password policy
             (2.1.6.13: asked, never preselected). Fabric's directory is a Samba AD domain on every install.
    Inputs:  ctx — SetupContext; reads and sets ctx.vars ad_domain, ad_password_policy; domain for the suggestion.
             Interactive.
    Returns: None; ctx.vars set (an empty answer keeps a value already set, and is refused where none is). An answer
             AD would refuse beside an earlier one (_rule: the maximum age above the minimum, the lock at least the
             window) is explained and that one question asked again.
    Fails:   EOFError from input(); ValidationError from check_password_policy (only on a rule not asked here).
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
        labels = chosen.split(".")
        if (chosen and chosen != domain and len(labels) >= 2 and all(_LABEL.match(x) for x in labels)
                and len(chosen) <= 253 and not domain.endswith("." + chosen)
                and labels[-1] not in ("local", "localhost")):
            ctx.vars["ad_domain"] = chosen
            break
        print(f"    {YELLOW}a domain of two labels or more (letters, digits, hyphens), not .local, not {domain} itself "
              f"nor a parent of it{NC}")
    print("    The password policy is yours: nothing is preselected (2.1.6.13).")
    policy = dict(ctx.vars.get("ad_password_policy") or {})
    for key, question in POLICY_QUESTIONS:    # each answer checked as AD takes it, against those before it
        if key in ("lockout_window_minutes", "lockout_minutes") and policy.get("lockout_threshold") == 0:
            policy[key] = 0                   # never locked: neither the window nor the lock time applies
            continue
        low, high = POLICY_KEYS[key]
        policy[key] = _number(question, low, high, policy.get(key), _rule(key, policy))
    while True:
        hint = {True: " [y]", False: " [n]"}.get(policy.get("complexity"), "")
        answer = input(f"    Require letters of both cases, digits or symbols (complexity) [y/n]{hint}: ")
        answer = answer.strip().lower()
        if not answer and isinstance(policy.get("complexity"), bool):
            break
        if answer[:1] in ("y", "n"):
            policy["complexity"] = answer.startswith("y")
            break
    check_password_policy(policy)             # every rule was asked above: a refusal here is a bug, said loudly
    ctx.vars["ad_password_policy"] = policy
