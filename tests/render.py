"""Render every template the way deploy.py does, against a vars file shaped like a
long-running install (round-tripped values). Usage: render.py <out-dir>"""
import copy
import json
import os
import sys
import glob
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[0:0] = [os.path.join(REPO, 'fabricctl', 'lib'), REPO]
from fabriclib.common.jinja_env import jinja_env  # noqa: E402  (the same env deploy.py uses)
from fabriclib.dns.reverse_zones import reverse_zones  # noqa: E402

env = jinja_env(os.path.join(REPO, 'fabricctl', 'jinja'))

secrets = dict(ca_password='x', rndc_secret='dGVzdC1vbmx5LXJuZGMtc2VjcmV0LTMyLWJ5dGVzISE=', ldap_admin_password='DmPass1', ldap_keycloak_password='KcPass1',
               keycloak_admin_user='admin', keycloak_admin_password='x', keycloak_db_password='x',
               ldap_super_admin_password='Sa1', ldap_group_admin_password='Ga1',
               ldap_user_creator_password='Uc1', ldap_user_modifier_password='Um1', ldap_device_admin_password='Da1', ldap_radius_password='Rr1',
               radius_secrets={'switch1': 'Sw1tchSecretSw1tchSecret', 'ap-old': 'OldApSecretOldApSecret'},
               webui_oidc_secret='OidcSecret1',
               tsig_secrets={'npm': 'bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch', 'acme_dns-01': 'YWNtZS10ZXN0LXNlY3JldA==',
                             'dev1': 'ZGV2MS1zZWNyZXQ=', 'lonely': 'bG9uZWx5LXNlY3JldA=='})
user = dict(deploy_base_dir='/opt', domain='lan.j-j.family', hostname='pi-core',
            host_ip='192.168.7.53', lan_cidr='192.168.7.0/24', lan_gateway='192.168.7.1',
            fabric_subnet='10.255.0.0/24', landing_page_cname=None, install_keycloak=True,
            cert_country='US', cert_province='S', cert_city='C', cert_org='O', cert_ou='IT', ca_name='CA',
            project_containers=['nginx', 'step-ca', 'bind9', 'dirsrv', 'keycloak', 'postgres', 'dirsrv'],
            service_dirs=[{'folder': 'dirsrv', 'owner': 'ldap'}, {'folder': 'extra', 'owner': 'root'}],
            # as normalize_tsig_keys leaves them: an NPM-style per-host key and a primary one
            tsig_keys=[{'name': 'npm', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family',
                        'record_types': ['TXT'], 'records': ['npm', 'shelfmark']},
                       {'name': 'acme_dns-01', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family',
                        'record_types': ['TXT'], 'primary': True},
                       {'name': 'dev1', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family', 'record_types': ['TXT']},
                       {'name': 'lonely', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family', 'record_types': ['TXT']}],
            # certbot devices: rights come from the ACL's policy
            bind_acls={'certbot-devices': ['key "dev1"']},
            bind_acl_policies={'certbot-devices': {'domain': 'lan.j-j.family', 'record_types': ['TXT'],
                                                   'records': ['web', 'git']}},
            dns={'dynamic_zone_var': {'zone_authority': True,
                                      'CNAME': [{'name': 'None', 'canonical': 'pi-core'},
                                                {'name': 'calibre', 'canonical': 'nas25-apps'}]}})

# Suites that start real containers override install-specific values
# (deploy path, host IP, ports) with a JSON object in FABRIC_TEST_VARS.
user.update(json.loads(os.environ.get("FABRIC_TEST_VARS", "{}")))

ctx = {**secrets, **user, 'render_date': '2026-01-01'}
PRISTINE = copy.deepcopy(ctx)      # vars.yaml.j2 updates the dns dict it is given in place
v1 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**ctx))
v2 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**ctx, **v1}))

# Reverse zones: generated from forward A/AAAA records (deploy.py does the same).
rv = reverse_zones({'domain': 'lan.test', 'host_ip': '192.168.7.53', 'dns': {
    'dynamic_zone_var': {'zone_authority': True,
                         'A': [{'name': '@', 'ip': '192.168.7.53'}, {'name': 'fabric', 'ip': '192.168.7.53'},
                               {'name': 'nas', 'ip': '192.168.7.10'}, {'name': 'lab', 'ip': '10.1.2.3'},
                               {'name': 'cloud', 'ip': '8.8.8.8'}],
                         'AAAA': [{'name': 'nas', 'ip': 'fd12:3456:789a:1::10'}, {'name': 'pub', 'ip': '2001:db8::1'}]},
    'iot.lan.test': {'A': [{'name': 'cam', 'ip': '192.168.7.99'}]},
    '5.168.192.in-addr.arpa': {'A': []},
}})
z = rv['zones']
assert list(z) == ['1.0.0.0.a.9.8.7.6.5.4.3.2.1.d.f.ip6.arpa', '2.1.10.in-addr.arpa', '7.168.192.in-addr.arpa'], list(z)
ptr7 = {r['label']: r['target'] for r in z['7.168.192.in-addr.arpa']}
assert ptr7 == {'10': 'nas.lan.test.', '53': 'fabric.lan.test.', '99': 'cam.iot.lan.test.'}, ptr7
assert [r['label'] for r in z['7.168.192.in-addr.arpa']] == ['10', '53', '99'], 'PTRs sorted numerically'
assert z['1.0.0.0.a.9.8.7.6.5.4.3.2.1.d.f.ip6.arpa'][0] == {
    'label': '0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0', 'target': 'nas.lan.test.', 'ip': 'fd12:3456:789a:1::10',
    'source': 'AAAA nas in lan.test'}, z
