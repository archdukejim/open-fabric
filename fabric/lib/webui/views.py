"""HTML rendering for webui. Jinja2 with autoescape; no inline scripts
or styles, so the page works under a strict Content-Security-Policy."""
import base64

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
    "dirsrv": ("389 Directory Server", "Users, groups and organisational units; role accounts; password policy."),
    "freeradius": ("FreeRADIUS 802.1X", "Network access: EAP-TLS device certificates, MAC authentication, "
                                       "VLAN assignment, switches and access points (NAS clients)."),
    "openbao": ("OpenBao", "Seal status and unseal methods (key file, USB key, KMIP, PKCS#11), secrets engines, "
                           "fabric's own secrets, dynamic credentials and the SSH certificate authority."),
}
# BIND9 tab sections: (view, label)
BIND9_SECTIONS = [("forward", "Forward zones"), ("reverse", "Reverse zones"), ("tsig", "TSIG keys")]
# Step-CA tab sub-menu: (view, label)
STEPCA_MENU = [("ca", "Certificate authority"), ("sign", "Sign a CSR"), ("issue", "New key + certificate"),
               ("inspect", "Inspect"), ("convert", "Convert"), ("issued", "Issued")]
STEPCA_VIEWS = {v for v, _ in STEPCA_MENU}
KEY_TYPES = ["RSA-2048", "RSA-3072", "RSA-4096", "EC-P256", "EC-P384"]
TSIG_SCOPES = [("acme-hosts", "Certbot DNS-01 for listed hosts only (TXT)"),
               ("acme-zone", "Certbot DNS-01 for any host in the zone (TXT)"),
               ("any-name", "Any name in the zone, chosen record types")]
TSIG_ANY_TYPES = ["A", "AAAA", "CNAME", "TXT", "SRV", "MX"]

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
{% set ok = services | selectattr(1, 'equalto', 'active') | rejectattr(2, 'in', ['unhealthy', 'starting']) | list | length %}
<h1>Overview</h1>
<p class="muted">{{ ok }} of {{ services | length }} services healthy.</p>
<section class="tiles">
{% for name, state, health in services %}
{% set info = service_info.get(name, (name, None)) %}
{% if state != 'active' or health == 'unhealthy' %}{% set light, why = 'bad', (state if state != 'active' else 'running, health check failing') %}
{% elif health == 'starting' %}{% set light, why = 'warn', 'starting' %}
{% else %}{% set light, why = 'ok', 'running' ~ (', healthy' if health == 'healthy' else '') %}{% endif %}
<div class="tile" title="{{ name }}: {{ why }}">
  <div class="tile-head">
    <span class="light {{ light }}" role="img" aria-label="{{ why }}"></span>
    {% if info[1] %}<a href="/{{ info[1] }}"><strong>{{ name }}</strong></a>{% else %}<strong>{{ name }}</strong>{% endif %}
  </div>
  <div class="muted">{{ info[0] }}{% if light != 'ok' %} · <span class="{{ light }}-text">{{ why }}</span>{% endif %}</div>
</div>
{% endfor %}
</section>
{% endblock %}""",

    "bind9": """{% extends "base" %}{% block body %}
<h1>BIND9 · DNS</h1>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<nav class="sections">
{% for id, label in bind9_sections %}<a href="/bind9{{ '' if id == 'forward' else '?view=' ~ id }}" class="section{{ ' active' if id == section }}">{{ label }}</a>{% endfor %}
</nav>

{% if section == 'forward' %}
{% if forward_zones | length > 1 %}
<div class="picker"><span class="muted">Zone</span>
{% for z in forward_zones %}<a href="/bind9?zone={{ z.key | urlencode }}" class="subtab{{ ' active' if zone and z.key == zone.key }}">{{ z.name }} <span class="muted">{{ z.records }}</span></a>{% endfor %}
</div>
{% endif %}
{% if zone %}
<section class="card"><h2>{{ zone.name }}</h2>
<p class="muted">{{ zone.status }}</p>
<table><thead><tr><th>Type</th><th>Name</th><th>Value</th><th>Reverse (PTR)</th><th></th></tr></thead><tbody>
{% for r in zone.records %}
<tr><td><span class="pill">{{ r.type }}</span></td><td>{{ r.name or '(missing)' }}</td><td><code>{{ r.value }}</code></td>
<td>{% if r.ptr %}<span class="muted small">auto</span> <code class="small">{{ r.ptr }}</code>{% elif r.ptr_note %}<span class="muted small">none — {{ r.ptr_note }}</span>{% endif %}</td>
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
</form>
<p class="muted">A and AAAA records with a private address get their PTR record automatically — see Reverse zones.</p></section>
{% else %}<section class="card"><p class="blank">No forward zones.</p></section>{% endif %}

