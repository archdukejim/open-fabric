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
    "freeradius": ("FreeRADIUS 802.1X", "Network access: EAP-TLS device certificates, MAC authentication, "
                                       "VLAN assignment, switches and access points (NAS clients)."),
}
# BIND9 tab sections: (view, label)
BIND9_SECTIONS = [("forward", "Forward zones"), ("reverse", "Reverse zones"), ("tsig", "TSIG keys")]
# OpenBao tab sections and unlock-method (key slot) types
OPENBAO_SECTIONS = [("status", "Status"), ("unlock", "Unlock methods"), ("secrets", "Secrets"),
                    ("disk", "Disk encryption")]
OPENBAO_VIEWS = {"status", "unlock", "secrets", "disk", "add-security-key", "add-usb", "add-hsm", "rotate", "remove"}
SLOT_TYPES = {
    "local": ("Key file", "On this host's disk. Always present, so no kill switch."),
    "pkcs11": ("Security key", "YubiKey, Nitrokey, SmartCard-HSM or any PKCS#11 token. The key can't be copied."),
    "kmip": ("HSM / key manager", "Any KMIP server on your network. Revoke fabric there to lock the vault."),
    "security-key": ("Security key", "YubiKey, Nitrokey, SmartCard-HSM or any PKCS#11 token. The key can't be copied."),
    "usb": ("USB stick", "A plain or keypad-encrypted stick. Cheap; a plain stick can be copied."),
    "hsm": ("HSM / key manager", "Any KMIP server on your network. Revoke fabric there to lock the vault."),
}
# 389-DS tab sections: (view, label)
DIRSRV_SECTIONS = [("devices", "Devices"), ("roles", "Roles"), ("people", "People")]
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
    "freeradius": ("802.1X", "freeradius"), "fabric-web": ("This web UI", None), "fabric-agent": ("Host API", None),
}