assert {s['ip'] for s in rv['skipped']} == {'8.8.8.8', '2001:db8::1'}, 'public addresses get no local reverse zone'
apex = reverse_zones({'domain': 'lan.test', 'dns': {'dynamic_zone_var': {'A': [{'name': '@', 'ip': '192.168.9.1'}]}}})
assert apex['zones']['9.168.192.in-addr.arpa'][0]['target'] == 'lan.test.', 'apex record -> PTR to the zone, not "@."'
full_rev = reverse_zones(v1)
print('reverse zones', list(full_rev['zones']))
diff = {k: (v1.get(k), v2.get(k)) for k in set(v1) | set(v2) if v1.get(k) != v2.get(k)}
assert not diff, diff
print('project_containers', v2['project_containers'])
print('service_dirs', [d['folder'] for d in v2['service_dirs']])
print('ldap backends', v2['nginx_backend_ldap'], v2['nginx_backend_ldaps'])
print('install_webui', v2['install_webui'], v2['hostname_mgr'])
print('CNAMEs', [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']])

full = {**secrets, **v2, 'reverse_zone_names': list(full_rev['zones'])}
out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else None
if out:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'vars.yaml'), 'w') as f:
        yaml.safe_dump(v2, f)
for tpl in sorted(env.list_templates()):
    if not tpl.endswith('.j2') or tpl == 'vars.yaml.j2':
        continue
    extra = {}
    if tpl.startswith('bind9/data/zone'):
        extra = dict(zone_name='lan.j-j.family', zone_records=v2['dns']['dynamic_zone_var'])
    if tpl.startswith('bind9/data/reverse'):
        extra = dict(reverse_zone_name='7.168.192.in-addr.arpa', ptr_records=rv['zones']['7.168.192.in-addr.arpa'])
    if tpl.startswith('systemd/'):
        extra = dict(item={'service': 'ldap', 'compose': 'dirsrv', 'folder': 'dirsrv', 'requires': []})
    if tpl.endswith('.json.j2'):
        json.loads(env.get_template(tpl).render(**full))
    text = env.get_template(tpl).render(**full, **extra)
    if out:
        dest = os.path.join(out, tpl[:-3])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, 'w', encoding='utf-8').write(text)
    if tpl.endswith(('.yml.j2', '.yaml.j2')):
        yaml.safe_load(text)
zones = env.get_template('bind9/config/named.conf.zones.j2').render(**full)
keys = env.get_template('bind9/config/named.conf.keys.j2').render(**full)
for want in ('grant "npm" name _acme-challenge.npm.lan.j-j.family. TXT;',
             'grant "npm" name _acme-challenge.shelfmark.lan.j-j.family. TXT;',
             'grant "acme_dns-01" subdomain _acme-challenge TXT;'):
    assert want in zones, f'missing update-policy grant: {want}'
assert 'zonesub' not in zones, 'no key asked for any_name: nothing may get zonesub'
for want in ('grant "dev1" name _acme-challenge.web.lan.j-j.family. TXT;',
             'grant "dev1" name _acme-challenge.git.lan.j-j.family. TXT;'):
    assert want in zones, f'missing ACL-policy grant: {want}'
assert 'grant "lonely"' not in zones, 'a key with no records, policy or any_name must get no update rights'
acl = env.get_template('bind9/config/named.conf.acl.j2').render(**full)
assert 'acl "certbot-devices"' in acl and 'key "dev1";' in acl, 'policy ACL not rendered'
assert 'secret "bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch";' in keys, 'embedded TSIG secret not rendered'
print('TSIG keys and RFC2136 grants rendered')

