# fabriclib/federation

Sites joined into one fabric: an upstream that owns identity and the root CA, downstream sites with
their own local network (design [federation.md](../../../../docs/design/federation.md)).

| File | What |
|---|---|
| `constants.py` | The site-name, domain and base-DN rules, the invitation format and lifetime, the join body limit |
| `create_invitation.py` | Upstream: a one-time invitation for a new site (only a hash of its secret is kept; audited) |
| `list_invitations.py` | Upstream: the open invitations, without their secrets |
| `revoke_invitation.py` | Upstream: withdraw an open invitation (audited) |
| `accept_join.py` | Upstream: an invited site joins — check the invitation, sign the site's CA with the root key, record the site |
| `decode_invitation.py` | Joining node: read and check an invitation (no network) |
| `join_upstream.py` | Joining node: make the site CA request, pin the upstream's root, join over verified TLS, stage the CA, record the upstream |
| `relay_join.py` | On a relay node: pass a join that names it (`via`) on to its upstream and return the answer unchanged |
| `drop_relay.py` | On a site that joined through a relay: talk to the upstream directly from now on |
| `remove_site.py` | On a parent: forget a site that joined here (its CA stays valid until it expires: no revocation yet) |
| `reparent_site.py` | On a site: move under another parent with its invitation — new CA, Step-CA switched, certificates re-issued |
| `dns_links.py` | The DNS links to the sites next to this one (delegation, secondary zones, TSIG keys) for the BIND templates |
| `federation_status.py` | Standalone, upstream or site; the endpoint; joined sites; open invitations |
| `set_federation_endpoint.py` | Turn the federation endpoint on or off (certificate first) and apply |
| `deploy_federation_endpoint.py` | Deploy step: the `fabric-federation` unit and the socket directory nginx mounts (or their removal) |
| `run_federation_command.py` | `fabricctl federation status / enable / disable / invite / invitations / revoke` |
| `common/` | Helpers shared by the operations above (see its README) |
