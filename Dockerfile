FROM python:3.14.8-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

LABEL org.opencontainers.image.title="proxmox-discord-notifier"
LABEL org.opencontainers.image.description="Proxmox Discord notifier service"
LABEL org.opencontainers.image.source="https://github.com/Skulldorom/proxmox-discord-notifier"
LABEL org.opencontainers.image.licenses="MIT"

ARG APP_DIR=/opt/proxmox-discord-notifier
ARG UID=10001
ARG GID=10001
ENV PYTHONUNBUFFERED=1 \
    TZ=UTC \
    LOG_RETENTION_DAYS=30 \
    LOG_DIRECTORY=/var/logs/p2d \
    UV_PROJECT_ENVIRONMENT=${APP_DIR}/.venv \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.8.22@sha256:9874eb7afe5ca16c363fe80b294fe700e460df29a55532bbfea234a0f12eddb1 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${GID} notifier \
    && useradd --uid ${UID} --gid notifier --create-home --home-dir /home/notifier --shell /usr/sbin/nologin notifier \
    && mkdir -p ${APP_DIR} ${LOG_DIRECTORY} \
    && chown notifier:notifier ${APP_DIR} ${LOG_DIRECTORY}

WORKDIR ${APP_DIR}
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python3
COPY --chown=notifier:notifier . ./
RUN uv sync --locked --no-dev --python /usr/local/bin/python3 && chown -R notifier:notifier ${APP_DIR}

VOLUME ["/var/logs/p2d"]
USER notifier:notifier
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:6068/health')" || exit 1
EXPOSE 6068
CMD [".venv/bin/proxmox-discord-notifier", "--host", "0.0.0.0", "--port", "6068"]
