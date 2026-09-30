# installers/deb

The Debian package: a wrapper that turns the repository's product folders
(`fabricctl/`, `webui/`) into an installable `fabricctl` .deb.

| File | What |
|---|---|
| `assemble-tree.sh` | Assemble the installed tree from `fabricctl/` and `webui/` (the one place that knows the mapping; tests use it too) |
| `build-deb.sh` | Build `dist/fabricctl_<version>_all.deb` from this checkout (one package for amd64 and arm64) |
| `install-from-checkout.sh` | Build the .deb from this checkout, install it with apt, run `fabricctl setup` (development installs) |
| `control.in` | Package metadata; `@VERSION@` is filled in by `build-deb.sh` |
| `fabricctl` | `/usr/bin/fabricctl`: `setup`/`reinstall`/`uninstall`/`restore` and help run the packaged code, everything else the deployed install |
| `postinst` | Prints the next step; never starts services or touches the network |
| `postrm` | `remove`: leaves the install running and untouched; `purge`: export to `/var/backups/fabric/`, then uninstall |

Repository → host:

| Repository | On the host |
|---|---|
| `fabricctl/` (not `examples/`) | `/usr/lib/fabricctl/fabric/` |
| `webui/` (the app; not `Dockerfile`, `.dockerignore`) | `/usr/lib/fabricctl/fabric/lib/webui/` |
| `webui/Dockerfile`, `.dockerignore` | `/usr/lib/fabricctl/fabric/jinja/webui/build/` |
| `docs/`, `LICENSE`, `README.md` | `/usr/lib/fabricctl/` |
| `fabricctl/examples/vars.yaml` | `/usr/share/doc/fabricctl/examples/vars.yaml` |
| `installers/deb/fabricctl` | `/usr/bin/fabricctl` |

`fabricctl setup` then copies `/usr/lib/fabricctl/fabric` to `/opt/fabric` (the
install) and creates `/opt/<service>`, the systemd units and `fabric.target`.
The installed layout did not change when the repository was split (design
D25), so existing installs upgrade in place.

Upgrade: install the newer `.deb`, then `sudo fabricctl setup` (every other
command warns until you do). To remove fabric use `sudo fabricctl uninstall`:
it offers to export all data to a folder you choose and to purge the package.
`sudo apt remove fabricctl` removes only the tool (fabric keeps running);
`sudo apt purge fabricctl` removes fabric too, after exporting its data to
`/var/backups/fabric/` because apt cannot ask where.