# Web UI at any host name; certificate page on its own host.
assert v2['hostname_mgr'] == 'fabric.lan.j-j.family' and v2['hostname_certs'] == 'certs.lan.j-j.family', v2['hostname_mgr']
custom = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'webui_hostname': 'Admin.Example.org'}))
assert custom['hostname_mgr'] == 'admin.example.org', custom['hostname_mgr']
names = [r['name'] for r in custom['dns']['dynamic_zone_var']['CNAME']]
assert 'fabric' not in names and 'admin' not in names, f'no CNAME for a web UI outside the domain: {names}'
ngx = env.get_template('nginx/nginx.conf.j2').render(**{**secrets, **custom})
assert 'server_name admin.example.org;' in ngx and 'server_name certs.lan.j-j.family;' in ngx
same = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'hostname': 'fabric'}))
assert 'fabric' not in [r['name'] for r in same['dns']['dynamic_zone_var']['CNAME']], 'CNAME must not shadow the host A record'
print('web UI host name (default, custom, same as host) and certs host rendered')

# Federation (design federation.md): the endpoint's vhost, socket mount, CNAME and unit only when it is
# on; a site's organisation suffix comes from org_domain, its local suffix and names from its own.
assert v2['federation_endpoint'] is False and v2['org_domain'] == v2['domain'], (v2['federation_endpoint'], v2['org_domain'])
assert v2['hostname_federation'] == 'federation.lan.j-j.family', v2['hostname_federation']
assert 'federation' not in [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']], 'no CNAME while the endpoint is off'
assert 'server_name federation.' not in env.get_template('nginx/nginx.conf.j2').render(**full), 'no vhost while off'
assert '/srv/federation' not in env.get_template('nginx/docker-compose.yml.j2').render(**full), 'no socket mount while off'
fed = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'federation_endpoint': True}))
assert 'federation' in [r['name'] for r in fed['dns']['dynamic_zone_var']['CNAME']], 'CNAME for the endpoint'
ngx = env.get_template('nginx/nginx.conf.j2').render(**{**secrets, **fed})
assert 'server_name federation.lan.j-j.family;' in ngx and 'proxy_pass http://unix:/srv/federation/federation.sock:;' in ngx
assert 'limit_req zone=federation' in ngx and 'client_max_body_size 16k;' in ngx, 'the join route is rate- and size-limited'
assert 'federation/run:/srv/federation:ro' in env.get_template('nginx/docker-compose.yml.j2').render(**{**secrets, **fed})
unit = env.get_template('systemd/fabric-federation.service.j2').render(**fed)
assert f"--allow-uid {fed['service_users']['nginx']['uid']}" in unit and 'lib/federation/server.py' in unit, unit
site = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'domain': 'branch1.lan.j-j.family',
                                                                  'org_domain': 'lan.j-j.family', 'site_name': 'branch1'}))
assert site['ldap_base_dn'] == v2['ldap_base_dn'] == 'dc=lan,dc=j-j,dc=family', site['ldap_base_dn']
assert site['ldap_local_dn'] == 'ou=branch1,dc=lan,dc=j-j,dc=family' and site['hostname_federation'] == 'federation.branch1.lan.j-j.family'
# a chosen base DN (the root site's install, e.g. dc=lan): the site part sits under it; the seed's base entry
# takes its first RDN (domain for dc=, organization for o=)
for base, oc in (('dc=lan', 'objectClass: domain\ndc: lan'), ('o=acme,dc=lan', 'objectClass: organization\no: acme')):
    chosen = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'ldap_base_dn': base}))
    assert chosen['ldap_base_dn'] == base and chosen['ldap_local_dn'] == f'ou=pi-core,{base}', chosen['ldap_local_dn']
    tree = env.get_template('dirsrv/seed/10-tree.ldif.j2').render(**{**chosen, **secrets})
    assert f'dn: {base}\nobjectClass: top\n{oc}' in tree, tree[:400]
    assert f'dn: ou=pi-core,{base}\nobjectClass: top\nobjectClass: organizationalUnit\nou: pi-core' in tree
print('federation: endpoint vhost/mount/CNAME/unit only when on; a site shares the organisation suffix')
# DNS links (design federation.md M4): none -> no transfers; with links -> keys, transfers, secondaries, delegation
plain = env.get_template('bind9/config/named.conf.zones.j2').render(**full)
assert 'type secondary' not in plain and 'also-notify' not in plain, 'no federation links: no secondaries, no notify'
links = {'children': [{'site': 'lab', 'key': 'fed-lab', 'algorithm': 'hmac-sha256', 'secret': 'c2VjcmV0', 'delegate': True,
                       'label': 'lab', 'domain': 'lab.lan.j-j.family', 'address': '192.168.9.9'}],
         'upstream': {'site': 'hq', 'key': 'fed-pi-core', 'algorithm': 'hmac-sha256', 'secret': 'dXBzdHJlYW0=',
                      'domain': 'hq.example.org', 'address': '192.168.8.8'}}
