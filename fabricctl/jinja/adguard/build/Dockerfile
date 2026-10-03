# AdGuard Home without file capabilities (manual 2.4.1.5).
#
# The upstream binary carries file capabilities (net_bind_service, net_raw) so it can bind 53 as non-root.
# fabric runs it on an unprivileged port inside the container with every capability dropped, and the
# kernel refuses to exec a binary whose file capabilities cannot be granted ("operation not permitted").
# A plain copy carries no security.capability attribute, so this layer is the same program without them.
# No network is needed to build it. The base is always given by the compose file: the digest-pinned ref
# from images.lock.yaml (image_adguard), so an upstream push never changes what runs.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
RUN cp /opt/adguardhome/AdGuardHome /tmp/AdGuardHome && mv /tmp/AdGuardHome /opt/adguardhome/AdGuardHome