{% elif section == 'reverse' %}
<section class="card"><h2>Reverse zones</h2>
<p class="muted">Generated from the forward zones: every A and AAAA record with a private address (RFC 1918, 100.64/10, IPv6 ULA) gets a PTR record — one per address, a named host before the zone apex. IPv4 zones are /24, IPv6 zones /64. To change a PTR, change the forward record; Apply publishes both.</p></section>
{% for name, ptrs in reverse.zones.items() %}
<section class="card"><h2>{{ name }} <span class="muted">{{ ptrs | length }}</span></h2>
<table><thead><tr><th>Address</th><th>PTR</th><th>Points to</th><th>From</th></tr></thead><tbody>
{% for r in ptrs %}<tr><td><code>{{ r.ip }}</code></td><td><code class="small">{{ r.label }}</code></td><td>{{ r.target }}</td><td class="muted">{{ r.source }}</td></tr>{% endfor %}
</tbody></table></section>
{% else %}<section class="card"><p class="blank">No reverse zones yet: add an A or AAAA record with a private address.</p></section>
{% endfor %}
{% if manual_reverse %}<section class="card"><h2>Written by hand</h2>
<p class="muted">Defined directly in <code>vars.yaml</code> (<code>dns:</code>); not generated: {{ manual_reverse | map(attribute='name') | join(', ') }}.</p></section>{% endif %}
{% if reverse.skipped %}
<section class="card"><h2>No reverse record</h2>
<table><thead><tr><th>Name</th><th>Address</th><th>Why</th></tr></thead><tbody>
{% for r in reverse.skipped %}<tr><td>{{ r.name }}</td><td><code>{{ r.ip }}</code></td><td class="muted">{{ r.reason }}</td></tr>{% endfor %}
</tbody></table></section>
{% endif %}

{% else %}
<section class="card"><h2>TSIG keys</h2>
<p class="muted">RFC2136 keys for dynamic updates (certbot DNS-01, nginx-proxy-manager). Update rights are deny-by-default; a secret is shown only once, when it is created or replaced.</p>
{% if tsig_keys %}
<table><thead><tr><th>Key</th><th>May update</th><th>Types</th><th>ACLs</th><th></th></tr></thead><tbody>
{% for k in tsig_keys %}
<tr><td><strong>{{ k.name }}</strong><div class="muted small">{{ k.algorithm }}</div></td><td>{{ k.scope }}</td>
<td>{{ k.types }}</td><td>{{ k.acls | join(', ') or '—' }}</td>
<td class="num"><div class="row-actions">
<form method="post" action="/bind9/tsig/{{ k.name | urlencode }}/rotate"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="ghost">New secret</button></form>
<form method="post" action="/bind9/tsig/{{ k.name | urlencode }}/delete"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="danger">Delete</button></form>
</div></td></tr>
{% endfor %}</tbody></table>
{% else %}<p class="blank">No TSIG keys yet.</p>{% endif %}
</section>
<section class="card"><h2>New TSIG key for a zone</h2>
<form method="post" action="/bind9/tsig/create" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Key name<input name="name" required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,62}" placeholder="npm-certbot"></label>
<label>Zone<select name="zone">{% for z in forward_zones %}<option>{{ z.name }}</option>{% endfor %}</select></label>
<label class="wide">May update<select name="scope">{% for v, l in tsig_scopes %}<option value="{{ v }}">{{ l }}</option>{% endfor %}</select></label>
<label class="wide">Hosts (listed-hosts scope)<input name="hosts" placeholder="npm, nas, printer"></label>
<fieldset class="wide"><legend>Record types (any-name scope)</legend>
{% for t in tsig_any_types %}<label class="check"><input type="checkbox" name="type_{{ t }}" value="1"{{ ' checked' if t == 'TXT' }}> {{ t }}</label>{% endfor %}
</fieldset>
<label class="wide">Existing secret (optional — keep a current client working)<input name="secret" type="password" autocomplete="off" placeholder="base64; leave empty to generate"></label>
<div><button>Create key</button></div>
</form></section>
<section class="card"><h2>ACLs and update policies</h2><p class="blank">Left intentionally blank.</p>
<p class="muted">Who may query the zones, and which certbot devices may prove which names (today: <code>fabricctl acl</code>).</p></section>
{% endif %}
<form method="post" action="/apply" class="apply card">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<button>Apply changes</button>
<span class="muted">Publishes zone, reverse-zone and key changes to BIND9 — reloads only what changed (same as <code>fabricctl --apply</code>).</span>
</form>
{% endblock %}""",

    "stepca": """{% extends "base" %}{% block body %}
