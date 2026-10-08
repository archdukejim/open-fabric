# packaging/apt

fabric's signed apt repository on GitHub Pages (manual 1.4.1.1, decision D7), built by `.github/workflows/package.yml`.

| File | What |
|---|---|
| `distributions` | reprepro's suites: `stable` (released packages) and `testing` (a release candidate's), `amd64 arm64`, component `main` |
| `build-repo.sh` | Build the signed repository from the released `.deb` files (and a candidate's): only `dists/`, `pool/`, `public.key` and an `index.html` (how to add it, the key's fingerprint) are written out |
