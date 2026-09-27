# fabric web UI — its own unprivileged container.
#
# Only the web app lives here (TLS header checks, Keycloak OIDC, sessions,
# HTML). It has no Docker socket and no host access: every action is a call
# to fabric-agent on the host over a mounted unix socket.
#
# Debian packages only (python3 + jinja2 + openssl); rebuilt with
# `docker compose build --pull` to pick up security updates.
FROM debian:trixie-slim

ARG WEBUI_UID=912
ARG WEBUI_GID=912

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
