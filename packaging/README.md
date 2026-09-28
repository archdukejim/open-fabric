# packaging

How fabricctl is built into an installable package.

| File | What |
|---|---|
| `build-deb.sh` | Build `dist/fabricctl_<version>_all.deb` from this checkout (one package for amd64 and arm64) |
| `deb/control.in` | Package metadata; `@VERSION@` is filled in by `build-deb.sh` |
| `deb/fabricctl` | `/usr/bin/fabricctl`: `setup`/`reinstall`/`uninstall` run the packaged code, everything else the deployed install |
| `deb/postinst` | Prints the next step; never starts services or touches the network |

Layout on the host:

| Path | From |
|---|---|
| `/usr/lib/fabricctl/{fabric,docs}` | the package (read-only source) |
| `/usr/bin/fabricctl` | the package |
| `/usr/share/doc/fabricctl/examples/vars.yaml` | the package (`custom-vars-tpl.yml`) |
| `/opt/fabric`, `/opt/<service>` | `fabricctl setup` (the install) |
| `/etc/systemd/system/*.service`, `fabric.target` | `fabricctl setup` |

Upgrade: install the newer `.deb`, then `sudo fabricctl setup` (every other
command warns until you do). `apt remove fabricctl` removes the tool, not the
install; `sudo fabricctl uninstall` removes the install.
