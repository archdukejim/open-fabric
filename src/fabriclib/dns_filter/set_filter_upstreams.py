from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.check_filter_settings import check_filter_settings


def set_filter_upstreams(actor, text, source="cli"):
    """Purpose: where the DNS filter sends internet lookups (manual 1.12.2.8, 1.12.2.14): DNS-over-TLS upstreams, each
             with the name its certificate is checked against, or none (BIND resolves from the root servers). Saved in
             vars.yaml; applied by the next apply.
    Inputs:  actor — who asks (audit); text — "<address> <certificate name>" pairs separated by commas or new lines
             (e.g. "9.9.9.9 dns.quad9.net, 149.112.112.112 dns.quad9.net"), or "none"; source — "cli" or "web".
    Returns: the upstreams saved, [{address, name}] ([] for none).
    Fails:   ValidationError for an empty text, a pair without its name, or from check_filter_settings (not an
             address, not a name); OSError or yaml errors from the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/upstreams)."""
    text = str(text or "").strip()
    if not text:
        raise ValidationError("upstreams: \"<address> <certificate name>\" pairs, or none")
    ups = []
    if text.lower() != "none":
        for part in text.replace("\n", ",").split(","):
            pair = part.split()
            if not pair:
                continue
            if len(pair) != 2:
                raise ValidationError(f"{part.strip()!r}: an address and the name on its certificate, e.g. "
                                      "9.9.9.9 dns.quad9.net")
            ups.append({"address": pair[0], "name": pair[1].lower()})
    with vars_lock():
        data = load_vars()
        check_filter_settings({**data, "dns_filter_upstreams": ups})
        data["dns_filter_upstreams"] = ups
        save_vars(data)
    write_audit(actor, "DNS_FILTER_UPSTREAMS", ", ".join(f"{u['address']} {u['name']}" for u in ups) or "none",
                source)
    return ups
