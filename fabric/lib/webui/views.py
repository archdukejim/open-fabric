"""HTML rendering for webui. Jinja2 with autoescape; no inline scripts
or styles, so the page works under a strict Content-Security-Policy."""
import jinja2

_env = jinja2.Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)

# (tab id, path, label, optional feature)
TABS = [
    ("overview", "/", "Overview", False),
    ("bind9", "/bind9", "BIND9 · DNS", False),
    ("kea", "/kea", "Kea · DHCP", True),
    ("stepca", "/stepca", "Step-CA · PKI", False),
    ("dirsrv", "/dirsrv", "389-DS · Directory", False),
    ("freeradius", "/freeradius", "FreeRADIUS · 802.1X", True),
    ("openbao", "/openbao", "OpenBao · Secrets", False),
]
PLACEHOLDERS = {
    "kea": ("Kea DHCP", "Subnets and pools, reservations, active leases, and DHCP-driven DNS updates into BIND9."),
    "stepca": ("Step-CA", "Root and intermediate CA, issued certificates and renewals, client certificates for "
                          "admins, ACME provisioner."),
    "dirsrv": ("389 Directory Server", "Users, groups and organisational units; role accounts; password policy."),
    "freeradius": ("FreeRADIUS 802.1X", "Network access: EAP-TLS device certificates, MAC authentication, "
                                       "VLAN assignment, switches and access points (NAS clients)."),
    "openbao": ("OpenBao", "Seal status and unseal methods (key file, USB key, KMIP, PKCS#11), secrets engines, "
                           "fabric's own secrets, dynamic credentials and the SSH certificate authority."),
}
# service -> (what it is, tab)
SERVICES = {
    "nginx": ("Reverse proxy", None), "bind9": ("DNS", "bind9"), "stepca": ("Certificate authority", "stepca"),
    "ldap": ("389-DS directory", "dirsrv"), "postgres": ("Keycloak database", None),
    "keycloak": ("Single sign-on", None), "openbao": ("Secrets", "openbao"), "kea": ("DHCP", "kea"),
    "freeradius": ("802.1X", "freeradius"), "webui": ("This web UI", None), "fabric-agent": ("Host API", None),
}

