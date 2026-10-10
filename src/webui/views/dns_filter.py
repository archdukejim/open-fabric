import time

from webui.views.constants import DNS_FILTER_SECTIONS
from webui.views.render_page import render_page


def _ago(ts):
    """Purpose: how long ago a time was, for the lists' state.
    Inputs:  ts — seconds since the epoch, or None.
    Returns: "never", "5 min ago", "3 h ago" or "2 days ago".
    Fails:   never.
    Feeds:   dns_filter."""
    if not ts:
        return "never"
    s = max(0, int(time.time() - ts))
    return f"{s // 60} min ago" if s < 7200 else f"{s // 3600} h ago" if s < 172800 else f"{s // 86400} days ago"


def dns_filter(ctx, section, overview, log, search, msg="", err=""):
    """Purpose: The DNS filter tab (manual 1.12.2.14): the statistics, the lists (and AdGuard's catalogue to add from),
             the rules, the query log with Allow / Block from a line, and the upstreams.
    Inputs:  ctx — page context; section — a DNS_FILTER_SECTIONS id; overview — filter_overview's dict, or None
             without dns:filter; log — query_log's result or None; search — the query log's search (client, name,
             blocked, limit); msg, err — flash texts.
    Returns: HTML str.
    Fails:   Jinja2 errors propagate (e.g. UndefinedError when the template reads a key the caller left out).
    Feeds:   src/webui/routes/dns_filter_page; devserver."""
    peak = max([h["queries"] for h in ((overview or {}).get("stats") or {}).get("hours") or []] or [1])
    return render_page("dns_filter", ctx=ctx, tab="dnsfilter", sections=DNS_FILTER_SECTIONS, view=section,
                       d=overview, log=log, search=search, peak=peak, ago=_ago, msg=msg, err=err)
