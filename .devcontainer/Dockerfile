FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
USER root
# Base image ships a yarn apt source whose key has expired (NO_PUBKEY 62D54FD4003F6525);
# it breaks apt-get update in devcontainer features (sshd). Yarn is not used.
RUN rm -f /etc/apt/sources.list.d/yarn.list
COPY .devcontainer/requirements-security.lock /tmp/requirements-security.lock
COPY requirements-console.txt requirements.lock requirements-dev.lock requirements-retrieval.txt /tmp/metis-requirements/
RUN python -m venv /opt/metis-venv \
    && /opt/metis-venv/bin/pip install --no-cache-dir -r /tmp/metis-requirements/requirements-dev.lock \
    && python -m venv /opt/security-venv \
    && /opt/security-venv/bin/pip install --no-cache-dir -r /tmp/requirements-security.lock \
    && /opt/security-venv/bin/pip check \
    && SEMGREP_SEND_METRICS=off SEMGREP_ENABLE_VERSION_CHECK=0 /opt/security-venv/bin/semgrep --version \
    && /opt/security-venv/bin/bandit --version
COPY .devcontainer/semgrep.yml /opt/metis-security-rules.yml
ENV PATH="/opt/metis-venv/bin:/opt/security-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    SEMGREP_SEND_METRICS=off \
    SEMGREP_ENABLE_VERSION_CHECK=0
