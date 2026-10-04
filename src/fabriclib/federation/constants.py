import re

# A site name: one host-name label. It names the site's local directory suffix (o=<site_name>), its
# intermediate CA ("<site_name> Intermediate CA") and the default branch domain <site_name>.<domain>.
SITE_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

INVITE_PREFIX = "fabric-join-1."     # an invitation: this prefix + base64url(JSON), see create_invitation
INVITE_TTL_SECONDS = 3600            # an invitation is good for one join within an hour
JOIN_BODY_MAX = 16384                # the join request is small: names, a CSR, the secret
# A DNS name of two or more labels, lower case (a site's domain, the organisation domain, a host name).
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$")

# The organisation's base DN (ldap_base_dn): dc= or o= first, then dc= labels, lower case (dc=lan, o=acme,
# dc=lan,dc=example,dc=com). Chosen at the root site's install, the same at every site.
BASE_DN_RE = re.compile(r"^(dc|o)=[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(,dc=[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")

