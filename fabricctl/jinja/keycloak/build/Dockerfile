# Keycloak, pre-built ("optimized"). Build-time options are baked in here so
# the container starts with `start --optimized`: no Quarkus re-augmentation
# at every boot, which (a) lets the root filesystem be read-only and (b)
# makes startup much faster on a Raspberry Pi.
#
# Changing any build-time option below requires rebuilding this image.
# The base is always given by the compose file: a digest-pinned ref from
# fabric/images.lock.yaml (no default, so an unpinned build cannot happen).
ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS builder

ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=false
RUN /opt/keycloak/bin/kc.sh build

FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"
COPY --from=builder /opt/keycloak/ /opt/keycloak/
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized"]
