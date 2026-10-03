# Volume 1 — Systems and services

Architecture, services, APIs and runtime infrastructure.

## 1.1 Product overview

- [1.1.1 What fabric is](1.1.1-what-fabric-is.md)
- [1.1.2 Where fabric came from](1.1.2-history.md)
- [1.1.3 Phases](1.1.3-phases.md)

## 1.2 Decision register

Every decision that shapes fabric, with an identifier never reused (Rule 13). Recorded decisions are rules for this repository.

- [1.2.1 Product decisions D1–D25](1.2.1-product-decisions.md)
- [1.2.2 Early design decisions D26–D59 (the checklist)](1.2.2-checklist-answers.md)
- [1.2.3 Deviations from the global rules](1.2.3-deviations.md)
- [1.2.4 Federation decisions F1–F10 (D60–D69, in order)](1.2.4-federation-decisions.md)
- [1.2.5 Domain-join decisions J1–J3 (D70–D72, in order)](1.2.5-domain-join-decisions.md)
- [1.2.6 Samba decisions S1–S6 (D73–D78, in order)](1.2.6-samba-decisions.md)

## 1.3 Architecture

- [1.3.1 System topology and request flows](1.3.1-topology.md)
- [1.3.2 Repository layout](1.3.2-repository-layout.md)
- [1.3.3 Installed layout](1.3.3-installed-layout.md)
- [1.3.4 Containers: hardening and resources](1.3.4-containers.md)
- [1.3.5 DNS architecture](1.3.5-dns-architecture.md)
- [1.3.6 PKI chain and certificate relay](1.3.6-pki-chain.md)
- [1.3.7 Templates](1.3.7-templates.md)
- [1.3.8 Targets and hardening](1.3.8-targets-and-hardening.md)

## 1.4 fabricctl and fabric-agent

- [1.4.1 The host package](1.4.1-host-package.md)
- [1.4.2 Setup: secure by default, scriptable](1.4.2-setup-design.md)

## 1.5 Open Fabric web UI

- [1.5.1 Architecture and components](1.5.1-webui-architecture.md)
- [1.5.2 Security model and who may do what](1.5.2-webui-security.md)
- [1.5.3 The fixed API](1.5.3-agent-api.md)
- [1.5.4 The web UI as the single pane](1.5.4-single-pane.md)
- [1.5.5 Access control for people across the stack](1.5.5-rbac.md)

## 1.6 Identity: directory and sign-in

- [1.6.1 389 Directory Server](1.6.1-directory.md)
- [1.6.2 Keycloak](1.6.2-keycloak.md)

## 1.7 Secrets: OpenBao

- [1.7.1 OpenBao](1.7.1-openbao.md)

## 1.8 Federation

- [1.8.1 Sites, terms and ownership](1.8.1-sites.md)
- [1.8.2 Services within a site: HA partners](1.8.2-ha-partners.md)
- [1.8.3 Services between sites](1.8.3-between-sites.md)
- [1.8.4 Joining and the federation endpoint](1.8.4-joining.md)
- [1.8.5 Attachment: flat, relay, nested](1.8.5-attachment.md)
- [1.8.6 What changes in fabric](1.8.6-changes.md)
- [1.8.7 Phases and milestones](1.8.7-milestones.md)
