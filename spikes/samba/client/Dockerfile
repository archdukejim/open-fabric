# S0 spike Q9 (manual 5.8.1.5) — throwaway. An Ubuntu 24.04 client (fabric's Linux target) joining AD with adcli
# and getting identities, Kerberos and sudo rules from it through SSSD.
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      sssd-ad sssd-tools adcli krb5-user sudo libsss-sudo dnsutils ca-certificates \
 && rm -rf /var/lib/apt/lists/*
