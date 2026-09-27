"""HTML rendering for webui. Jinja2 with autoescape; no inline scripts
or styles, so the page works under a strict Content-Security-Policy."""
import jinja2

_env = jinja2.Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)

_BASE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Fabric{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css"></head>
<body>
<header>
  <a class="brand" href="/">Fabric</a>
  {% if ctx %}
  <nav><a href="/">Overview</a><a href="/audit">Audit log</a></nav>
  <form method="post" action="/logout" class="who">
    <span>{{ ctx.user }}</span>
    <input type="hidden" name="csrf" value="{{ ctx.csrf }}">
    <button class="link">Sign out</button>
  </form>
  {% endif %}
</header>
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

    "dashboard": """{% extends "base" %}{% block body %}
<h1>Overview</h1>
<section class="card"><h2>Services</h2>
<table><thead><tr><th>Service</th><th>State</th></tr></thead><tbody>
{% for name, state in services %}
<tr><td>{{ name }}</td><td><span class="pill {{ 'ok' if state == 'active' else 'bad' }}">{{ state }}</span></td></tr>
{% endfor %}</tbody></table></section>
<section class="card"><h2>DNS zones</h2>
<table><thead><tr><th>Zone</th><th class="num">Records</th></tr></thead><tbody>
{% for z in zones %}
<tr><td><a href="/zone/{{ z.key | urlencode }}">{{ z.name }}</a></td><td class="num">{{ z.records }}</td></tr>
{% endfor %}</tbody></table>
<form method="post" action="/apply" class="apply">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<button>Apply changes</button>
<span class="muted">Renders configuration and reloads only what changed — same as <code>fabricctl --apply</code>.</span>
</form></section>{% endblock %}""",

    "zone": """{% extends "base" %}{% block body %}
<p class="crumb"><a href="/">Overview</a> / {{ zone.name }}</p>
<h1>{{ zone.name }}</h1>
<p class="muted">{{ zone.status }}</p>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<section class="card"><h2>Records</h2>
<table><thead><tr><th>Type</th><th>Name</th><th>Value</th><th></th></tr></thead><tbody>
{% for r in zone.records %}
<tr><td><span class="pill">{{ r.type }}</span></td><td>{{ r.name or '(missing)' }}</td><td><code>{{ r.value }}</code></td>
<td class="num"><form method="post" action="/zone/{{ zone.key | urlencode }}/delete">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="type" value="{{ r.type }}">
<input type="hidden" name="index" value="{{ r.index }}"><input type="hidden" name="name" value="{{ r.name }}">
<button class="danger">Delete</button></form></td></tr>
{% endfor %}</tbody></table></section>
<section class="card"><h2>Add record</h2>
<form method="post" action="/zone/{{ zone.key | urlencode }}/add" class="grid">
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
<form method="post" action="/apply" class="apply">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button>Apply changes</button></form>
{% endblock %}""",

    "apply": """{% extends "base" %}{% block body %}
<h1>Apply {{ 'succeeded' if ok else 'failed' }}</h1>
<section class="card"><pre>{{ output }}</pre></section>
<p><a href="/">Back to overview</a></p>{% endblock %}""",

    "audit": """{% extends "base" %}{% block body %}
<h1>Audit log</h1><p class="muted">Newest first. Web and CLI changes both land here.</p>
<section class="card"><pre>{% for line in lines %}{{ line }}{% endfor %}</pre></section>{% endblock %}""",
}
_env.loader = jinja2.DictLoader(_TEMPLATES)


def _render(name, **kw):
    kw.setdefault("ctx", None)
    return _env.get_template(name).render(**kw)


def error_page(status, message):
    return _render("error", status=status, message=message)


def continue_page(target):
    return _render("continue", target=target)


def dashboard(ctx, services, zones):
    return _render("dashboard", ctx=ctx, services=services, zones=zones)


def zone(ctx, zone_detail, types, msg, err):
    return _render("zone", ctx=ctx, zone=zone_detail, types=types, msg=msg, err=err)


def apply_result(ctx, ok, output):
    return _render("apply", ctx=ctx, ok=ok, output=output)


def audit(ctx, lines):
    return _render("audit", ctx=ctx, lines=lines)


def css():
    return """
:root{--bg:#f8fafc;--surface:#fff;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;
--accent:#0369a1;--ok:#15803d;--bad:#b91c1c;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--surface:#1e293b;--border:#334155;
--text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--ok:#4ade80;--bad:#f87171}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;flex-wrap:wrap;align-items:center;gap:16px;padding:12px 16px;border-bottom:1px solid var(--border);background:var(--surface)}
header nav{display:flex;gap:16px;flex:1}
.brand{font-weight:600;color:var(--text);text-decoration:none}
.who{display:flex;gap:8px;align-items:center;color:var(--muted);margin:0}
main{max-width:1000px;margin:0 auto;padding:16px}
footer{max-width:1000px;margin:0 auto;padding:16px;color:var(--muted);font-size:13px}
h1{font-size:22px;margin:8px 0 12px}h2{font-size:16px;margin:0 0 12px}
a{color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 0 16px;overflow-x:auto}
.narrow{max-width:520px;margin:48px auto}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border);vertical-align:middle}
th{color:var(--muted);font-weight:500;font-size:13px}
td form{margin:0}
.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border:1px solid var(--border);border-radius:999px;font-size:12px}
.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.bad{color:var(--bad);border-color:var(--bad)}
.muted,.crumb{color:var(--muted)}
.flash{padding:8px 12px;border-radius:6px;border:1px solid}
.flash.ok{color:var(--ok)}.flash.bad{color:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;align-items:end}
label{display:flex;flex-direction:column;gap:4px;font-size:13px;color:var(--muted)}
input,select{font:inherit;padding:6px 8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
button{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:var(--surface);cursor:pointer}
button.danger{background:transparent;color:var(--bad);border-color:var(--bad);padding:2px 10px}
button.link{background:none;border:none;color:var(--accent);padding:0}
.apply{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:12px}
pre{white-space:pre-wrap;word-break:break-word;margin:0;font-size:13px}
code{font-size:13px}
"""