_BASE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Fabric · web control{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css"></head>
<body>
<header>
  <a class="brand" href="/">Fabric <span class="subtitle">web control</span></a>
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
<td class="num">{% if can('dns:write') %}<form method="post" action="/bind9/zone/{{ zone.key | urlencode }}/delete">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="type" value="{{ r.type }}">
<input type="hidden" name="index" value="{{ r.index }}"><input type="hidden" name="name" value="{{ r.name }}">
<button class="danger">Delete</button></form>{% endif %}</td></tr>
{% endfor %}</tbody></table></section>
<section class="card"><h2>Add record</h2>
{% if can('dns:write') %}<form method="post" action="/bind9/zone/{{ zone.key | urlencode }}/add" class="grid">
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
</form>{% endif %}
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
{% if can('tsig:manage') %}<form method="post" action="/bind9/tsig/{{ k.name | urlencode }}/rotate"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="ghost">New secret</button></form>{% endif %}
{% if can('tsig:manage') %}<form method="post" action="/bind9/tsig/{{ k.name | urlencode }}/delete"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="danger">Delete</button></form>{% endif %}
</div></td></tr>
{% endfor %}</tbody></table>
{% else %}<p class="blank">No TSIG keys yet.</p>{% endif %}
</section>
<section class="card"><h2>New TSIG key for a zone</h2>
{% if can('tsig:manage') %}<form method="post" action="/bind9/tsig/create" class="grid">
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
</form>{% endif %}</section>
<section class="card"><h2>ACLs and update policies</h2><p class="blank">Left intentionally blank.</p>
<p class="muted">Who may query the zones, and which certbot devices may prove which names (today: <code>fabricctl acl</code>).</p></section>
{% endif %}
{% if can('dns:write') %}<form method="post" action="/apply" class="apply card">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<button>Apply changes</button>
<span class="muted">Publishes zone, reverse-zone and key changes to BIND9 — reloads only what changed (same as <code>fabricctl --apply</code>).</span>
</form>{% endif %}
{% endblock %}""",

    "dirsrv": """{% extends "base" %}{% from "dirsrv_macros" import device_fields, role_fields with context %}{% block body %}
<h1>389-DS · Directory</h1>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<nav class="sections">
{% for id, label in sections %}<a href="/dirsrv?view={{ id }}" class="section{{ ' active' if id == section }}">{{ label }}</a>{% endfor %}
</nav>
{% if unavailable %}<section class="card"><p class="flash bad">The directory could not be read: {{ unavailable }}</p></section>

{% elif view == 'devices' %}
<section class="card"><h2>Devices <span class="muted">{{ data.devices | length }}</span></h2>
<p class="muted">What a device may do comes from its roles. A disabled device gets nothing, whatever its roles say.</p>
{% if data.devices %}
<table><thead><tr><th></th><th>Device</th><th>Type</th><th>MAC</th><th>Owner</th><th>Roles</th><th>Access</th></tr></thead><tbody>
{% for d in data.devices %}
<tr><td><span class="light {{ 'ok' if d.enabled else 'bad' }}" role="img" aria-label="{{ 'enabled' if d.enabled else 'disabled' }}" title="{{ 'enabled' if d.enabled else 'disabled' }}"></span></td>
<td><a href="/dirsrv?view=device&name={{ d.name | urlencode }}"><strong>{{ d.name }}</strong></a>{% if d.description %}<div class="muted small">{{ d.description }}</div>{% endif %}</td>
<td>{{ d.type }}</td><td><code class="small">{{ d.macs | join(' ') or '—' }}</code></td><td>{{ d.owner or '—' }}</td>
<td>{{ d.roles | join(', ') or '—' }}</td>
<td class="small">{% if not d.enabled %}<span class="bad-text">disabled</span>{% else %}{% if d.vlan %}VLAN {{ d.vlan }} · {% endif %}{{ d.permissions | length }} permission{{ '' if d.permissions | length == 1 else 's' }}{% endif %}{% if d.certs %} · {{ d.certs | length }} cert{{ '' if d.certs | length == 1 else 's' }}{% endif %}</td></tr>
{% endfor %}</tbody></table>
{% else %}<p class="blank">No devices yet.</p>{% endif %}
</section>
<section class="card"><h2>Add a device</h2>
{% set d = {'enabled': True, 'roles': [], 'macs': [], 'type': 'laptop'} %}
{% if can('devices:enroll') %}<form method="post" action="/dirsrv/devices/_new" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Name<input name="name" required pattern="[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?" placeholder="jims-laptop"></label>
{{ device_fields(d) }}
<div><button>Add device</button></div>
</form>{% endif %}</section>

{% elif view == 'device' %}
{% set d = device %}
<p><a href="/dirsrv?view=devices">← Devices</a></p>
<section class="card"><h2><span class="light {{ 'ok' if d.enabled else 'bad' }}"></span> {{ d.name }}</h2>
<dl class="kv"><dt>Roles</dt><dd>{{ d.roles | join(', ') or '—' }}</dd>
<dt>VLAN</dt><dd>{{ d.vlan or '—' }}{% if d.vlan %} <span class="muted">(from role {{ d.vlan_from }})</span>{% endif %}</dd>
<dt>May</dt><dd>{% for p in d.permissions %}<div>{{ data.permissions[p][0] }} <span class="muted small">· {{ p }}</span></div>{% else %}{{ 'nothing — disabled' if not d.enabled else 'nothing (no role grants anything)' }}{% endfor %}</dd></dl>
</section>
<section class="card"><h2>Edit</h2>
{% if can('devices:admin') %}<form method="post" action="/dirsrv/devices/{{ d.name | urlencode }}" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
{{ device_fields(d) }}
<div><button>Save</button></div>
</form>{% endif %}</section>
<section class="card"><h2>Certificates</h2>
<p class="muted">Certificates issued to this device (by SHA-256 fingerprint). 802.1X EAP-TLS will accept these for this device.</p>
{% if d.certs %}<table><tbody>{% for fp in d.certs %}
<tr><td><code class="fp small">{{ fp }}</code></td><td class="num">{% if can('pki:link-device') %}<form method="post" action="/dirsrv/devices/{{ d.name | urlencode }}/certs/unlink">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="sha256" value="{{ fp }}"><button class="danger">Unlink</button></form>{% endif %}</td></tr>
{% endfor %}</tbody></table>{% else %}<p class="blank">None linked.</p>{% endif %}
<p><a class="btn" href="/stepca?view=issue&device={{ d.name | urlencode }}">Generate key + certificate</a>
<a class="btn" href="/stepca?view=sign&device={{ d.name | urlencode }}">Sign its CSR</a></p>
</section>
{% if can('devices:admin') %}<form method="post" action="/dirsrv/devices/{{ d.name | urlencode }}/delete" class="card apply">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="danger">Delete device</button>
<span class="muted">Removes it from every role. Its certificates stay valid until they expire.</span></form>{% endif %}

{% elif view == 'roles' %}
<section class="card"><h2>Roles <span class="muted">{{ data.roles | length }}</span></h2>
<p class="muted">A role grants its devices permissions and, optionally, a VLAN. With several roles, permissions add up and the VLAN comes from the role with the lowest priority number.</p>
{% if data.roles %}
<table><thead><tr><th>Role</th><th>Priority</th><th>VLAN</th><th>Grants</th><th>Devices</th></tr></thead><tbody>
{% for r in data.roles %}
<tr><td><a href="/dirsrv?view=role&name={{ r.name | urlencode }}"><strong>{{ r.name }}</strong></a>{% if r.description %}<div class="muted small">{{ r.description }}</div>{% endif %}</td>
<td>{{ r.priority }}</td><td>{{ r.vlan or '—' }}</td><td class="small">{{ r.permissions | join(', ') or '—' }}</td><td>{{ r.members | length }}</td></tr>
{% endfor %}</tbody></table>
{% else %}<p class="blank">No roles yet.</p>{% endif %}
</section>
<section class="card"><h2>New role</h2>
{% if can('roles:admin') %}<form method="post" action="/dirsrv/roles/_new" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Name<input name="name" required pattern="[a-z0-9][a-z0-9_-]{0,62}" placeholder="iot"></label>
{{ role_fields({'permissions': [], 'priority': 100}) }}
<div><button>Create role</button></div>
</form>{% endif %}</section>

{% elif view == 'role' %}
{% set r = role %}
<p><a href="/dirsrv?view=roles">← Roles</a></p>
<section class="card"><h2>{{ r.name }}</h2>
<p class="muted">Devices: {% for m in r.members %}<a href="/dirsrv?view=device&name={{ m | urlencode }}">{{ m }}</a>{{ ', ' if not loop.last }}{% else %}none{% endfor %} — add or remove devices from each device's page.</p>
{% if can('roles:admin') %}<form method="post" action="/dirsrv/roles/{{ r.name | urlencode }}" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
{{ role_fields(r) }}
<div><button>Save</button></div>
</form>{% endif %}</section>
{% if can('roles:admin') %}<form method="post" action="/dirsrv/roles/{{ r.name | urlencode }}/delete" class="card apply">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="danger">Delete role</button>
<span class="muted">Only possible once no device is in it.</span></form>{% endif %}

{% elif view == 'people' %}
<section class="card"><h2>People <span class="muted">{{ people.users | length }}</span></h2>
<p class="muted">Accounts live in Keycloak, which writes them here. New people join the plain <code>users</code> group; fabric roles come from the fabric groups (admins, auditors, operators, helpdesk), which an administrator manages in <a href="{{ people.keycloak_url }}">the Keycloak admin console</a>.</p>
{% if people.users %}
<table><thead><tr><th></th><th>User</th><th>Name</th><th>E-mail</th><th>Groups</th><th></th></tr></thead><tbody>
{% for u in people.users %}<tr><td><span class="light {{ 'bad' if u.locked else 'ok' }}" title="{{ 'locked' if u.locked else 'active' }}"></span></td>
<td>{{ u.uid }}</td><td>{{ u.name }}</td><td>{{ u.mail or '—' }}</td><td>{{ u.groups | join(', ') or '—' }}</td>
<td class="num">{% if can('people:reset') %}<form method="post" action="/dirsrv/people/{{ u.uid | urlencode }}/reset"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="ghost" title="new one-time password, TOTP enrolled again, sessions ended">Reset sign-in</button></form>{% endif %}</td></tr>{% endfor %}
</tbody></table>{% else %}<p class="blank">No users.</p>{% endif %}
</section>
{% if can('people:create') %}<section class="card"><h2>Add a person</h2>
<form method="post" action="/dirsrv/people/_new" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>User name<input name="uid" required pattern="[a-z][a-z0-9._-]{1,31}" placeholder="jsmith"></label>
<label>E-mail<input name="email" type="email" required></label>
<label>First name<input name="first" required maxlength="60"></label>
<label>Last name<input name="last" required maxlength="60"></label>
<div><button>Add</button></div>
</form>
<p class="muted small">They get a one-time password (shown once) and must choose their own and set up two-factor at the first sign-in. To use this web UI they also need a client certificate: <code>sudo fabricctl client-cert &lt;user&gt;</code>.</p>
</section>{% endif %}
<section class="card"><h2>Groups</h2>
<table><thead><tr><th>Group</th><th>Members</th></tr></thead><tbody>
{% for g in people.groups %}<tr><td>{{ g.name }}</td><td>{{ g.members }}</td></tr>{% endfor %}
</tbody></table></section>
{% endif %}
{% endblock %}""",

    "person_result": """{% extends "base" %}
{% block body %}
<h1>389-DS · Directory</h1>
<p><a href="/dirsrv?view=people">← People</a></p>
<section class="card"><h2>{{ uid }}: {{ 'created' if what == 'created' else 'sign-in reset' }}</h2>
<p>One-time password — <strong>shown only now</strong>, stored nowhere:</p>
<pre class="secret">{{ password }}</pre>
<p class="muted">Give it to {{ uid }} over a safe channel. At the next sign-in they choose their own password and set up two-factor (TOTP){{ '; their previous sessions were ended' if what == 'reset' else '' }}.</p>
</section>
{% endblock %}""",

    "kea": """{% extends "base" %}
{% block body %}
<h1>Kea · DHCP <span class="opt">optional</span></h1>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
{% if not d.enabled %}
<section class="card"><h2>DHCP is off</h2>
<p class="muted">Kea 3.0 LTS hands out addresses on your LAN and registers clients' hostnames in their own DNS zone (<code>dhcp.&lt;domain&gt;</code>). Turn it on in <code>vars.yaml</code> and re-run setup:</p>
<pre>install_kea: true
dhcp:
  interfaces: [eth0]
  subnets:
    - subnet: 192.168.4.0/22
      pools: ["192.168.5.100 - 192.168.5.200"]
      routers: 192.168.4.1</pre></section>
{% else %}
<section class="card"><h2>Subnets</h2>
<p class="muted">Serving on {{ d.interfaces | join(', ') }} · lease {{ d.lease_time }} s{% if d.ddns_zone %} · hostnames registered in <code>{{ d.ddns_zone }}</code>{% endif %}</p>
<table><thead><tr><th>Subnet</th><th>Pools</th><th>Router</th><th>Reservations</th></tr></thead><tbody>
{% for s in d.subnets %}<tr><td>{{ s.subnet }}</td><td>{{ (s.pools or []) | join(', ') }}</td><td>{{ s.routers or '—' }}</td><td class="num">{{ (s.reservations or []) | length }}</td></tr>{% endfor %}
</tbody></table></section>
<section class="card"><h2>Reservations</h2>
<table><thead><tr><th>MAC</th><th>Address</th><th>Hostname</th><th></th></tr></thead><tbody>
{% for s in d.subnets %}{% for r in s.reservations or [] %}<tr><td><code>{{ r.mac }}</code></td><td>{{ r.ip }}</td><td>{{ r.hostname or '—' }}</td>
<td class="num">{% if can('dhcp:write') %}<form method="post" action="/kea/reservations/{{ r.mac | urlencode }}/delete"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="ghost">Remove</button></form>{% endif %}</td></tr>{% endfor %}{% endfor %}
</tbody></table>
{% if can('dhcp:write') %}<form method="post" action="/kea/reservations" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>MAC<input name="mac" required placeholder="aa:bb:cc:dd:ee:ff"></label>
<label>Address (inside a subnet, outside its pools)<input name="ip" required placeholder="192.168.4.20"></label>
<label>Hostname (optional)<input name="hostname" placeholder="printer"></label>
<div><button>Reserve</button></div>
</form>
<p class="muted small">Saved and applied at once; the client gets the address at its next renewal.</p>{% endif %}
</section>
<section class="card"><h2>Leases <span class="muted">{{ d.leases | length }}</span></h2>
{% if d.leases_error %}<p class="flash warn">{{ d.leases_error }}</p>{% endif %}
{% if d.leases %}<table><thead><tr><th>Address</th><th>MAC</th><th>Hostname</th><th>Expires</th><th>State</th></tr></thead><tbody>
{% for l in d.leases %}<tr><td>{{ l.ip }}</td><td><code>{{ l.mac }}</code></td><td>{{ l.hostname or '—' }}</td><td>{{ l.expires }}</td><td>{{ l.state }}</td></tr>{% endfor %}
</tbody></table>{% elif not d.leases_error %}<p class="blank">No leases yet.</p>{% endif %}
</section>
{% endif %}
{% endblock %}""",

    "dirsrv_macros": """{% macro device_fields(d) %}
<label>Type<select name="type">{% for t in data.types %}<option{{ ' selected' if t == d.type }}>{{ t }}</option>{% endfor %}</select></label>
<label>Owner (username, optional)<input name="owner" value="{{ d.owner or '' }}" placeholder="jim"></label>
<label class="wide">MAC addresses (space or comma separated)<input name="macs" value="{{ d.macs | join(' ') }}" placeholder="aa:bb:cc:dd:ee:ff"></label>
<label class="wide">Description<input name="description" value="{{ d.description or '' }}" maxlength="200"></label>
<fieldset class="wide"><legend>Roles</legend>
{% for r in data.roles %}<label class="check"><input type="checkbox" name="role_{{ r.name }}" value="1"{{ ' checked' if r.name in d.roles }}> {{ r.name }}</label>{% else %}<span class="muted">No roles yet — <a href="/dirsrv?view=roles">create one</a>.</span>{% endfor %}
</fieldset>
<label class="check"><input type="checkbox" name="enabled" value="1"{{ ' checked' if d.enabled }}> Enabled</label>
{% endmacro %}
{% macro role_fields(r) %}
<label>Priority (lower wins)<input name="priority" inputmode="numeric" value="{{ r.priority }}"></label>
<label>VLAN (optional)<input name="vlan" inputmode="numeric" value="{{ r.vlan or '' }}" placeholder="30"></label>
<label class="wide">Description<input name="description" value="{{ r.description or '' }}" maxlength="200"></label>
<fieldset class="wide"><legend>Grants</legend>
{% for p, info in data.permissions.items() %}<label class="check perm"><input type="checkbox" name="perm_{{ p }}" value="1"{{ ' checked' if p in r.permissions }}> {{ info[0] }} <span class="muted small">· enforced by {{ info[1] }} once installed</span></label>{% endfor %}
</fieldset>
{% endmacro %}""",

    "openbao": """{% extends "base" %}{% block body %}
<h1>OpenBao · Secrets</h1>
{% if msg %}<p class="flash ok">{{ msg }}</p>{% endif %}
{% if err %}<p class="flash bad">{{ err }}</p>{% endif %}
<nav class="sections">
{% for id, label in sections %}<a href="/openbao{{ '' if id == 'status' else '?view=' ~ id }}" class="section{{ ' active' if id == section }}">{{ label }}</a>{% endfor %}
</nav>
{% set light = 'bad' if not s.reachable or s.sealed or not s.initialized else ('warn' if not s.key.ok else 'ok') %}

{% if view == 'status' %}
<section class="card"><h2><span class="light {{ light }}"></span>
{% if not s.reachable %}Unreachable{% elif not s.initialized %}Not initialised{% elif s.sealed %}Sealed{% else %}Unsealed{% endif %}</h2>
{% if s.error %}<p class="flash bad">{{ s.error }}</p>{% endif %}
<dl class="kv">
{% if s.reachable %}<dt>Version</dt><dd>OpenBao {{ s.version }}</dd>
<dt>Seal</dt><dd>{{ s.seal_type }}{% if s.seal_type == 'static' %} — unlocked at start by one of its <a href="/openbao?view=unlock">unlock methods</a>{% endif %}</dd>
<dt>Storage</dt><dd>{{ s.storage }}</dd>
<dt>fabric's secrets</dt><dd>{% if s.secrets %}in OpenBao — <code class="small">fabric/secrets</code>, version {{ s.secrets.version }}, updated {{ s.secrets.updated }}{% else %}<span class="warn-text">still in a file on disk</span> — moved in by the next <code>fabricctl setup</code>{% endif %}</dd>{% endif %}
<dt>Address</dt><dd><a href="{{ s.url }}ui/">{{ s.url }}</a> <span class="muted">(OpenBao's own UI and API)</span></dd>
</dl></section>
{% if s.mounts %}
<section class="card"><h2>Secret engines</h2>
<table><thead><tr><th>Path</th><th>Type</th><th>What for</th></tr></thead><tbody>
{% for m in s.mounts %}<tr><td><code>{{ m.path }}</code></td><td>{{ m.type }}{% if m.version %} v{{ m.version }}{% endif %}</td><td class="muted">{{ m.description }}</td></tr>{% endfor %}
</tbody></table>
<p class="muted">Sign-in methods: {{ s.auth | join(', ') or '—' }}. fabric-setup and fabric-agent use AppRoles bound to this host; the initial root token was revoked.</p></section>
{% endif %}

{% elif view == 'unlock' %}
{% set removable = slots | rejectattr('type', 'equalto', 'local') | list %}
{% set has_local = slots | selectattr('type', 'equalto', 'local') | list | length > 0 %}
<section class="card"><h2>Unlock methods <span class="muted">{{ slots | length }}</span></h2>
<p class="muted">OpenBao has one vault key. Each method below holds its own protected copy; <strong>any one</strong> of them present at start unlocks the vault. None present: the vault stays locked and everything else keeps running.</p>
<p><span class="light {{ 'warn' if has_local else ('ok' if removable else 'bad') }}"></span>
{% if has_local %} <strong>Kill switch off</strong> — the key file on this host always unlocks the vault; removing a device changes nothing.
{% elif removable %} <strong>Kill switch armed</strong> — removing the last present device locks the vault.
{% else %} No unlock methods.{% endif %}</p>
{% if slots %}
<table><thead><tr><th></th><th>Method</th><th>Device</th><th>Key</th><th>Added</th><th></th></tr></thead><tbody>
{% for sl in slots %}
<tr><td><span class="light {{ 'ok' if sl.present else 'bad' }}" title="{{ 'present now' if sl.present else 'not present' }}"></span></td>
<td><strong>{{ slot_types[sl.type][0] }}</strong><div class="muted small">{{ sl.label }}</div>{% if sl.tested %}<div class="muted small">tested: {{ sl.tested }}</div>{% endif %}</td>
<td><code class="small">{{ sl.device }}</code>{% if sl.detail %}<div class="muted small">{{ sl.detail }}</div>{% endif %}</td>
<td><code class="small">{{ sl.key_id }}</code></td><td class="small">{{ sl.added }}</td>
<td class="num"><div class="row-actions">
{% if can('vault:unlock') %}<form method="post" action="/openbao/slots/{{ sl.id | urlencode }}/test"><input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button class="ghost"{{ '' if live else ' disabled' }}>Test</button></form>{% endif %}
<a class="btn danger-link{{ '' if live and slots | length > 1 else ' disabled' }}" href="/openbao?view=remove&slot={{ sl.id | urlencode }}">Remove</a>
</div></td></tr>
{% endfor %}</tbody></table>
{% endif %}
</section>
{% if has_local and removable %}<p class="flash warn">A device slot works, but the key file on this host still unlocks the vault on its own: anyone with this disk needs nothing else. <a href="/openbao?view=remove&slot=local">Remove the key file</a>.</p>
{% elif removable | length == 1 and not has_local %}<p class="flash warn">Only one device can unlock this vault. If it is lost or breaks, the vault's data is gone — OpenBao's recovery keys cannot decrypt it. Add a second one for your safe.</p>{% endif %}
<section class="card"><h2>Add an unlock method</h2>
{% if add_live | select | list | length < 3 %}<p class="muted">Each type says what it was tested against; <span class="pill">arrives next</span> marks types whose adding is still being built.</p>{% endif %}
<div class="tiles">
{% for t in ['security-key', 'usb', 'hsm'] %}
<div class="tile"><div class="tile-head"><strong>{{ slot_types[t][0] }}</strong>{% if t == 'security-key' %}<span class="pill ok">recommended</span>{% endif %}{% if not add_live[t] %}<span class="pill">arrives next</span>{% endif %}</div>
<div class="muted small">{{ slot_types[t][1] }}</div>
<div><a class="btn" href="/openbao?view=add-{{ t }}">Add…</a></div></div>
{% endfor %}
</div></section>
<section class="card"><h2>Rotate the vault key</h2>
<p class="muted">Makes a new vault key and re-protects it in every method whose device is present now. Methods whose device is not present stop working — the answer to a lost stick or token.</p>
<p><a class="btn" href="/openbao?view=rotate">Rotate…</a></p></section>

{% elif view == 'add-security-key' %}
<p><a href="/openbao?view=unlock">← Unlock methods</a></p>
<section class="card"><h2>Add a security key</h2>
<p class="muted">YubiKey 5 (PIV), Nitrokey, SmartCard-HSM or any PKCS#11 token. An RSA key on the token that can never be read out wraps the vault key; at start the token unwraps it. The PIN is kept root-only on this host, so the token itself is the factor — but unlike a stick it cannot be copied.</p>
<p class="flash warn">Tested with a software token (SoftHSM2) only. YubiKey, Nitrokey and other hardware tokens are untested.</p>
{% set pk = devices.pkcs11 or [] %}
{% if pk %}
{% if can('vault:unlock') %}<form method="post" action="/openbao/slots/add-security-key" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<fieldset class="wide"><legend>Tokens the PKCS#11 libraries see</legend>
{% set enrolled = slots | map(attribute='device') | join(' ') %}
{% for t in pk %}{% set used = ('serial ' ~ t.serial ~ ' ') in (enrolled ~ ' ') %}{% set bad = t.pin_state in ('locked', 'last try') %}<label class="check perm"><input type="radio" name="token" value="{{ t.module }}|{{ t.serial }}"{{ ' disabled' if used or bad }}{{ ' checked' if loop.first and not used and not bad }}> <strong>{{ t.manufacturer }} {{ t.model }}</strong> <span class="muted small">serial {{ t.serial }}{% if t.label %} · “{{ t.label }}”{% endif %} · {{ t.library }} · PIN {{ t.pin_state }}{{ ' · already an unlock method' if used }}</span></label>{% endfor %}
</fieldset>
<fieldset class="wide"><legend>Key on the token</legend>
<label class="check perm"><input type="radio" name="key" value="new" checked> Make a new RSA-2048 key on the token</label>
<label class="check perm"><input type="radio" name="key" value="existing"> Use an existing key, id (hex) <input name="key_id" pattern="[0-9a-fA-F]{2,64}" placeholder="03" size="8"></label>
<p class="muted small">YubiKey: tokens usually cannot make keys through PKCS#11. Create one with <code>ykman piv keys generate 9d …</code> (add <code>--touch-policy always</code> to require a touch at every unlock), then use id <code>03</code>.</p>
</fieldset>
<label>Label<input name="label" placeholder="Pi key / safe key" maxlength="60"></label>
<label>Token PIN<input name="pin" type="password" autocomplete="off" required minlength="4" maxlength="64"></label>
<label class="wide">Type this host's name to confirm<input name="confirm" autocomplete="off" required placeholder="{{ host }}"></label>
<div><button{{ '' if add_live['security-key'] else ' disabled' }}>Add security key</button></div>
</form>{% endif %}
<p class="muted small">fabric wraps the vault key with the token, unwraps it again and checks it before saving. It never spends a token's last PIN try, and after a wrong PIN it does not retry unattended. You may be asked to sign in again first.</p>
{% else %}<p class="blank">No PKCS#11 token found. Plug one in; the library must be installed (<code>ykcs11</code> for YubiKey, <code>opensc-pkcs11</code> for most others, both with <code>pcscd</code>).</p>{% endif %}
{% set seen = pk | map(attribute='serial') | list %}
{% for t in devices.tokens if t.serial not in seen %}{% if loop.first %}<p class="muted small">On USB but not seen by a PKCS#11 library:{% endif %} {{ t.vendor }} {{ t.product }} (serial {{ t.serial or '—' }}){{ '.' if loop.last else ',' }}{% if loop.last %}</p>{% endif %}{% endfor %}
</section>

{% elif view == 'add-usb' %}
<p><a href="/openbao?view=unlock">← Unlock methods</a></p>
<section class="card"><h2>Add a USB stick</h2>
<p class="muted">The stick is wiped and gets a copy of the vault key. fabric records its serial and filesystem UUID and ignores sticks it did not make. Keypad-encrypted drives (Apricorn, IronKey, iStorage) work too: unlock them with their PIN first. A plain stick can be copied by anyone who holds it for a moment — a security key cannot.</p>
{% if devices.disks %}
{% if can('vault:unlock') %}<form method="post" action="/openbao/slots/add-usb" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<fieldset class="wide"><legend>Plugged into this host (will be erased)</legend>
{% for d in devices.disks %}<label class="check perm"><input type="radio" name="disk" value="{{ d.path }}"{{ ' checked' if loop.first }}> <strong>{{ d.model }}</strong> <span class="muted small">{{ d.size_gb }} GB · serial {{ d.serial or '—' }} · {{ d.path }}{% if d.labels %} · {{ d.labels | join(', ') }}{% endif %}</span></label>{% endfor %}
</fieldset>
<label>Label<input name="label" placeholder="safe stick" maxlength="60"></label>
<label class="wide">Type this host's name to confirm erasing it<input name="confirm" autocomplete="off" required placeholder="{{ host }}"></label>
<div><button class="danger"{{ '' if add_live['usb'] else ' disabled' }}>Erase and add</button></div>
</form>{% endif %}
{% else %}<p class="blank">No USB disk found. Plug one into this host and reload.</p>{% endif %}
</section>

{% elif view == 'add-hsm' %}
<p><a href="/openbao?view=unlock">← Unlock methods</a></p>
<section class="card"><h2>Add an HSM or key manager (KMIP)</h2>
<p class="muted">Any KMIP server that can Encrypt/Decrypt (AES-256-CBC) with a key you created on it — CipherTrust, Fortanix, Entrust KeyControl, IBM GKLM, Cosmian, OVHcloud KMS, … The vault key is encrypted by a key that never leaves the device, over mutual TLS (the device's certificate verified against the CA you give). Revoking fabric's client, or disabling the key, on the device is the kill switch.</p>
<p class="flash warn">Tested with the PyKMIP server only. Vendor HSMs and key managers are untested.</p>
{% if can('vault:unlock') %}<form method="post" action="/openbao/slots/add-hsm" enctype="multipart/form-data" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Endpoint<input name="endpoint" required placeholder="kms.lan:5696"></label>
<label>Key id (an active AES-256 key on the device)<input name="key_id" required maxlength="128"></label>
<label>TLS server name (if not the endpoint's host)<input name="server_name" placeholder="kms.lan"></label>
<label>Label<input name="label" maxlength="60"></label>
<label class="wide">Device's CA certificate (PEM)<input type="file" name="ca_file" required></label>
<label class="wide">fabric's client certificate (PEM, registered on the device)<input type="file" name="cert_file" required></label>
<label class="wide">Its private key (PEM)<input type="file" name="key_file" required></label>
<label class="wide">Type this host's name to confirm<input name="confirm" autocomplete="off" required placeholder="{{ host }}"></label>
<div><button{{ '' if add_live['hsm'] else ' disabled' }}>Test and add</button></div>
</form>{% endif %}
<p class="muted small">No client certificate yet? Make one under Step-CA → New key + certificate (e.g. CN <code>fabric-{{ host }}</code>), register the certificate on the device, then upload both here. A wrap and unwrap through the device run before anything is saved; the certificates are kept root-only on this host.</p></section>

{% elif view == 'rotate' %}
<p><a href="/openbao?view=unlock">← Unlock methods</a></p>
<section class="card"><h2>Rotate the vault key</h2>
<table><thead><tr><th></th><th>Method</th><th>After rotation</th></tr></thead><tbody>
{% for sl in slots %}<tr><td><span class="light {{ 'ok' if sl.present else 'bad' }}"></span></td><td>{{ slot_types[sl.type][0] }} <span class="muted small">{{ sl.label }}</span></td>
<td>{% if sl.present %}re-protected with the new key{% else %}<span class="bad-text">stops working (device not present)</span>{% endif %}</td></tr>{% endfor %}
</tbody></table>
{% if can('vault:unlock') %}<form method="post" action="/openbao/rotate" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label class="wide">Type this host's name to confirm<input name="confirm" autocomplete="off" required placeholder="{{ host }}"></label>
<div><button{{ '' if live and slots | selectattr('present') | list else ' disabled' }}>Rotate</button></div>
</form>{% endif %}
<p class="muted small">OpenBao restarts once with the old and new key, re-protects itself, then keeps only the new one. You will be asked to sign in again first.</p></section>

{% elif view == 'remove' %}
<p><a href="/openbao?view=unlock">← Unlock methods</a></p>
{% set sl = slots | selectattr('id', 'equalto', slot_id) | first %}
<section class="card"><h2>Remove {{ slot_types[sl.type][0] | lower if sl else 'method' }}</h2>
{% if sl %}<p>{{ sl.label }} — <code class="small">{{ sl.device }}</code></p>
<p class="muted">{% if sl.type == 'local' %}The key file is shredded. From then on only your devices unlock the vault.{% elif sl.type == 'usb' %}Its record is removed; the copy on the stick stays usable until you rotate the key — rotate if the stick is lost.{% else %}Its protected copy is deleted; the device's own key is untouched.{% endif %}</p>
{% if can('vault:unlock') %}<form method="post" action="/openbao/slots/{{ sl.id | urlencode }}/remove" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label class="wide">Type this host's name to confirm<input name="confirm" autocomplete="off" required placeholder="{{ host }}"></label>
<div><button class="danger"{{ '' if live and slots | length > 1 else ' disabled' }}>Remove</button></div>
</form>{% endif %}{% if slots | length < 2 %}<p class="muted">The last unlock method cannot be removed.</p>{% endif %}
{% else %}<p class="blank">No such method.</p>{% endif %}
</section>

{% elif view == 'disk' %}
<section class="card"><h2>Disk encryption with your security key or USB stick</h2>
<p class="muted">fabric does not encrypt disks: you do it once, at the console. This encrypts the volume holding fabric's data (<code>/opt</code>, <code>/etc/fabric</code>) with LUKS2, unlocked by the <strong>same YubiKey or USB stick</strong> that unlocks OpenBao. A stolen disk or SD card then reveals nothing.</p>
<p class="flash warn">Untested with hardware by the fabric project. Try it on a spare machine first, and always keep a passphrase slot. The full guide: <code>docs/disk-encryption.md</code>.</p>
<h3>Before you start</h3>
<ul>
<li><strong>Keep a passphrase</strong> (offline) and back up the LUKS header after every change: <code>sudo cryptsetup luksHeaderBackup /dev/sdX2 --header-backup-file luks-header.img</code></li>
<li><strong>One YubiKey, two jobs:</strong> OpenBao uses its PIV application (PKCS#11), LUKS its FIDO2 application — both on one YubiKey 5.</li>
<li>A <strong>data volume</strong> unlocked after boot works on Ubuntu 24.04 as installed. The <strong>root</strong> filesystem with FIDO2 needs <code>dracut</code> instead of initramfs-tools.</li>
</ul>
<h3>1. An encrypted volume for fabric's data</h3>
<pre>sudo cryptsetup luksFormat --type luks2 /dev/sdX2       # passphrase: keep it
sudo cryptsetup open /dev/sdX2 fabricdata
sudo mkfs.ext4 -L fabricdata /dev/mapper/fabricdata
sudo mkdir -p /srv/fabricdata && sudo mount /dev/mapper/fabricdata /srv/fabricdata
sudo mkdir -p /srv/fabricdata/opt /srv/fabricdata/etc-fabric</pre>
<p>Bind <code>/srv/fabricdata/opt</code> → <code>/opt</code> and <code>/srv/fabricdata/etc-fabric</code> → <code>/etc/fabric</code> in <code>/etc/fstab</code>, and open the volume from <code>/etc/crypttab</code>:</p>
<pre>fabricdata  UUID=&lt;luks-partition-uuid&gt;  none  luks,discard</pre>
<p class="muted small">Best on a fresh host, before <code>fabricctl setup</code> — or <code>fabricctl uninstall --export</code>, encrypt, then <code>fabricctl restore</code>.</p>
<h3>2a. Unlock with a YubiKey (FIDO2)</h3>
<pre>sudo apt install fido2-tools
sudo systemd-cryptenroll --fido2-device=auto /dev/sdX2     # touch the key; --fido2-with-client-pin=yes adds its PIN
sudo systemd-cryptenroll /dev/sdX2                         # lists: password + fido2</pre>
<pre>fabricdata  UUID=&lt;luks-partition-uuid&gt;  none  luks,discard,fido2-device=auto</pre>
<p class="muted small">Enrol a second YubiKey for your safe the same way. Remove one: <code>sudo systemd-cryptenroll --wipe-slot=&lt;slot&gt; /dev/sdX2</code>.</p>
<h3>2b. Unlock with the USB stick</h3>
<p>Add the stick in fabric <strong>first</strong> (Unlock methods → Add a USB stick erases it), then put a LUKS key file beside fabric's <code>fabric-vault/</code> folder:</p>
<pre>sudo mount /dev/disk/by-label/FABRIC-KEY /mnt
sudo dd if=/dev/urandom of=/mnt/luks.key bs=64 count=1 &amp;&amp; sudo chmod 0400 /mnt/luks.key
sudo cryptsetup luksAddKey /dev/sdX2 /mnt/luks.key
sudo blkid -s UUID -o value /dev/disk/by-label/FABRIC-KEY   # the stick's UUID
sudo umount /mnt</pre>
<pre>fabricdata  UUID=&lt;luks-partition-uuid&gt;  /luks.key:UUID=&lt;stick-uuid&gt;  luks,discard,keyfile-timeout=30s</pre>
<p class="muted small">Without the stick the boot asks for the passphrase after 30 s. Adding the stick to fabric again erases it: add the key file again afterwards.</p>
<h3>3. Check</h3>
<p>Reboot; <code>lsblk -f</code> shows the volume open and mounted; <code>sudo fabricctl doctor</code> passes. Then reboot without the key or stick: the boot must stop at the passphrase prompt.</p>
</section>

{% elif view == 'secrets' %}
<section class="card"><h2>fabric's own secrets</h2>
{% if s.secrets %}<p><span class="light ok"></span> In OpenBao at <code>fabric/secrets</code> · version {{ s.secrets.version }} · updated {{ s.secrets.updated }}</p>
<p class="muted">CA, directory, Keycloak and TSIG secrets. fabric reads them with its own AppRole; people cannot read them, not even in OpenBao's UI. On the host: <code>sudo fabricctl secrets list</code> / <code>show &lt;name&gt;</code> (audited).</p>
{% else %}<p><span class="light bad"></span> Not readable now{% if s.error %}: {{ s.error }}{% endif %}.</p>{% endif %}
</section>
<section class="card"><h2>Your applications' secrets</h2>
<p class="muted">Browse, edit and version secrets under <code>apps/</code> in OpenBao's own UI. Sign in with Keycloak (method OIDC, your web UI account and TOTP); the web UI admin role gets the <code>fabric-admin</code> policy.</p>
<p><a class="btn" href="{{ s.url }}ui/vault/auth?with=oidc" target="_blank" rel="noopener">Open OpenBao</a></p>
<p class="muted small">If nobody can sign in (Keycloak down): <code>sudo fabricctl vault break-glass</code> with the recovery keys gives a root token; revoke it with <code>sudo fabricctl vault revoke-token</code>.</p>
</section>
{% endif %}
{% endblock %}""",

    "stepca": """{% extends "base" %}
{% macro device_select() %}{% if devices %}<label>For device (optional — links the certificate to it)<select name="device"><option value="">—</option>{% for d in devices %}<option{{ ' selected' if d.name == device }}>{{ d.name }}</option>{% endfor %}</select></label>{% endif %}{% endmacro %}
{% block body %}
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
{% if can('pki:sign') %}<form method="post" action="/stepca/sign" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="csr" value="{{ review.pem }}">
{{ device_select() }}
<label>Valid for (days)<input name="days" inputmode="numeric" value="{{ [365, ca.max_days if ca else 365] | min }}" required></label>
<div><button>Sign certificate</button></div>
</form>{% endif %}
<p class="muted">Issued as a leaf certificate for server and client authentication, from the fabric intermediate CA.</p>
{% endif %}
<details><summary>Decoded request</summary><pre>{{ review.text }}</pre></details>
</section>
{% endif %}
<section class="card"><h2>Sign a certificate signing request</h2>
<p class="muted">For devices that make their own key (switches, printers, appliances, Windows <code>certreq</code>, <code>openssl req</code>). The private key never leaves the device.</p>
{% if can('pki:sign') %}<form method="post" action="/stepca/sign/review" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><input type="hidden" name="device" value="{{ device }}">
<label>Upload a CSR (.csr, .req, .pem or DER)<input type="file" name="csr_file" accept=".csr,.req,.pem,.der,.txt"></label>
<label>…or paste it<textarea name="csr" rows="8" placeholder="-----BEGIN CERTIFICATE REQUEST-----"></textarea></label>
<div><button>Review</button></div>
</form>{% endif %}</section>

{% elif view == 'issue' %}
<section class="card"><h2>New private key and certificate</h2>
<p class="muted">For devices that cannot make a CSR. The key is generated here, shown once for download (PEM and a password-protected .p12) and not kept.</p>
{% if can('pki:issue') %}<form method="post" action="/stepca/issue" class="grid">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Name (CN)<input name="cn" required placeholder="printer.home.arpa" value="{{ (device ~ ('.' ~ ca.domain if ca and ca.domain else '')) if device else '' }}"></label>
{{ device_select() }}
<label class="wide">Other names (DNS, IP, e-mail; comma or space separated)<input name="sans" placeholder="printer, 192.168.1.40"></label>
<label>Key type<select name="key_type">{% for k in key_types %}<option{{ ' selected' if k == 'RSA-2048' }}>{{ k }}</option>{% endfor %}</select></label>
<label>Valid for (days)<input name="days" inputmode="numeric" value="{{ [365, ca.max_days if ca else 365] | min }}" required></label>
<div><button>Generate</button></div>
</form>{% endif %}
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
{% if can('pki:read') %}<form method="post" action="/stepca/inspect" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Upload (.crt, .cer, .pem, .der, .csr)<input type="file" name="file"></label>
<label>…or paste<textarea name="data" rows="8" placeholder="-----BEGIN CERTIFICATE-----"></textarea></label>
<div><button>Inspect</button></div>
</form>{% endif %}</section>

{% elif view == 'convert' %}
<section class="card"><h2>Convert a certificate</h2>
<p class="muted">Get a certificate as PEM (.crt), DER (.cer), full chain (.pem / .p7b) — and, with its private key, a password-protected .p12 for Windows, macOS and phones. The key is not kept.</p>
{% if can('pki:issue') %}<form method="post" action="/stepca/convert" enctype="multipart/form-data" class="stack">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}">
<label>Certificate (upload)<input type="file" name="cert_file"></label>
<label>…or paste<textarea name="cert" rows="6" placeholder="-----BEGIN CERTIFICATE-----"></textarea></label>
<label>Private key for a .p12 (optional, unencrypted PEM; upload)<input type="file" name="key_file"></label>
<label>…or paste<textarea name="key" rows="4" placeholder="-----BEGIN PRIVATE KEY-----" autocomplete="off"></textarea></label>
<div><button>Convert</button></div>
</form>{% endif %}</section>

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
{% if r.device %}<p class="flash ok">Linked to device <a href="/dirsrv?view=device&name={{ r.device | urlencode }}">{{ r.device }}</a>.</p>{% endif %}
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
{% if can('dns:write') %}<form method="post" action="/apply" class="apply card">
<input type="hidden" name="csrf" value="{{ ctx.csrf }}"><button>Apply changes</button>
<span class="muted">Until applied, BIND9 does not know this {{ 'key' if action == 'created' else 'secret' }}.</span></form>{% endif %}
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


# every permission a page asks about (the dev preview's fallback when it runs without fabriclib)
PREVIEW_PERMS = ["status:read", "dns:read", "dns:write", "tsig:manage", "dhcp:read", "dhcp:write", "pki:read", "pki:issue", "pki:sign",
                 "pki:link-device", "devices:read", "devices:enroll", "devices:admin", "roles:admin", "radius:read",
                 "people:read", "vault:status", "vault:unlock", "audit:read"]
# tab -> the permission(s) that show it (any of them)
TAB_PERMS = {"overview": ("status:read",), "bind9": ("dns:read",), "kea": ("dhcp:read",), "stepca": ("pki:read",),
             "dirsrv": ("devices:read", "people:read"), "freeradius": ("radius:read",),
             "openbao": ("vault:status",)}
MENU_PERMS = {"sign": "pki:sign", "issue": "pki:issue", "convert": "pki:issue", "people": "people:read",
              "devices": "devices:read", "roles": "devices:read", "unlock": "vault:status", "disk": "vault:status"}


def _render(name, **kw):
    """Pages see `can(permission)`: what the signed-in person may do
    (fabric-agent enforces it; the pages only hide what they cannot use)."""
    kw.setdefault("ctx", None)
    kw.setdefault("tab", None)
    perms = set((kw["ctx"] or {}).get("perms") or ())

    def can(perm):
        return perm in perms
    kw["can"] = can
    kw["tabs"] = [t for t in TABS if any(can(q) for q in TAB_PERMS.get(t[0], ()))]
    for key in ("menu", "sections"):
        if kw.get(key):
            kw[key] = [(v, label) for v, label in kw[key] if can(MENU_PERMS.get(v, "")) or v not in MENU_PERMS]
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


def stepca(ctx, view, ca, issued=None, review=None, inspected=None, err="", devices=None, device=""):
    """devices: directory devices a certificate can be linked to (sign/issue)."""
    return _render("stepca", ctx=ctx, tab="stepca", view=view, menu=STEPCA_MENU, ca=ca, issued=issued,
                   review=review, inspected=inspected, err=err, key_types=KEY_TYPES, devices=devices or [],
                   device=device)


def openbao(ctx, status, view="status", slots=(), devices=None, slot_id="", host="", live=False, msg="", err="",
            add_live=None):
    """status: vault_status(); slots: list_slots(); devices: detect_devices().
    live: whether slot changes are available (False shows them disabled)."""
    section = view if view in ("status", "secrets", "disk") else "unlock"
    return _render("openbao", ctx=ctx, tab="openbao", s=status, view=view, section=section, sections=OPENBAO_SECTIONS,
                   slots=list(slots), devices=devices or {"tokens": [], "disks": []}, slot_types=SLOT_TYPES,
                   slot_id=slot_id, host=host, live=live, msg=msg, err=err,
                   add_live=add_live or {"security-key": False, "usb": False, "hsm": False})


def kea(ctx, overview, msg="", err=""):
    return _render("kea", ctx=ctx, tab="kea", d=overview, msg=msg, err=err)


def person_result(ctx, uid, what, password):
    return _render("person_result", ctx=ctx, tab="dirsrv", uid=uid, what=what, password=password)


def dirsrv(ctx, view, data=None, people=None, device=None, role=None, msg="", err="", unavailable=""):
    """view: devices | device | roles | role | people. data: device_overview()."""
    section = {"device": "devices", "role": "roles"}.get(view, view)
    return _render("dirsrv", ctx=ctx, tab="dirsrv", view=view, section=section, sections=DIRSRV_SECTIONS,
                   data=data or {"devices": [], "roles": [], "types": [], "permissions": {}}, people=people,
                   device=device, role=role, msg=msg, err=err, unavailable=unavailable)


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
.brand{font-weight:600;color:var(--text);text-decoration:none}.brand .subtitle{font-weight:400;color:var(--muted);font-size:.85em;margin-left:.35em}
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
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 0 16px;overflow-x:auto;overflow-y:hidden}
.narrow{max-width:520px;margin:48px auto}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:6px}
.tile-head{display:flex;align-items:center;gap:10px}
.light{display:inline-block;vertical-align:middle;flex:none;width:10px;height:10px;border-radius:50%;background:var(--muted)}
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
.sections{display:flex;gap:4px;border-bottom:1px solid var(--border);margin:0 0 16px;overflow-x:auto;overflow-y:hidden}
.section{flex:none;padding:8px 12px;color:var(--muted);text-decoration:none;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap}
.section:hover{color:var(--text)}.section.active{color:var(--text);border-bottom-color:var(--accent);font-weight:600}
.picker{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px}
.small{font-size:12px}
label.perm{flex-basis:100%}
button:disabled,.btn.disabled{opacity:.45;cursor:not-allowed;pointer-events:none}
.danger-link{color:var(--bad);border-color:var(--bad)}
.devbanner{margin:0;padding:8px 16px;text-align:center;font-weight:600;background:#b45309;color:#fff}
"""
