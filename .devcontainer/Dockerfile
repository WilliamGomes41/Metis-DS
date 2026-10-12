# Stage "workspace": editor/Codespace container (has egress, no heavy test assets).
# Stage "runner": isolated test runner. Everything the offline security tests
# need is downloaded HERE, at BUILD time; at runtime the runner has no egress
# (scripts/security_sandbox.py assert_isolated_network / NET-01).
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm AS workspace
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

FROM workspace AS runner
ARG PLAYWRIGHT_VERSION=1.63.0
ARG OSV_SCANNER_VERSION=v2.7.0
ARG OSV_SCANNER_SHA256=160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b
# PI-05 local model: SmolLM2-135M-Instruct (~270 MB, CPU-friendly on 2 cores), pinned commit.
ARG PI05_MODEL_REPO=HuggingFaceTB/SmolLM2-135M-Instruct
ARG PI05_MODEL_REVISION=12fd25f77366fa6b3b4b768ec3050bf629380bac
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    METIS_DOCLING_PYTHON=/opt/docling/bin/python \
    METIS_DOCLING_ARTIFACTS_PATH=/opt/docling-models \
    METIS_PI05_MODEL_PATH=/opt/models/smollm2-135m-instruct \
    OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=/opt/osv-db \
    HF_HOME=/opt/hf-home
# 1. Playwright + headless Chromium (with OS deps), isolated venv.
RUN python -m venv /opt/playwright-venv \
    && /opt/playwright-venv/bin/pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}" \
    && /opt/playwright-venv/bin/playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /opt/ms-playwright
# 2. Docling: same recipe/pins as Dockerfile.docling (torch CPU), models + manifest baked in.
COPY requirements-docling.txt requirements-docling.lock /tmp/metis-requirements/
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-urw-base35 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/docling \
    && /opt/docling/bin/pip install --no-cache-dir torch==2.14.1+cpu torchvision==0.29.1+cpu --index-url https://download.pytorch.org/whl/cpu \
    && /opt/docling/bin/pip install --no-cache-dir -r /tmp/metis-requirements/requirements-docling.lock \
    && /opt/docling/bin/pip check
COPY scripts/prepare_docling_models.py /tmp/docling-prep/scripts/
COPY src/__init__.py src/docling_contract_v1.py src/docling_render_fonts_v1.py /tmp/docling-prep/src/
RUN /opt/docling/bin/python /tmp/docling-prep/scripts/prepare_docling_models.py /opt/docling-models \
    && rm -rf /tmp/docling-prep /root/.cache \
    && mkdir -p /opt/hf-home
# 3. PI-05 small local model (transformers, runs in the docling venv: torch CPU + transformers).
RUN /opt/docling/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='${PI05_MODEL_REPO}', revision='${PI05_MODEL_REVISION}', local_dir='${METIS_PI05_MODEL_PATH}', allow_patterns=['*.json','*.safetensors','*.txt','merges.txt','vocab.json'])" \
    && rm -rf /root/.cache "${METIS_PI05_MODEL_PATH}/.cache" \
    && HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/docling/bin/python -c "from transformers import AutoTokenizer, AutoModelForCausalLM; p='${METIS_PI05_MODEL_PATH}'; AutoTokenizer.from_pretrained(p); AutoModelForCausalLM.from_pretrained(p)"
# 5. osv-scanner (checksum-pinned) + offline PyPI vulnerability DB, downloaded now.
RUN curl -fsSL -o /usr/local/bin/osv-scanner \
        "https://github.com/google/osv-scanner/releases/download/${OSV_SCANNER_VERSION}/osv-scanner_linux_amd64" \
    && echo "${OSV_SCANNER_SHA256}  /usr/local/bin/osv-scanner" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/osv-scanner \
    && mkdir -p /opt/osv-db/osv-scanner/PyPI \
    && curl -fsSL -o /opt/osv-db/osv-scanner/PyPI/all.zip \
        https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip \
    && chmod -R a+rX /opt/osv-db \
    && (osv-scanner scan --offline-vulnerabilities -L requirements.txt:/tmp/metis-requirements/requirements.lock >/dev/null; rc=$?; test "$rc" -le 1)
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1
