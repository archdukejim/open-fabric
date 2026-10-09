from agent.read_text import read_text
from agent.route_not_found import RouteNotFound
from fabriclib.common.load_vars import load_vars
from fabriclib.dns_filter.add_filter_list import add_filter_list
from fabriclib.dns_filter.add_filter_rule import add_filter_rule
from fabriclib.dns_filter.read_query_log import read_query_log
from fabriclib.dns_filter.remove_filter_list import remove_filter_list
from fabriclib.dns_filter.remove_filter_rule import remove_filter_rule
from fabriclib.dns_filter.set_filter_upstreams import set_filter_upstreams
from fabriclib.dns_filter.start_list_fetch import start_list_fetch
from fabriclib.system.apply_changes import apply_changes


def post_dns_filter(route, actor, data):
    """Purpose: answer POST /v1/dns-filter/... (manual 1.12.2.14): the DNS filter's settings changed from the web
             console, each saved and applied at once (the resolver reloads), and the query-log search.
    Inputs:  route — segments after /v1/ (already authorized: dns:filter, querylog dns:querylog); actor — who asks
             (audit); data — the JSON body: lists {name, url}; lists/delete {url}; rules and rules/delete {kind
             (allow | block), name}; upstreams {upstreams: "<address> <name>, …" or "none"}; fetch {}; querylog
             {client, name, blocked, limit}.
    Returns: a change: {"result": what it saved, "applied": bool, "output": the apply's output, "fetching": True
             when the lists job was started (a list added, or fetch)}; fetch: {"fetching": True}; querylog:
             read_query_log's result.
    Fails:   ValidationError (-> 400) for what fabriclib refuses (and nothing is saved); RouteNotFound (-> 404).
    Feeds:   agent/post_route."""
    if route == ["dns-filter", "querylog"]:            # a search: its terms in the body (a GET's query is ignored)
        return read_query_log(load_vars(), client=read_text(data, "client"), name=read_text(data, "name"),
                              blocked_only=bool(data.get("blocked")), limit=data.get("limit", 200))
    if route == ["dns-filter", "fetch"]:
        return {"fetching": start_list_fetch()}
    fetch = False
    if route == ["dns-filter", "lists"]:
        result, fetch = add_filter_list(actor, read_text(data, "name"), read_text(data, "url"), "web"), True
    elif route == ["dns-filter", "lists", "delete"]:
        result = remove_filter_list(actor, read_text(data, "url"), "web")
    elif route == ["dns-filter", "rules"]:
        result = add_filter_rule(actor, read_text(data, "kind"), read_text(data, "name"), "web")
    elif route == ["dns-filter", "rules", "delete"]:
        result = remove_filter_rule(actor, read_text(data, "kind"), read_text(data, "name"), "web")
    elif route == ["dns-filter", "upstreams"]:
        result = set_filter_upstreams(actor, read_text(data, "upstreams"), "web")
    else:
        raise RouteNotFound()
    ok, output = apply_changes(actor, source="web")
    # a new list is fetched by the lists job (fabric-agent has no internet), which applies it once it has a copy
    return {"result": result, "applied": ok, "output": output,
            "fetching": start_list_fetch() if fetch and ok else False}