_BASE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Fabric{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css"></head>
<body>
<header>
  <a class="brand" href="/">Fabric</a>
  {% if ctx %}
  <div class="who">
    <a href="/audit">Audit log</a>
    <span>{{ ctx.user }}</span>
    <form method="post" action="/logout"><input type="hidden" name="csrf" value="{{ ctx.csrf }}">
    <button class="link">Sign out</button></form>
  </div>
  {% endif %}
</header>
{% if ctx and ctx.dev %}<p class="devbanner">DEV PREVIEW — sample data, no sign-in, nothing is saved or applied</p>{% endif %}
{% if ctx %}
<nav class="tabs">
{% for id, href, label, optional in tabs %}
  <a href="{{ href }}" class="tab{{ ' active' if id == tab }}">{{ label }}{% if optional %}<span class="opt">optional</span>{% endif %}</a>
{% endfor %}
</nav>
{% endif %}
<main>{% block body %}{% endblock %}</main>
{% if ctx %}<footer>fabricctl {{ ctx.version.version }}{% if ctx.version.build %} · {{ ctx.version.build | replace('\\n', ' · ') }}{% endif %}</footer>{% endif %}
</body></html>"""

_TEMPLATES = {
    "base": _BASE,
    "error": """{% extends "base" %}{% block body %}
<section class="card narrow"><h1>{{ status }}</h1><p>{{ message }}</p>
<p><a href="/login">Sign in again</a></p></section>{% endblock %}""",

    "continue": """{% extends "base" %}{% block title %}Signing in…{% endblock %}
{% block body %}<meta http-equiv="refresh" content="0;url={{ target }}">
<section class="card narrow"><p>Signed in. <a href="{{ target }}">Continue</a></p></section>{% endblock %}""",

    "overview": """{% extends "base" %}{% block body %}
{% set healthy = services | selectattr(1, 'equalto', 'active') | list | length %}
<h1>Overview</h1>
<p class="muted">{{ healthy }} of {{ services | length }} services running.</p>
<section class="tiles">
{% for name, state, health in services %}
{% set info = service_info.get(name, (name, None)) %}
<div class="tile">
  <div class="tile-head">
    {% if info[1] %}<a href="/{{ info[1] }}"><strong>{{ name }}</strong></a>{% else %}<strong>{{ name }}</strong>{% endif %}
    <span class="pill {{ 'ok' if state == 'active' else 'bad' }}">{{ state }}</span>
  </div>
  <div class="muted">{{ info[0] }}</div>
  {% if health %}<div><span class="pill {{ 'ok' if health == 'healthy' else ('warn' if health == 'starting' else 'bad') }}">{{ health }}</span></div>{% endif %}
</div>
{% endfor %}
</section>
{% endblock %}""",

    "bind9": """{% extends "base" %}{% block body %}
<h1>BIND9 · DNS</h1>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<nav class="subtabs">
{% for z in zones %}<a href="/bind9?zone={{ z.key | urlencode }}" class="subtab{{ ' active' if zone and z.key == zone.key }}">{{ z.name }} <span class="muted">{{ z.records }}</span></a>{% endfor %}
</nav>
{% if zone %}
<p class="muted">{{ zone.status }}</p>
<section class="card"><h2>Records — {{ zone.name }}</h2>
<table><thead><tr><th>Type</th><th>Name</th><th>Value</th><th></th></tr></thead><tbody>
{% for r in zone.records %}
<tr><td><span class="pill">{{ r.type }}</span></td><td>{{ r.name or '(missing)' }}</td><td><code>{{ r.value }}</code></td>
<td class="num"><form method="post" action="/bind9/zone/{{ zone.key | urlencode }}/delete">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="type" value="{{ r.type }}">
<input type="hidden" name="index" value="{{ r.index }}"><input type="hidden" name="name" value="{{ r.name }}">
<button class="danger">Delete</button></form></td></tr>
{% endfor %}</tbody></table></section>
<section class="card"><h2>Add record</h2>
<form method="post" action="/bind9/zone/{{ zone.key | urlencode }}/add" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Type<select name="type">{% for t in types %}<option>{{ t }}</option>{% endfor %}</select></label>
<label>Name<input name="name" required placeholder="www or @"></label>
<label>IP (A / AAAA)<input name="ip" placeholder="192.168.1.20"></label>
<label>Target (CNAME / MX / SRV)<input name="target" placeholder="host"></label>
<label>Text (TXT)<input name="text"></label>
<label>Priority (MX / SRV)<input name="priority" inputmode="numeric" placeholder="10"></label>
<label>Weight (SRV)<input name="weight" inputmode="numeric"></label>
<label>Port (SRV)<input name="port" inputmode="numeric"></label>
<div><button>Add record</button></div>
</form></section>
{% endif %}
<form method="post" action="/apply" class="apply card">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<button>Apply changes</button>
<span class="muted">Publishes record changes: renders configuration and reloads only what changed — same as <code>fabricctl --apply</code>.</span>
</form>
<section class="card"><h2>TSIG keys</h2><p class="blank">Left intentionally blank.</p>
<p class="muted">RFC2136 keys, their secrets and update rights (today: <code>fabricctl tsig</code>).</p></section>
<section class="card"><h2>ACLs and update policies</h2><p class="blank">Left intentionally blank.</p>
<p class="muted">Who may query the zones, and which certbot devices may prove which names (today: <code>fabricctl acl</code>).</p></section>
{% endblock %}""",

    "placeholder": """{% extends "base" %}{% block body %}
<h1>{{ title }}{% if optional %} <span class="pill">optional</span>{% endif %}</h1>
<section class="card blank-card">
<p class="blank">Left intentionally blank.</p>
<p class="muted">{{ about }}</p>
{% if optional %}<p class="muted">Optional feature: it can be added to or removed from a running fabric.</p>{% endif %}
</section>
{% endblock %}""",

    "apply": """{% extends "base" %}{% block body %}
<h1>Apply {{ 'succeeded' if ok else 'failed' }}</h1>
<section class="card"><pre>{{ output }}</pre></section>
<p><a href="/bind9">Back to BIND9</a></p>{% endblock %}""",

    "audit": """{% extends "base" %}{% block body %}
<h1>Audit log</h1><p class="muted">Newest first. Web and CLI changes both land here.</p>
<section class="card"><pre>{% for line in lines %}{{ line }}{% endfor %}</pre></section>{% endblock %}""",
}
_env.loader = jinja2.DictLoader(_TEMPLATES)


def _render(name, **kw):
    kw.setdefault("ctx", None)
    kw.setdefault("tab", None)
    kw["tabs"] = TABS
    return _env.get_template(name).render(**kw)


def error_page(status, message):
    return _render("error", status=status, message=message)


def continue_page(target):
    return _render("continue", target=target)


def overview(ctx, services):
    """services: [(name, systemd state, container health)]"""
    return _render("overview", ctx=ctx, tab="overview", services=services, service_info=SERVICES)


def bind9(ctx, zones, zone, types, msg, err):
    return _render("bind9", ctx=ctx, tab="bind9", zones=zones, zone=zone, types=types, msg=msg, err=err)


def placeholder(ctx, tab):
    title, about = PLACEHOLDERS[tab]
    optional = next(opt for tid, _, _, opt in TABS if tid == tab)
    return _render("placeholder", ctx=ctx, tab=tab, title=title, about=about, optional=optional)


def apply_result(ctx, ok, output):
    return _render("apply", ctx=ctx, tab="bind9", ok=ok, output=output)


def audit(ctx, lines):
    return _render("audit", ctx=ctx, lines=lines)


def css():
    return """
:root{--bg:#f8fafc;--surface:#fff;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;
--accent:#0369a1;--ok:#15803d;--bad:#b91c1c;--warn:#b45309;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--surface:#1e293b;--border:#334155;
--text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;padding:12px max(16px,calc((100% - 1100px)/2 + 16px));border-bottom:1px solid var(--border);background:var(--surface)}
.brand{font-weight:600;color:var(--text);text-decoration:none}
.who{display:flex;gap:12px;align-items:center;color:var(--muted);margin:0}.who form{margin:0}
.tabs{display:flex;gap:4px;overflow-x:auto;padding:0 max(16px,calc((100% - 1100px)/2 + 16px));border-bottom:1px solid var(--border);background:var(--surface);scrollbar-width:thin}
.tab{flex:none;padding:10px 12px;color:var(--muted);text-decoration:none;border-bottom:2px solid transparent;white-space:nowrap}
.tab:hover{color:var(--text)}.tab.active{color:var(--text);border-bottom-color:var(--accent);font-weight:600}
.opt{margin-left:6px;font-size:11px;padding:0 6px;border:1px solid var(--border);border-radius:999px;color:var(--muted);font-weight:400}
.subtabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.subtab{padding:4px 12px;border:1px solid var(--border);border-radius:999px;text-decoration:none;color:var(--text);background:var(--surface)}
.subtab.active{border-color:var(--accent);color:var(--accent)}
main{max-width:1100px;margin:0 auto;padding:16px}
footer{max-width:1100px;margin:0 auto;padding:16px;color:var(--muted);font-size:13px}
h1{font-size:22px;margin:8px 0 12px}h2{font-size:16px;margin:0 0 12px}
a{color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 0 16px;overflow-x:auto}
.narrow{max-width:520px;margin:48px auto}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:6px}
.tile-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.blank{font-style:italic;color:var(--muted);margin:0 0 8px}
.blank-card{min-height:320px}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border);vertical-align:middle}
th{color:var(--muted);font-weight:500;font-size:13px}
td form{margin:0}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border:1px solid var(--border);border-radius:999px;font-size:12px}
.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.bad{color:var(--bad);border-color:var(--bad)}
.pill.warn{color:var(--warn);border-color:var(--warn)}
.muted,.crumb{color:var(--muted)}
.flash{padding:8px 12px;border-radius:6px;border:1px solid}
.flash.ok{color:var(--ok)}.flash.bad{color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:13px;color:var(--muted)}
input,select{font:inherit;padding:6px 8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
button{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:var(--surface);cursor:pointer}
button.danger{background:transparent;color:var(--bad);border-color:var(--bad);padding:2px 10px}
button.link{background:none;border:none;color:var(--accent);padding:0}
.apply{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
pre{white-space:pre-wrap;word-break:break-word;margin:0;font-size:13px}
code{font-size:13px}
.devbanner{margin:0;padding:8px 16px;text-align:center;font-weight:600;background:#b45309;color:#fff}
"""