zones = env.get_template('bind9/config/named.conf.zones.j2').render(**full, federation_links=links)
keys = env.get_template('bind9/config/named.conf.keys.j2').render(**full, federation_links=links)
assert 'allow-transfer { key "fed-lab"; key "fed-pi-core"; };' in zones and 'notify explicit;' in zones, zones[:600]
assert 'zone "lab.lan.j-j.family" {\n    type secondary;\n    primaries { 192.168.9.9 port 53 key "fed-lab"; };' in zones
assert 'zone "hq.example.org" {\n    type secondary;' in zones and 'key "fed-lab" {' in keys and 'key "fed-pi-core" {' in keys
db = env.get_template('bind9/data/zone.j2').render(**full, federation_links=links, zone_name=v2['domain'],
                                                   zone_records=v2['dns']['dynamic_zone_var'])
assert 'lab                     NS      ns.lab.lan.j-j.family.' in db and 'ns.lab                  A       192.168.9.9' in db
print('federation DNS: no links -> no transfers; links -> keys, signed transfers, secondaries, delegation with glue')
# DNS filter (dns-filter.md): off by default; on -> AdGuard on 53, BIND on 5053 (even when vars.yaml had 53), CNAME,
# the vhost (OIDC first), AdGuard's container without capabilities and its UI unpublished
assert v2['dns_filter'] == 'none' and v2['install_adguard'] is False
assert v2['bind_dns_port'] == user.get('bind_dns_port', 53), 'with the filter off the port is what vars say (53)'
adg = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'dns_filter': 'AdGuard',
                                                                 'bind_dns_port': 53}))
assert adg['install_adguard'] is True and adg['bind_dns_port'] == 5053, (adg['install_adguard'], adg['bind_dns_port'])
assert 'adguard' in [r['name'] for r in adg['dns']['dynamic_zone_var']['CNAME']] and adg['adguard_upstreams'] == []
kept = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'bind_dns_port': 5053}))
assert kept['bind_dns_port'] == 5053, 'with the filter off a chosen port is kept (an AdGuard of your own)'
ngx = env.get_template('nginx/nginx.conf.j2').render(**{**secrets, **adg})
assert 'server_name adguard.lan.j-j.family;' in ngx and 'auth_request /oauth2/auth;' in ngx
assert 'include /etc/nginx/conf.d/adguard-auth.inc;' in ngx and 'adguard' not in env.get_template('nginx/nginx.conf.j2').render(**full)
comp = yaml.safe_load(env.get_template('adguard/docker-compose.yml.j2').render(**{**secrets, **adg}))['services']
assert comp['adguardhome']['cap_drop'] == ['ALL'] and 'cap_add' not in comp['adguardhome']
auth = yaml.safe_load(env.get_template('adguard-auth/docker-compose.yml.j2').render(**{**secrets, **adg}))['services']
assert not any(':3000' in p for p in comp['adguardhome']['ports']) and list(comp) == ['adguardhome'], list(comp)
assert auth['oauth2-proxy']['read_only'] is True and auth['oauth2-proxy']['cap_drop'] == ['ALL']
assert 'skip_oidc_discovery = true' in env.get_template('adguard/oauth2-proxy.cfg.j2').render(**adg), 'starts while Keycloak is down'
_o2p = env.get_template('adguard/oauth2-proxy.cfg.j2').render(**adg)
assert not [ln for ln in _o2p.splitlines() if ln.strip().startswith(('client_secret', 'cookie_secret'))], \
    'oauth2-proxy secrets only via secrets.env'
print('DNS filter: off by default; on -> AdGuard on 53, BIND on 5053, CNAME, OIDC vhost, no capabilities, UI unpublished')
# time (ntp.md): served by default with NTS sources and ntp.<domain>; a record of the user's own named ntp is kept
assert v2['ntp_serve'] is True and v2['ntp_set_clock'] is True and all(x.endswith(' nts') for x in v2['ntp_servers'])
assert 'ntp' in [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']]
own = copy.deepcopy(PRISTINE)
own['dns'] = {'dynamic_zone_var': {'zone_authority': True, 'A': [{'name': 'ntp', 'ip': '192.168.4.9'}]}}
own_v = yaml.safe_load(env.get_template('vars.yaml.j2').render(**own))
assert 'ntp' not in [r['name'] for r in own_v['dns']['dynamic_zone_var'].get('CNAME', [])], 'never a CNAME next to an A'
assert yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'ntp_servers': []}))['ntp_servers'] == []
assert 'time-sync.target' in env.get_template('systemd/wrapper.service.j2').render(**{**v2, 'item': {'service': 'x', 'folder': 'x', 'compose': 'x'}})
print('time: served with NTS sources by default, ntp.<domain>, units after time-sync.target, Kea option 42')
# Every image is pinned by digest (design D21): the vars defaults are the lock's refs,
# no compose file or Dockerfile names an image any other way.
import re  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
lock = read_images_lock(os.path.join(REPO, 'fabricctl'))
assert lock and all(re.fullmatch(r'sha256:[0-9a-f]{64}', e['digest']) for e in lock.values()), 'bad images.lock.yaml'
for e in lock.values():
    assert v2[e['var']] == e['ref'], f"{e['var']} default is not the lock's ref: {v2[e['var']]}"
