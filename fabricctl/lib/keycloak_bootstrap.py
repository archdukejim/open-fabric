#!/usr/bin/env python3
"""Idempotently configure Keycloak for fabric (fabriclib/keycloak/configure_keycloak.py).

  sudo python3 keycloak_bootstrap.py [--vars /opt/fabric/config/vars.yaml]
                                     [--secrets /opt/fabric/config/fabric-secrets.yml]

Talks to the Keycloak admin REST API over TLS pinned to the core root CA (no credentials on any command line).
Safe to re-run: it converges. Run by setup's start step, `fabricctl --keycloak-sync` and tests/keycloak/run.sh.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fabriclib.keycloak.configure_keycloak import configure_keycloak  # noqa: E402


def main():
    """Purpose: parse the command line and configure Keycloak.
    Inputs:  --vars (default /opt/fabric/config/vars.yaml), --secrets (default /opt/fabric/config/fabric-secrets.yml).
    Returns: None.
    Fails:   argparse exits 2 on bad arguments; whatever configure_keycloak raises (SystemExit with the message).
    Feeds:   `python3 keycloak_bootstrap.py`."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", default="/opt/fabric/config/vars.yaml")
    ap.add_argument("--secrets", default="/opt/fabric/config/fabric-secrets.yml")
    args = ap.parse_args()
    configure_keycloak(args.vars, args.secrets)


if __name__ == "__main__":
    main()
