# packaging

What builds fabric's release artifacts (global Rule 7.1).

| Path | What |
|---|---|
| [deb/](deb/) | The `fabricctl` Debian package |
| [images/](images/) | The build files of the images fabric builds itself (decision D41: published from CI) |
| [docker-bake.hcl](docker-bake.hcl) | The build matrix of those images: nine images, amd64 and arm64 (manual 4.7.1) |