for key, val in v2.items():
    if key.startswith('image_') and isinstance(val, str):
        assert '@sha256:' in val or val.startswith('fabric/') and val.endswith(':local'), f'{key} not pinned: {val}'
for svc in ('nginx', 'bind9', 'stepca', 'dirsrv', 'keycloak', 'postgres', 'webui', 'openbao', 'fluentbit'):
    dc = yaml.safe_load(env.get_template(f'{svc}/docker-compose.yml.j2').render(**{**secrets, **v2}))
    for name, spec in dc['services'].items():
        ref = ((spec.get('build') or {}).get('args') or {}).get('BASE_IMAGE') or spec.get('image', '')
        assert '@sha256:' in ref or (spec.get('build') and '@sha256:' in spec['build']['args'].get('BASE_IMAGE', '')),             f'{svc}/{name}: image not pinned: {ref}'
for df in glob.glob(os.path.join(REPO, 'fabricctl', 'jinja', '*', 'build', 'Dockerfile')) + [os.path.join(REPO, 'webui', 'Dockerfile')]:
    text = open(df).read()
    assert not re.search(r'^ARG BASE_IMAGE=', text, re.M), f'{df}: BASE_IMAGE must have no default'
    assert all(ln.split()[1].startswith('${BASE_IMAGE}') for ln in text.splitlines() if ln.startswith('FROM ')),         f'{df}: FROM must be the pinned ${{BASE_IMAGE}}'
print('every image pinned by digest (lock, vars defaults, compose files, Dockerfiles)')

# Fluent Bit (optional log forwarding, D20): verified TLS to every destination, no credential in the file
fb_vars = {**v2, "hostname": "pi-core", "log_forwarding": {"syslog": {"host": "siem.lan", "port": 6514},
                                                          "elastic": {"url": "https://es.lan:9200", "user": "fabric"}}}
fb = yaml.safe_load(env.get_template('fluentbit/fluent-bit.yaml.j2').render(**fb_vars))
outs = {o["name"]: o for o in fb["pipeline"]["outputs"]}
assert set(outs) == {"syslog", "es"} and all(o["tls.verify"] in (True, "on") for o in outs.values()), outs
assert outs["syslog"]["mode"] == "tls" and outs["syslog"]["syslog_format"] == "rfc5424", outs["syslog"]
assert outs["es"]["host"] == "es.lan" and outs["es"]["port"] == 9200 and outs["es"]["http_passwd"] == "${LOG_ELASTIC_PASSWORD}"
assert fb["service"]["storage.path"] == "/buffer" and any(i["name"] == "systemd" for i in fb["pipeline"]["inputs"])
none = yaml.safe_load(env.get_template('fluentbit/fluent-bit.yaml.j2').render(**{**v2, "hostname": "h"}))
assert [o["name"] for o in none["pipeline"]["outputs"]] == ["null"], none
for svc in ('nginx', 'bind9', 'stepca', 'dirsrv', 'keycloak', 'postgres', 'webui', 'openbao'):
    dc = yaml.safe_load(env.get_template(f'{svc}/docker-compose.yml.j2').render(**{**secrets, **v2}))
    assert all(sp.get("logging", {}).get("driver") == "journald" for sp in dc["services"].values()), svc
print('Fluent Bit: verified TLS to syslog and Elasticsearch, password from the environment; containers log to the journal')
# A declared OpenBao audit device must never change (OpenBao then refuses to become
# active on upgrade); new needs get a new device.
hcl = env.get_template('openbao/openbao.hcl.j2').render(**{**secrets, **v2})
assert 'audit "file" "file" {\n  description = "fabric: every request"\n  options {\n    file_path = "/openbao/logs/audit.log"\n  }\n}' in hcl, 'the original audit device changed'
print('OpenBao audit devices: the original one unchanged')
# Kea (optional DHCP, design §5 / D16): configs, the DHCP subzone, the key's rights, input checks
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp  # noqa: E402
kv = {**v2, "install_kea": True, "kea_ddns_secret": "a2VhLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmchIQ==",
      "dhcp": {"interfaces": ["eth0"], "subnets": [{"subnet": "192.168.7.0/24", "pools": ["192.168.7.100 - 192.168.7.199"],
               "routers": "192.168.7.1", "reservations": [{"mac": "AA-BB-CC-00-11-22", "ip": "192.168.7.20",
                                                           "hostname": "printer"}]}]}}
kv["dhcp"] = normalize_dhcp(kv)
assert kv["dhcp"]["subnets"][0]["reservations"][0]["mac"] == "aa:bb:cc:00:11:22"


