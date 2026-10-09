# templates/resolver/config

Rendered into `<base>/resolver/config` by `dns_filter/deploy_resolver` (manual [1.12.2](../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11225-the-main-view)).

| File | What |
|---|---|
| `named.conf.j2` | The resolver: clients allowed, DoT upstreams, fabric's zones forwarded to the authoritative BIND, the response policy order, the query and RPZ logs |
| `fabric.rpz.j2` | Passthru for fabric's own zones: first, so they are never filtered |
| `owner.rpz.j2` | The owner's allows and blocks (`dns_filter_allow`, `dns_filter_block`) |
| `rndc.key.j2` | The resolver's own control key (`resolver_rndc_secret`) |
