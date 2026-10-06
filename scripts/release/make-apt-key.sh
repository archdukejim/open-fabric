#!/bin/bash
# -----------------------------------------------------------------------
# Make fabric's apt repository signing key, once (manual 1.4.1.1, D7, 4.7.1):
# a dedicated Ed25519 signing key that expires in two years, with a random
# passphrase. Both go into this repository's Actions secrets
# (GPG_PRIVATE_KEY, GPG_PASSPHRASE) through `gh secret set` on standard input,
# never a command line; the key exists nowhere else. Its revocation
# certificate is written to the folder you name: keep it offline.
#
#   bash scripts/release/make-apt-key.sh <folder for the revocation certificate>
#
# Needs gpg and an authenticated `gh` with admin rights on the repository.
# Run it by hand (the repository's owner): agents do not handle signing keys.
# -----------------------------------------------------------------------
set -euo pipefail
KEEP="${1:?usage: make-apt-key.sh <folder for the revocation certificate>}"
REPO="${FABRIC_REPO:-archdukejim/open-fabric}"
mkdir -p "$KEEP"
export GNUPGHOME
GNUPGHOME="$(mktemp -d)"
trap 'gpgconf --kill gpg-agent 2>/dev/null; rm -rf "$GNUPGHOME"' EXIT
umask 077

PASS="$(head -c 32 /dev/urandom | base64 | tr -d '/+=')"
printf '%s' "$PASS" > "$GNUPGHOME/pass"
gpg --batch --pinentry-mode loopback --passphrase-file "$GNUPGHOME/pass" \
    --quick-generate-key "open-fabric apt repository <apt@open-fabric.invalid>" ed25519 sign 2y
FPR="$(gpg --batch --with-colons --list-secret-keys | awk -F: '$1 == "fpr" {print $10; exit}')"

gpg --batch --pinentry-mode loopback --passphrase-file "$GNUPGHOME/pass" --armor \
    --export-secret-keys "$FPR" | gh secret set GPG_PRIVATE_KEY --repo "$REPO"
gh secret set GPG_PASSPHRASE --repo "$REPO" < "$GNUPGHOME/pass"
cp "$GNUPGHOME/openpgp-revocs.d/$FPR.rev" "$KEEP/open-fabric-apt-$FPR.rev"
gpg --batch --armor --export "$FPR" > "$KEEP/open-fabric-apt-public.key"

echo "signing key $FPR stored as GPG_PRIVATE_KEY and GPG_PASSPHRASE in $REPO's Actions secrets"
echo "revocation certificate: $KEEP/open-fabric-apt-$FPR.rev  (keep it offline; it revokes the key if it leaks)"
echo "public key (also published with the repository): $KEEP/open-fabric-apt-public.key"