def kea_json(name):
    text = env.get_template(f"kea/{name}.j2").render(**kv)
    return json.loads("\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("//")))


k4 = kea_json("kea-dhcp4.conf")["Dhcp4"]
sn = k4["subnet4"][0]
assert sn["pools"] == [{"pool": "192.168.7.100 - 192.168.7.199"}] and sn["reservations"][0]["ip-address"] == "192.168.7.20"
assert k4["ddns-qualifying-suffix"] == "dhcp.lan.j-j.family." and k4["ddns-conflict-resolution-mode"] == "check-with-dhcid"
assert k4["control-socket"]["socket-name"].startswith("/var/run/kea/") and k4["interfaces-config"]["interfaces"] == ["eth0"]
# time (ntp.md): Kea hands out this host's chrony (option 42) unless dhcp.ntp says otherwise
assert {"name": "ntp-servers", "data": kv["host_ip"]} in k4["option-data"], k4["option-data"]
kv["dhcp"] = {**kv["dhcp"], "ntp": ["192.168.7.2", "192.168.7.3"]}
assert {"name": "ntp-servers", "data": "192.168.7.2, 192.168.7.3"} in kea_json("kea-dhcp4.conf")["Dhcp4"]["option-data"]
kv["dhcp"] = {**kv["dhcp"], "ntp": []}
assert "ntp-servers" not in str(kea_json("kea-dhcp4.conf")["Dhcp4"]["option-data"]), "dhcp.ntp [] hands out none"
kv["dhcp"] = {k: x for k, x in kv["dhcp"].items() if k != "ntp"}
try:
    normalize_dhcp({**kv, "dhcp": {**kv["dhcp"], "ntp": ["time.example"]}})
    raise AssertionError("dhcp.ntp must be IPv4 addresses")
except ValidationError:
    pass
d2 = kea_json("kea-dhcp-ddns.conf")["DhcpDdns"]
assert d2["forward-ddns"]["ddns-domains"][0]["name"] == "dhcp.lan.j-j.family." and d2["tsig-keys"][0]["name"] == "kea-ddns"
zones = env.get_template('bind9/config/named.conf.zones.j2').render(**{**secrets, **kv, "tsig_keys": [], "tsig_secrets": {}})
dz = zones[zones.index('zone "dhcp.lan.j-j.family"'):]
dz = dz[:dz.index("};\n};") + 5]
assert 'grant "kea-ddns" zonesub A AAAA DHCID;' in dz and dz.count("grant") == 1, dz
keys = env.get_template('bind9/config/named.conf.keys.j2').render(**{**secrets, **kv, "tsig_keys": [], "tsig_secrets": {}})
assert 'key "kea-ddns"' in keys and kv["kea_ddns_secret"] in keys
parent = env.get_template('bind9/data/zone.j2').render(**{**secrets, **kv, "zone_name": "lan.j-j.family",
                                                        "zone_records": kv["dns"]["dynamic_zone_var"]})
assert re.search(r"^dhcp\s+NS\s+ns\.lan\.j-j\.family\.$", parent, re.M), "no delegation of the DHCP subzone"
nokea = env.get_template('bind9/config/named.conf.zones.j2').render(**{**secrets, **v2, "tsig_keys": [], "tsig_secrets": {}})
assert "dhcp.lan.j-j.family" not in nokea, "no DHCP subzone without Kea"
for bad, msg in ((lambda d: d["subnets"][0].update(pools=["192.168.8.1 - 192.168.8.9"]), "inside"),
                 (lambda d: d["subnets"][0]["reservations"][0].update(ip="192.168.7.150"), "outside its pools"),
                 (lambda d: d.update(interfaces=[]), "interface"),
                 (lambda d: d["subnets"][0].update(pools=["192.168.7.50 - 192.168.7.60"]), "inside a DHCP pool")):
    d = copy.deepcopy(kv["dhcp"])
    bad(d)
    vv = {**kv, "dhcp": d, "dns": {"dynamic_zone_var": {"A": [{"name": "nas", "ip": "192.168.7.53"}]}}}
    try:
        normalize_dhcp(vv)
        raise AssertionError(f"not refused: {msg}")
    except ValidationError as e:
        assert msg in str(e), (msg, str(e))
kc = yaml.safe_load(env.get_template('kea/docker-compose.yml.j2').render(**kv))["services"]
assert kc["kea-dhcp4"]["cap_add"] == ["NET_RAW", "NET_BIND_SERVICE"] and kc["kea-dhcp4"]["network_mode"] == "host"
assert kc["kea-ddns"]["user"] == "915:915" and not kc["kea-ddns"].get("cap_add")
assert kc["kea-dhcp4"]["build"]["args"]["KEA_KEY_FINGERPRINT"] == "9DA570BB192211885E4EB280B16C44CD45514C3C"
print('Kea: configs, the DHCP subzone (A/AAAA/DHCID only, delegated), refusals, two capabilities only')

# FreeRADIUS (802.1X): clients with their secrets, BlastRADIUS protection unless relaxed per client,
# EAP-TLS only with the fabric CA, no session resumption, the policy module, a hardened container
from fabriclib.radius.normalize_radius_clients import normalize_radius_clients  # noqa: E402
rclients, rembedded = normalize_radius_clients([{"name": "Switch1", "address": "192.168.7.2"},
                                                {"name": "ap-old", "address": "192.168.7.16/28",
                                                 "message_authenticator": False, "secret": "OldApSecretOldApSecret"}])
assert rclients[0] == {"name": "switch1", "address": "192.168.7.2", "message_authenticator": True}, rclients
assert rembedded == {"ap-old": "OldApSecretOldApSecret"} and "secret" not in rclients[1], "secret must leave vars"
for bad in ([{"name": "a", "address": "0.0.0.0/0"}], [{"name": "a", "address": "10.0.0.1"}, {"name": "b", "address": "10.0.0.0/24"}],
            [{"name": "a", "address": "10.0.0.1"}, {"name": "a", "address": "10.0.0.2"}], [{"name": "a b", "address": "10.0.0.1"}],
            [{"name": "a", "address": "10.0.0.1", "secret": "has $ {dollar} x"}], [{"name": "a", "address": "10.0.0.1", "secret": "short"}]):
    try:
        normalize_radius_clients(bad)
        raise AssertionError(f"accepted: {bad}")
    except ValidationError:
        pass
rv_ = {**v2, "install_freeradius": True, "radius_clients": rclients, "radius_secrets": secrets["radius_secrets"]}
clients_conf = env.get_template("freeradius/config/clients.conf.j2").render(**rv_)
assert 'secret = "Sw1tchSecretSw1tchSecret"' in clients_conf and "ipaddr = 192.168.7.16/28" in clients_conf
assert clients_conf.count("require_message_authenticator = yes") == 1 and "require_message_authenticator = no" in clients_conf
eap = env.get_template("freeradius/config/mods/eap.j2").render(**rv_)
assert "default_eap_type = tls" in eap and "ca_file = ${certdir}/ca.pem" in eap and "enable = no" in eap \
    and "virtual_server = fabric-check-eap-tls" in eap and not re.search(r"^\s*(peap|mschapv2|md5|leap|gtc)\s*\{", eap, re.M)
assert "ttls {" in eap, "the default network groups are mapped: EAP-TTLS on"
eap_none = env.get_template("freeradius/config/mods/eap.j2").render(**{**rv_, "radius_people": []})
assert "ttls {" not in eap_none, "no password logins while no group is mapped"
from fabriclib.radius.normalize_radius_people import normalize_radius_people  # noqa: E402
people = normalize_radius_people([{"group": "guests", "vlan": "50", "priority": 60}, {"group": "staff", "vlan": 20}])
assert people[0]["group"] == "guests" and people[1] == {"group": "staff", "vlan": 20, "priority": 100}, people
for bad in ([{"group": "staff", "vlan": 5000}], [{"group": "staff"}, {"group": "STAFF"}], [{"group": ""}],
            [{"group": "x", "priority": "high"}]):
    try:
        normalize_radius_people(bad)
        raise AssertionError(f"accepted: {bad}")
    except ValidationError:
        pass
eap_p = env.get_template("freeradius/config/mods/eap.j2").render(**{**rv_, "radius_people": people})
assert "ttls {" in eap_p and "virtual_server = fabric-inner-tunnel" in eap_p and "use_tunneled_reply = yes" in eap_p
frj_p = json.loads(env.get_template("freeradius/config/fabric-radius.json.j2").render(**{**rv_, "radius_people": people}))
assert frj_p["people"] == people, frj_p
frj = json.loads(env.get_template("freeradius/config/fabric-radius.json.j2").render(**rv_))
assert frj["uri"] == "ldaps://ldap.lan.j-j.family:3636" and frj["bind_dn"].startswith("cn=radius_reader,")
fc = yaml.safe_load(env.get_template("freeradius/docker-compose.yml.j2").render(**rv_))["services"]["freeradius"]
assert fc["cap_drop"] == ["ALL"] and not fc.get("cap_add") and fc["read_only"] and fc["user"] == "916:916", fc
assert fc["ports"] == [f"{v2['host_ip']}:1812:1812/udp", f"{v2['host_ip']}:1813:1813/udp"], fc["ports"]
accounts = env.get_template("dirsrv/seed/20-accounts.ldif.j2").render(**{**v2, **secrets})
assert "cn=radius_reader," in accounts and "userPassword: Rr1" in accounts
assert v2["radius_people"] == [{"group": "network-staff", "vlan": None, "priority": 50},
                               {"group": "network-guests", "vlan": None, "priority": 100}], v2["radius_people"]
kept_empty = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**ctx, **v1, "radius_people": []}))
assert kept_empty["radius_people"] == [], "an empty mapping must stay empty (no defaults brought back)"
tree = env.get_template("dirsrv/seed/10-tree.ldif.j2").render(**{**v2, **secrets})
assert "dn: cn=network-staff,ou=groups," in tree and "dn: cn=network-guests,ou=groups," in tree
assert not any(g.get("bundle") for g in v2["ldap_groups"] if g["name"] in ("network-staff", "network-guests")),     "the network groups grant no fabric web access"
print("FreeRADIUS: clients (secrets out of vars, bad ones refused), EAP-TLS, EAP-TTLS only for mapped groups, policy lookup, no capabilities")