<h1>Step-CA · PKI</h1>
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<nav class="subtabs">
{% for v, label in menu %}<a href="/stepca?view={{ v }}" class="subtab{{ ' active' if v == view }}">{{ label }}</a>{% endfor %}
</nav>
{% if view == 'ca' %}
{% if ca %}
{% for label, c in (('Root CA', ca.root), ('Intermediate CA', ca.intermediate)) %}
<section class="card"><h2>{{ label }}</h2>
<dl class="kv"><dt>Subject</dt><dd>{{ c.subject }}</dd><dt>Valid until</dt><dd>{{ c.not_after }}</dd>
<dt>Key</dt><dd>{{ c.key }}</dd><dt>SHA-256</dt><dd><code class="fp">{{ c.sha256 }}</code></dd></dl></section>
{% endfor %}
<section class="card"><h2>Trust this CA on a device</h2>
<p>Every format (Windows .cer, Linux .crt, PEM text, DER, .p7b chain) is published over plain HTTP at <a href="{{ ca.certs_url }}">{{ ca.certs_url }}</a>.</p>
<p class="muted">Manually issued certificates: at most {{ ca.max_days }} days (<code>pki_manual_max_days</code>).</p></section>
{% else %}<section class="card"><p class="flash bad">The CA certificates could not be read.</p></section>{% endif %}

{% elif view == 'sign' %}
{% if review %}
<section class="card"><h2>Review the request</h2>
<dl class="kv"><dt>Subject</dt><dd>{{ review.subject or '—' }}</dd>
<dt>Names</dt><dd>{{ review.sans | join(', ') or review.cn }}</dd><dt>Key</dt><dd>{{ review.key }}</dd></dl>
{% if review.ca_requested %}<p class="flash warn">The request asks to be a CA. That is ignored: fabric only issues leaf certificates here.</p>{% endif %}
{% if review.problems %}
<p class="flash bad">This request cannot be signed:</p><ul>{% for p in review.problems %}<li>{{ p }}</li>{% endfor %}</ul>
{% else %}
<form method="post" action="/stepca/sign" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="csr" value="{{ review.pem }}">
<label>Valid for (days)<input name="days" inputmode="numeric" value="{{ [365, ca.max_days if ca else 365] | min }}" required></label>
<div><button>Sign certificate</button></div>
</form>
<p class="muted">Issued as a leaf certificate for server and client authentication, from the fabric intermediate CA.</p>
{% endif %}
<details><summary>Decoded request</summary><pre>{{ review.text }}</pre></details>
</section>
{% endif %}
<section class="card"><h2>Sign a certificate signing request</h2>
<p class="muted">For devices that make their own key (switches, printers, appliances, Windows <code>certreq</code>, <code>openssl req</code>). The private key never leaves the device.</p>
<form method="post" action="/stepca/sign/review" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Upload a CSR (.csr, .req, .pem or DER)<input type="file" name="csr_file" accept=".csr,.req,.pem,.der,.txt"></label>
<label>…or paste it<textarea name="csr" rows="8" placeholder="-----BEGIN CERTIFICATE REQUEST-----"></textarea></label>
<div><button>Review</button></div>
</form></section>

