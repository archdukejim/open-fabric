# fabricctl

The Linux host side of fabric: the `fabricctl` command, the root
`fabric-agent` daemon, the installer (`fabricctl setup`) and the templates
for every service it deploys. Installed as `/usr/lib/fabricctl/fabric/`
and, by `fabricctl setup`, `/opt/fabric/` (see `installers/deb/`).

| Path | What |
|---|---|
| `VERSION` | fabricctl's version (the .deb version and the `v<VERSION>` release tag) |
| `images.lock.yaml` | The validated container images, pinned by digest, and the pinned packages built into fabric's own images |
| `link-vars-template.yaml` | The landing page's default links (used until the admin saves their own) |
| [lib/](lib/) | The code: `fabriclib` (one function per file), `fabric-agent`, the deploy engine, shell helpers |
| [jinja/](jinja/) | Templates for every service's configuration, compose file and systemd unit |
| [examples/](examples/) | A starting `vars.yaml` |

The web UI (control plane) is in `webui/` at the repository root; the
package puts it at `lib/webui/` here.