# each systemd unit waits for its health check by container name: that name
# must be a container_name in its compose template (else start hangs 10 min)
from fabriclib.deploy.service_units import service_units  # noqa: E402
units = [(u["compose"], u["folder"]) for u in service_units("/opt", {})]
assert len(units) >= 8, units
for container, folder in units:
    text = open(os.path.join(REPO, "fabricctl", "jinja", folder, "docker-compose.yml.j2")).read()
    assert re.search(rf"^\s+container_name: {re.escape(container)}\s*$", text, re.M), (folder, container)
print('every unit waits on a container its compose file defines')
print('all templates rendered')

# every fabricctl module imports (a syntax error there only shows in a full install otherwise)
import importlib  # noqa: E402
import pkgutil  # noqa: E402
import fabriclib  # noqa: E402
for mod in pkgutil.walk_packages(fabriclib.__path__, "fabriclib."):
    if not mod.name.endswith(".cli"):
        importlib.import_module(mod.name)
print('every fabriclib module imports')

# 802.1X guides: the Windows scripts carry the root CA, pin the server by name and root thumbprint,
# and hold a well-formed LAN profile; PowerShell here-strings close at column 0; CRLF; public data only
import subprocess as _sp  # noqa: E402
import tempfile as _tf  # noqa: E402
import xml.etree.ElementTree as _ET  # noqa: E402
from fabriclib.radius.radius_guides import radius_guides  # noqa: E402
with _tf.TemporaryDirectory() as _d:
    _sp.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{_d}/k", "-out", f"{_d}/c",
             "-days", "1", "-subj", "/CN=Guide Root"], check=True, capture_output=True)
    _pem = open(f"{_d}/c").read()
    _sha1 = _sp.run(["openssl", "x509", "-in", f"{_d}/c", "-noout", "-fingerprint", "-sha1"],
                    capture_output=True, text=True, check=True).stdout.split("=", 1)[1].strip().lower().replace(":", " ")