{% elif view == 'issue' %}
<section class="card"><h2>New private key and certificate</h2>
<p class="muted">For devices that cannot make a CSR. The key is generated here, shown once for download (PEM and a password-protected .p12) and not kept.</p>
<form method="post" action="/stepca/issue" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Name (CN)<input name="cn" required placeholder="printer.home.arpa"></label>
<label class="wide">Other names (DNS, IP, e-mail; comma or space separated)<input name="sans" placeholder="printer, 192.168.1.40"></label>
<label>Key type<select name="key_type">{% for k in key_types %}<option{{ ' selected' if k == 'RSA-2048' }}>{{ k }}</option>{% endfor %}</select></label>
<label>Valid for (days)<input name="days" inputmode="numeric" value="{{ [365, ca.max_days if ca else 365] | min }}" required></label>
<div><button>Generate</button></div>
</form>
<p class="muted">RSA-2048 is the most widely accepted by older devices; EC keys are smaller and faster where supported.</p></section>

{% elif view == 'inspect' %}
{% if inspected %}
{% for item in inspected['items'] %}
<section class="card"><h2>{{ 'Certificate' if inspected.kind == 'cert' else 'Certificate signing request' }}{% if inspected['items'] | length > 1 %} {{ loop.index }}{% endif %}</h2>
{% if item.trusted is not none %}<p><span class="pill {{ 'ok' if item.trusted else 'warn' }}">{{ 'issued by this fabric' if item.trusted else 'not issued by this fabric (or incomplete chain)' }}</span></p>{% endif %}
<dl class="kv"><dt>Subject</dt><dd>{{ item.info.subject or '—' }}</dd>
{% if item.info.issuer %}<dt>Issuer</dt><dd>{{ item.info.issuer }}</dd>{% endif %}
<dt>Names</dt><dd>{{ item.info.sans | join(', ') or '—' }}</dd><dt>Key</dt><dd>{{ item.info.key }}</dd>
{% if item.info.not_after %}<dt>Valid</dt><dd>{{ item.info.not_before }} → {{ item.info.not_after }}</dd>
<dt>Usage</dt><dd>{{ item.info.usage or '—' }}{{ ' · CA' if item.info.is_ca }}</dd>
<dt>Serial</dt><dd><code class="fp">{{ item.info.serial }}</code></dd><dt>SHA-256</dt><dd><code class="fp">{{ item.info.sha256 }}</code></dd>{% endif %}
</dl>
{% if item.info.problems %}<p class="flash bad">Would be refused for signing: {{ item.info.problems | join('; ') }}</p>{% endif %}
<details><summary>Full decode</summary><pre>{{ item.text }}</pre></details></section>
{% endfor %}
{% endif %}
<section class="card"><h2>Inspect a certificate or CSR</h2>
<p class="muted">Decodes PEM, DER or base64: subject, names, validity, usages, fingerprints, and whether this fabric issued it. Private keys are refused unread.</p>
<form method="post" action="/stepca/inspect" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Upload (.crt, .cer, .pem, .der, .csr)<input type="file" name="file"></label>
<label>…or paste<textarea name="data" rows="8" placeholder="-----BEGIN CERTIFICATE-----"></textarea></label>
<div><button>Inspect</button></div>
</form></section>

{% elif view == 'convert' %}
<section class="card"><h2>Convert a certificate</h2>
<p class="muted">Get a certificate as PEM (.crt), DER (.cer), full chain (.pem / .p7b) — and, with its private key, a password-protected .p12 for Windows, macOS and phones. The key is not kept.</p>
<form method="post" action="/stepca/convert" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Certificate (upload)<input type="file" name="cert_file"></label>
<label>…or paste<textarea name="cert" rows="6" placeholder="-----BEGIN CERTIFICATE-----"></textarea></label>
<label>Private key for a .p12 (optional, unencrypted PEM; upload)<input type="file" name="key_file"></label>
<label>…or paste<textarea name="key" rows="4" placeholder="-----BEGIN PRIVATE KEY-----" autocomplete="off"></textarea></label>
<div><button>Convert</button></div>
</form></section>

