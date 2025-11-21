FROM python:3.12.11-slim-bookworm

LABEL org.opencontainers.image.title="proxmox-discord-notifier"
LABEL org.opencontainers.image.description="Proxmox Discord notifier service"
LABEL org.opencontainers.image.authors="Skulldorom <51134009+Skulldorom@users.noreply.github.com>"
LABEL org.opencontainers.image.url="https://github.com/Skulldorom/proxmox2discord"
LABEL org.opencontainers.image.source="https://github.com/Skulldorom/proxmox2discord"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV LOG_RETENTION_DAYS=30

ARG APP_DIR=/opt/proxmox-discord-notifier
ENV LOG_DIRECTORY=/var/logs/p2d

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN mkdir -p ${LOG_DIRECTORY}

WORKDIR $APP_DIR

RUN apt-get update && \
    apt-get install -y tzdata  && \
    apt-get clean

ADD . $APP_DIR/

RUN uv sync --locked

RUN printf '#!/bin/sh\n' > /usr/local/bin/docker-entrypoint.sh \
 && printf 'if [ -n "$TZ" ]; then \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime; \
    echo "$TZ" > /etc/timezone; \
 fi\n' >> /usr/local/bin/docker-entrypoint.sh \
 && printf 'exec "$@"\n' >> /usr/local/bin/docker-entrypoint.sh \
 && chmod +x /usr/local/bin/docker-entrypoint.sh


EXPOSE 6068
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "proxmox-discord-notifier", "--host", "0.0.0.0", "--port", "6068"]