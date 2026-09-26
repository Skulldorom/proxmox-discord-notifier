# proxmox-discord-notifier

Reliable Proxmox Backup and VM Log Notifications in Discord

![alt text](image.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<p align="center">
  <a href="https://ko-fi.com/skulldorom"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support me on Ko-fi" /></a>
</p>

## Overview

Discord enforces a 2000‑character limit per message, which can truncate lengthy Proxmox backup logs or VM events and obscure critical details. **proxmox-discord-notifier** solves this by:

- Capturing full Proxmox output in raw log files.
- Sending concise Discord notifications with a link to the complete log.

Whether you run nightly backups or ad‑hoc snapshots, **proxmox-discord-notifier** ensures you never miss important context.

## Features

- **Raw Log Storage** — Saves complete Proxmox logs in a configurable directory.
- **Discord Embeds** — Sends rich notifications with title, severity, custom description, and log link.
- **Optional User Mentions** — Include a Discord user ID to automatically @mention a specific user in the alert.
- **Configurable Retention** — Auto-cleanup of old logs after _N_ days (default: 30 days; set to 0 to keep forever).
- **Dark-Mode Log Viewer** — Built-in HTML log viewer with dark theme for browsers.
- **Health Endpoint** — `/health` probe for orchestrator readiness/liveness checks.
- **Security Hardened** — Optional bearer authentication, signed expiring log links, SSRF protection, strict mention controls, and request-size limits.
- **Non-root Container** — The production process runs as the unprivileged `notifier` user and writes only to its configured log volume.
- **Lightweight** — Single Python package on FastAPI; managed with `uv`.
- **Docker‑Ready** — Stable Python runtime with a health check and persistent log volume support.
- **Tested** — Configuration, endpoints, Discord delivery, cleanup, and schema behavior are covered by automated tests.

## Prerequisites

- Docker _(or Python 3.12+ with `uv`)_

## Quickstart

### Using Docker

```bash
docker run -d \
  --name proxmox-discord-notifier \
  --restart unless-stopped \
  -e TZ=UTC \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e NOTIFIER_API_TOKEN="replace-with-a-long-random-secret" \
  -e LOG_SIGNING_SECRET="replace-with-a-different-32-character-minimum-secret" \
  -e LOG_RETENTION_DAYS=30 \
  -p 6068:6068 \
  -v p2d_logs:/var/logs/p2d \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

Or with Docker Compose:

```yaml
services:
  proxmox-discord-notifier:
    container_name: proxmox-discord-notifier
    image: ghcr.io/skulldorom/proxmox-discord-notifier:latest
    restart: unless-stopped
    volumes:
      - p2d_logs:/var/logs/p2d
    environment:
      - TZ=UTC
      - DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
      - NOTIFIER_API_TOKEN=replace-with-a-long-random-secret
      - LOG_SIGNING_SECRET=replace-with-a-different-32-character-minimum-secret
      - LOG_RETENTION_DAYS=30
    ports:
      - "6068:6068"

volumes:
  p2d_logs:
    name: p2d_logs
```

```bash
docker compose up -d
```

### Verify

| Check | What |
|-------|------|
| Interactive API docs | [http://<YOUR_HOST>:6068/docs](http://<YOUR_HOST>:6068/docs) |
| Health probe | `curl http://<YOUR_HOST>:6068/health` → `{"status":"ok"}` |

The Docker image includes a `HEALTHCHECK` that pings `/health` every 30 seconds — orchestrators like Docker Swarm, Nomad, or k8s can use this for readiness probes.

## Proxmox Integration

Point your Proxmox cluster at the `/notify` endpoint so every alert is mirrored to Discord and archived.

### Configuration

Configure the notifier through environment variables. Keep all secrets outside request payloads and version control.

| Setting | Default | Behavior |
| --- | --- | --- |
| `DISCORD_WEBHOOK` | unset | Server-side Discord webhook. Required unless the high-risk request override is enabled. HTTPS Discord-owned webhook URLs only. |
| `NOTIFIER_API_TOKEN` | unset | When set, `POST /api/notify` requires `Authorization: Bearer <token>`. When unset, the endpoint is only appropriate on a trusted private network. |
| `ALLOW_REQUEST_WEBHOOK` | `false` | Rejects `discord_webhook` supplied in requests by default. Set to `true` only with `NOTIFIER_API_TOKEN` configured; validated request webhooks then override `DISCORD_WEBHOOK`. |
| `MAX_REQUEST_BYTES` | `10550000` | Maximum raw `POST /api/notify` body size in bytes. Oversize bodies return `413` before JSON parsing, log writes, or Discord delivery. Configure the same or smaller limit in a reverse proxy. |
| `BASE_URL` | unset | Optional valid HTTP(S) external URL used for log links. Trailing slashes are removed. Without it, the incoming request URL is used. |
| `LOG_RETENTION_DAYS` | `30` | Non-negative days to retain logs. `0` disables automatic deletion. |
| `LOG_SIGNING_SECRET` | unset | Dedicated minimum-32-character HMAC secret for log links. Required to create or view logs; keep stable across restarts so existing links remain valid. |
| `LOG_URL_TTL_HOURS` | `24` | Lifetime of Discord log links, from 1 hour through 365 days. |
| `TZ` | `UTC` | Container timezone. |

`LOG_SIGNING_SECRET`, `NOTIFIER_API_TOKEN`, and `DISCORD_WEBHOOK` have separate purposes and must use different secret values. New log URLs contain an expiry and HMAC signature; unsigned, altered, and expired URLs are rejected.

#### Custom Base URL (Behind Proxy)

If your service is behind a reverse proxy or accessed via a custom domain, set the `BASE_URL` environment variable to ensure log URLs are generated correctly:

```bash
# Docker
docker run -d \
  --name proxmox-discord-notifier \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e BASE_URL="https://your-domain.com" \
  -p 6068:6068 \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

```yaml
# docker-compose
environment:
  - DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
  - BASE_URL=https://your-domain.com
```

Without `BASE_URL`, log URLs are generated from the incoming request, which may not work correctly behind a proxy.

#### Log Retention

By default, logs are kept for 30 days and then automatically deleted. Configure with `LOG_RETENTION_DAYS`:

- **Default**: `30` (keeps logs for 30 days)
- **Never delete**: Set to `0` to keep logs forever
- **Custom duration**: Set to any positive number of days

```bash
# Keep logs for 7 days
docker run -d \
  --name proxmox-discord-notifier \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e LOG_RETENTION_DAYS=7 \
  -p 6068:6068 \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

The cleanup task runs automatically every 24 hours starting when the application launches.

### Secure Proxmox setup

Set `DISCORD_WEBHOOK`, `NOTIFIER_API_TOKEN`, and `LOG_SIGNING_SECRET` on the service. In the Proxmox notification target, configure the server URL and save the API token as a secret header value:

| UI Field | Value / Example |
| --- | --- |
| **Endpoint Name** | `proxmox-discord-notifier` |
| **Method** | `POST` |
| **URL** | `http://<API_SERVER_IP>:6068/api/notify` |
| **Headers** | `Content-Type: application/json` and `Authorization: Bearer <NOTIFIER_API_TOKEN>` |
| **Body** | <pre lang=json>{<br/> "title": "{{ title }}",<br/> "message": "{{ escape message }}",<br/> "severity": "{{ severity }}",<br/> "mention_user_id": "{{ secrets.user_id }}"<br/>}</pre> |
| **Secrets** | `NOTIFIER_API_TOKEN` and optional `user_id` (a 17–20 digit Discord user ID) |
| **Enable** | ✓ |

`GET /health` remains unauthenticated for Docker and orchestrator probes. Do not expose an unauthenticated notifier outside a trusted private network.

### Request webhook override (higher risk)

Requests containing `discord_webhook` are rejected by default. If per-request routing is required, set both `ALLOW_REQUEST_WEBHOOK=true` and `NOTIFIER_API_TOKEN`; authenticated requests may then supply a validated Discord HTTPS webhook, which overrides `DISCORD_WEBHOOK`. This expands the trust boundary and should be used only for trusted callers.

### Custom Embed Description

You can include a `discord_description` field (max 4096 characters) in the request body to add custom text to the Discord embed — useful for including truncated summaries or contextual notes alongside the full log link.

```json
{
  "title": "Backup Failed",
  "message": "...full 50KB Proxmox output...",
  "severity": "error",
  "discord_description": "VM 104 — nightly backup to NFS share timed out after 30 minutes"
}
```

## Development

### Setup

```bash
# Clone and install with uv
git clone https://github.com/Skulldorom/proxmox-discord-notifier.git
cd proxmox-discord-notifier
uv sync
```

### Run Locally

```bash
uv run proxmox-discord-notifier serve --host 127.0.0.1 --port 6068
```

Set `DISCORD_WEBHOOK` in your environment or create a `.vscode/launch.json` with an `envFile` for local development.

### Run Tests

```bash
uv run pytest -v
```

The test suite covers:
- **Config** — settings validation, webhook URL SSRF protection, base URL quoting
- **Endpoints** — notify flow, health check, log retrieval, error cases
- **Discord** — payload building, webhook delivery
- **Log Cleanup** — retention policies, edge cases
- **Schema** — validation, field limits, error messages

### Lint

```bash
uv run ruff check .
```

### Format

```bash
uv run ruff format .
```

## Credits

This project is maintained by [Skulldorom](https://github.com/Skulldorom). While this implementation represents a fresh approach to Proxmox-to-Discord notifications, it may build upon concepts and ideas from earlier community projects in the Proxmox ecosystem.

## License

Released under the [MIT License](LICENSE).

Copyright (c) 2025 Jordan Shaw
