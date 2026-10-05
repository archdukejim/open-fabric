from fabriclib.radius.normalize_radius_clients import normalize_radius_clients
from fabriclib.radius.normalize_radius_people import normalize_radius_people
from fabriclib.secrets.random_secret import random_secret


def merge_radius_clients(custom_vars, secrets):
    """Purpose: 802.1X settings from the vars file, checked; each RADIUS client's shared secret in fabric's secrets.
    Inputs:  custom_vars — the admin's vars (radius_clients, radius_people), changed
             in place; secrets — dict with radius_secrets, changed in place.
    Returns: {client: secret or None} — what changed (None: a removed client's secret is deleted); {} when nothing.
    Fails:   ValidationError from normalize_radius_clients / normalize_radius_people.
    Feeds:   apply_deployment (the changes are saved key by key: removals must be explicit).
    Notes:   like TSIG keys, a `secret` in the vars file (a switch that already has one) moves into the secrets;
             otherwise one is generated once (alphanumeric: every switch CLI takes it as typed). radius_people unset:
             vars.yaml.j2's default (the two network groups) applies."""
    radius_clients, embedded = normalize_radius_clients(custom_vars.get("radius_clients"))
    custom_vars["radius_clients"] = radius_clients
    if custom_vars.get("radius_people") is not None:
        custom_vars["radius_people"] = normalize_radius_people(custom_vars["radius_people"])
    current = dict(secrets.get("radius_secrets") or {})
    changes = {}
    for c in radius_clients:
        secret = embedded.get(c["name"]) or current.get(c["name"]) or random_secret(alnum=True)
        if current.get(c["name"]) != secret:
            current[c["name"]] = changes[c["name"]] = secret
    for name in [n for n in current if n not in {c["name"] for c in radius_clients}]:
        current.pop(name)
        changes[name] = None
    secrets["radius_secrets"] = current
    return changes
