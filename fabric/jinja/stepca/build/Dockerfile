# step-ca, hardened. The upstream /usr/local/bin/step-ca carries a file
# capability (cap_net_bind_service) so it could bind low ports. A container
# with no-new-privileges and every capability dropped refuses to exec such a
# binary ("Operation not permitted"). step-ca listens on 9000 and does not
# need it: copying the file drops the security.capability xattr.
ARG BASE_IMAGE=smallstep/step-ca:latest
FROM ${BASE_IMAGE}

USER root
RUN cp /usr/local/bin/step-ca /tmp/step-ca \
 && mv -f /tmp/step-ca /usr/local/bin/step-ca \
 && chmod 0755 /usr/local/bin/step-ca
USER step
