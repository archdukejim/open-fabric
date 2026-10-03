# fabric manual

The manual is fabric's only source of truth: architecture, decisions, procedures and notes (global Rule 5).

## [Volume 1 — Systems and services](volume_1_systems_and_services/README.md)

- 1.1 Product overview
- 1.2 Decision register
- 1.3 Architecture
- 1.4 fabricctl and fabric-agent
- 1.5 Open Fabric web UI
- 1.6 Identity: directory and sign-in
- 1.7 Secrets: OpenBao
- 1.8 Federation

## [Volume 2 — Technologies and features](volume_2_technologies_and_features/README.md)

- 2.1 Settings reference
- 2.2 DHCP: Kea
- 2.3 802.1X: FreeRADIUS
- 2.4 DNS filter: AdGuard Home
- 2.5 Time: chrony
- 2.6 Container images
- 2.7 Host changes and consent
- 2.8 Log forwarding: Fluent Bit
- 2.9 Disk encryption
- 2.10 Joining Linux machines
- 2.11 Windows domain: Samba AD

## [Volume 3 — Operations](volume_3_operations/README.md)

- 3.1 Working with fabricctl
- 3.2 DNS
- 3.3 Certificates
- 3.4 DHCP
- 3.5 802.1X
- 3.6 DNS filter
- 3.7 Time
- 3.8 People and identities
- 3.9 Federation
- 3.10 OpenBao
- 3.11 Images
- 3.12 Log forwarding
- 3.13 The web UI
- 3.14 Lifecycle, status and ports

## [Volume 4 — Infrequent operations](volume_4_infrequent_ops/README.md)

- 4.1 Installation
- 4.2 Joining an existing fabric
- 4.3 Upgrades, rebuilds, reinstall, uninstall and restore
- 4.4 Subordinate CA
- 4.5 Disk encryption setup
- 4.6 Host maintenance
- 4.8 Testing
- 4.9 Development

## [Volume 5 — Notes and troubleshooting](volume_5_notes_and_troubleshooting/README.md)

- 5.1 Manual alignment
- 5.2 Stale-code register
- 5.3 Review findings
- 5.5 Reasoning and trade-offs
- 5.6 Troubleshooting

---

**Temporary, until the alignment is done ([5.1.1](volume_5_notes_and_troubleshooting/5.1.1-alignment-plan.md)):**
still outside the volumes; removed from this index when they have moved.

| Folder | What | Moves to |
|---|---|---|
| [`lib-doc/`](lib-doc/README.md) | Function reference, generated from the code's docstrings (`python3 tests/docs/gen_lib_doc.py`) | 1.11 |
| [`maintenance/`](maintenance/README.md) | `review-ledger.tsv`: when each file was last reviewed (read by `tests/docs/review_ledger.py`) | 5.3 |
