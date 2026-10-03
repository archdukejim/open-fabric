# fabric web UI — its own unprivileged container.
#
# Only the web app lives here (TLS header checks, Keycloak OIDC, sessions,
# HTML). It has no Docker socket and no host access: every action is a call
# to fabric-agent on the host over a mounted unix socket.
#
# Debian packages only (python3 + jinja2 + openssl); `fabricctl images update`
# rebuilds it on a newer validated Debian base (and its security updates).
# The base is always given by the compose file: a digest-pinned ref from
# fabric/images.lock.yaml (no default, so an unpinned build cannot happen).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"

ARG WEBUI_UID=606
ARG WEBUI_GID=606
# the service account's ids are baked in: a change rebuilds (images/needs_rebuild)
LABEL org.fabric.ids="${WEBUI_UID}:${WEBUI_GID}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-jinja2 openssl ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -o -g "$WEBUI_GID" webui \
 && useradd -o -r -M -u "$WEBUI_UID" -g "$WEBUI_GID" -d /nonexistent -s /usr/sbin/nologin webui

# app/ is fabric/lib/webui, copied into the build context at deploy time.
COPY app/ /app/webui/

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER webui
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/python3", "/app/webui/server.py", "--config", "/config/webui.json"]