{% elif view == 'issued' %}
<section class="card"><h2>Issued by hand</h2>
<p class="muted">Certificates signed from a CSR or generated here (newest first). Service certificates are managed by setup and not listed.</p>
{% if issued %}
<table><thead><tr><th>Subject</th><th>Names</th><th>How</th><th>Expires</th><th>By</th></tr></thead><tbody>
{% for c in issued %}
<tr><td>{{ c.subject }}</td><td>{{ (c.sans or []) | join(', ') }}</td><td>{{ 'CSR' if c.kind == 'csr' else 'key + cert' }}</td>
<td><span class="pill {{ 'ok' if c.status == 'valid' else ('warn' if c.status == 'expires soon' else 'bad') }}">{{ c.status }}</span> <span class="muted">{{ c.not_after }}</span></td>
<td>{{ c.actor }} <span class="muted">{{ c.when }}</span></td></tr>
{% endfor %}</tbody></table>
{% else %}<p class="blank">Nothing issued by hand yet.</p>{% endif %}
</section>
{% endif %}
{% endblock %}""",

    "pki_result": """{% extends "base" %}{% block body %}
<h1>{{ title }}</h1>
{% if r.key %}<p class="flash warn">This page is the only copy of the private key. It is not stored anywhere — download it now.</p>{% endif %}
<section class="card"><h2>{{ r.info.subject }}</h2>
<dl class="kv"><dt>Names</dt><dd>{{ r.info.sans | join(', ') or '—' }}</dd><dt>Key</dt><dd>{{ r.info.key }}</dd>
<dt>Valid</dt><dd>{{ r.info.not_before }} → {{ r.info.not_after }}</dd>
<dt>Serial</dt><dd><code class="fp">{{ r.info.serial }}</code></dd><dt>SHA-256</dt><dd><code class="fp">{{ r.info.sha256 }}</code></dd></dl>
</section>
<section class="card"><h2>Download</h2>
<ul class="downloads">
{% for fname, mime, data, what in files %}
<li><a class="btn" href="data:{{ mime }};base64,{{ data }}" download="{{ fname }}">{{ fname }}</a> <span class="muted">{{ what }}</span></li>
{% endfor %}
</ul>
{% if r.p12_password %}<p>.p12 password: <code class="secret">{{ r.p12_password }}</code> <span class="muted">(shown once)</span></p>{% endif %}
</section>
<section class="card"><h2>Certificate (PEM)</h2><textarea readonly rows="10">{{ r.cert }}</textarea></section>
{% if r.fullchain %}<section class="card"><h2>Full chain (PEM)</h2><textarea readonly rows="10">{{ r.fullchain }}</textarea></section>{% endif %}
{% if r.key %}<section class="card"><h2>Private key (PEM)</h2><textarea readonly rows="8">{{ r.key }}</textarea></section>{% endif %}
<p><a href="/stepca?view={{ back }}">Back</a></p>
{% endblock %}""",

    "tsig_result": """{% extends "base" %}{% block body %}
<h1>TSIG key {{ key_name }} {{ action }}</h1>
<p class="flash warn">The secret is shown only now. Put it in the client, then Apply to publish the key to BIND9.</p>
<section class="card"><h2>Secret</h2><p><code class="secret">{{ secret }}</code></p></section>
<section class="card"><h2>RFC2136 client settings (certbot / nginx-proxy-manager)</h2>
<textarea readonly rows="9">{{ ini }}</textarea>
<p><a class="btn" href="data:text/plain;base64,{{ ini_b64 }}" download="{{ key_name }}-rfc2136.ini">{{ key_name }}-rfc2136.ini</a></p>
</section>
<form method="post" action="/apply" class="apply card">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button>Apply changes</button>
<span class="muted">Until applied, BIND9 does not know this {{ 'key' if action == 'created' else 'secret' }}.</span></form>
<p><a href="/bind9?view=tsig">Back to TSIG keys</a></p>
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


def bind9(ctx, section, zones, zone=None, types=(), msg="", err="", tsig_keys=None, reverse=None):
    """section: forward (zone records) | reverse (generated PTRs) | tsig."""
    return _render("bind9", ctx=ctx, tab="bind9", section=section, bind9_sections=BIND9_SECTIONS,
                   forward_zones=[z for z in zones if not z.get("reverse")],
                   manual_reverse=[z for z in zones if z.get("reverse")], zone=zone, types=types, msg=msg,
                   err=err, tsig_keys=tsig_keys, reverse=reverse or {"zones": {}, "skipped": []},
                   tsig_scopes=TSIG_SCOPES, tsig_any_types=TSIG_ANY_TYPES)


