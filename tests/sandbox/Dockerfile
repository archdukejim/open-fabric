# A disposable "host" for end-to-end install tests: Ubuntu 24.04 with systemd
# as PID 1 and room for its own Docker daemon (fabricctl setup installs Docker
# itself, exactly as on a real machine). Run privileged; see run.sh.
FROM ubuntu:24.04
ENV container=docker DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends systemd systemd-sysv dbus iproute2 iptables ca-certificates curl \
    git sudo python3 procps kmod \
 && rm -rf /var/lib/apt/lists/* \
 && systemctl mask systemd-logind getty.target console-getty.service \
 && systemctl set-default multi-user.target
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