_g = radius_guides({**v2, "radius_clients": rclients}, root_pem=_pem)
for _m, _mode in (("tls", "machine"), ("ttls", "user")):
    _s = _g["windows"][_m]["script"]
    assert "\r\n" in _s and "\n" not in _s.replace("\r\n", ""), "CRLF line ends for Windows"
    _t = _s.replace("\r\n", "\n")
    assert _pem.strip() in _t and _g["server_name"] in _t and _sha1 in _t, (_m, _sha1)
    assert _t.count("@'\n") == 2 and _t.count("\n'@") == 2, "here-strings must open and close on their own lines"
    _xml = _t.split("Set-Content -Path $xml -Encoding Ascii -Value @'\n", 1)[1].split("'@", 1)[0]
    _root = _ET.fromstring(_xml.split("?>", 1)[1])
    assert _root.tag.endswith("LANProfile") and f"<authMode>{_mode}</authMode>" in _xml
    assert "Rr1" not in _t and "Sw1tchSecret" not in _t and "PRIVATE KEY" not in _t, "public data only"
assert "-Pfx" in _g["windows"]["tls"]["script"] and "<Type xmlns=\"http://www.microsoft.com/provisioning/EapCommon\">21<" \
    in _g["windows"]["ttls"]["script"] and "<PAPAuthentication />" in _g["windows"]["ttls"]["script"]
print("802.1X guides: Windows scripts (CA, pinned server, well-formed profiles, CRLF, public data only)")

# every fabricctl command on an install reaches cli.py: manage.sh hands it all its arguments (none: the menu)
_manage = open(os.path.join(REPO, "fabricctl", "lib", "manage.sh")).read()
assert 'exec python3 "$FABRIC_DIR/lib/fabriclib/cli.py" "$@"' in _manage and "set -- --interactive" in _manage
_cli = open(os.path.join(REPO, "fabricctl", "lib", "fabriclib", "cli.py")).read()
for _flag in ("--mint-certs", "--service-cert", "--render-jinja", "--print", "--interactive", "--apply",
              "--update-containers", "--client-cert", "--keycloak-sync", "--version"):
    assert f'"{_flag}"' in _cli, f"cli.py does not route {_flag}"
print('every fabricctl subcommand and flag reaches cli.py')