def stepca(ctx, view, ca, issued=None, review=None, inspected=None, err=""):
    return _render("stepca", ctx=ctx, tab="stepca", view=view, menu=STEPCA_MENU, ca=ca, issued=issued,
                   review=review, inspected=inspected, err=err, key_types=KEY_TYPES)


def _b64(text):
    return base64.b64encode(text.encode()).decode()


def pki_result(ctx, kind, r):
    """kind: sign | issue | convert. Files are offered as data: downloads, so
    nothing (least of all a private key) is kept server-side for a later GET."""
    n = r["name"]
    files = [(f"{n}.crt", "application/x-x509-ca-cert", _b64(r["cert"]), "certificate, PEM (Linux, most devices)"),
             (f"{n}.cer", "application/pkix-cert", r["der_b64"], "certificate, DER (Windows)"),
             (f"{n}-fullchain.pem", "application/x-pem-file", _b64(r["fullchain"]),
              "certificate + CA chain, PEM (web servers)")]
    if r.get("p7b_b64"):
        files.append((f"{n}.p7b", "application/x-pkcs7-certificates", r["p7b_b64"], "certificate + chain, PKCS#7"))
    if r.get("key"):
        files.append((f"{n}.key", "application/x-pem-file", _b64(r["key"]), "private key, PEM (unencrypted)"))
    if r.get("p12_b64"):
        files.append((f"{n}.p12", "application/x-pkcs12", r["p12_b64"], "certificate + key + chain, PKCS#12"))
    title = {"sign": "Certificate signed", "issue": "Key and certificate generated",
             "convert": "Certificate converted"}[kind]
    return _render("pki_result", ctx=ctx, tab="stepca", title=title, r=r, files=files, back=kind)


def tsig_result(ctx, name, secret, ini, action):
    return _render("tsig_result", ctx=ctx, tab="bind9", key_name=name, secret=secret, ini=ini, ini_b64=_b64(ini),
                   action=action)


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
.tile-head{display:flex;align-items:center;gap:10px}
.light{flex:none;width:10px;height:10px;border-radius:50%;background:var(--muted)}
.light.ok{background:var(--ok);box-shadow:0 0 6px var(--ok)}.light.warn{background:var(--warn);box-shadow:0 0 6px var(--warn)}
.light.bad{background:var(--bad);box-shadow:0 0 6px var(--bad)}
.bad-text{color:var(--bad)}.warn-text{color:var(--warn)}
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
.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:0 0 8px}
.kv dt{color:var(--muted);font-size:13px}.kv dd{margin:0;word-break:break-word}
.fp{word-break:break-all}
.secret{font-size:14px;padding:2px 6px;border:1px dashed var(--warn);border-radius:4px;word-break:break-all}
.flash.warn{color:var(--warn)}
.stack{display:flex;flex-direction:column;gap:12px}
.wide{grid-column:1/-1}
fieldset{border:1px solid var(--border);border-radius:6px;display:flex;flex-wrap:wrap;gap:12px;padding:8px 12px}
legend{font-size:13px;color:var(--muted)}
label.check{flex-direction:row;align-items:center;gap:6px;color:var(--text)}
textarea{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text)}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent)}
.downloads{list-style:none;padding:0;margin:0 0 8px;display:flex;flex-direction:column;gap:8px}
.btn{display:inline-block;padding:4px 12px;border:1px solid var(--accent);border-radius:6px;text-decoration:none}
button.ghost{background:transparent;color:var(--accent);padding:2px 10px}
.row-actions{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
.sections{display:flex;gap:4px;border-bottom:1px solid var(--border);margin:0 0 16px;overflow-x:auto}
.section{flex:none;padding:8px 12px;color:var(--muted);text-decoration:none;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap}
.section:hover{color:var(--text)}.section.active{color:var(--text);border-bottom-color:var(--accent);font-weight:600}
.picker{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px}
.small{font-size:12px}
.devbanner{margin:0;padding:8px 16px;text-align:center;font-weight:600;background:#b45309;color:#fff}
"""
