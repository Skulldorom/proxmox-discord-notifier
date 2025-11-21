# proxmox-discord-notifier

Reliable Proxmox Backup and VM Log Notifications in Discord

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

Discord enforces a 2000‑character limit per message, which can truncate lengthy Proxmox backup logs or VM events and obscure critical details. **Proxmox2Discord** solves this by:

- Capturing full Proxmox output in raw log files.
- Sending concise Discord notifications with a link to the complete log.

Whether you run nightly backups or ad‑hoc snapshots, **proxmox-discord-notifier** ensures you never miss important context.

## Features

- Raw Log Storage: Saves complete Proxmox logs in a configurable directory.
- Discord Embeds: Sends rich notifications with title, severity, and log link.
- Optional User Mentions: Include a Discord user ID to automatically @mention a specific user in the alert.
- Configurable Retention: Auto-cleanup of old logs after _N_ days (default: 30 days).
- Lightweight: Single Python package; minimal dependencies.
- Docker‑Ready: Official Dockerfile for fast deployment.

## Prerequisites

- Docker

## Quickstart

### Using Docker

Run with Docker.

```bash
docker run -d \
  --name proxmox-discord-notifier \
  --restart unless-stopped \
  -e TZ=UTC \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e LOG_RETENTION_DAYS=30 \
  -p 6068:6068 \
  -v p2d_logs:/var/logs/p2d \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

Optionally you can use docker-compose as well.

```
version: "3.9"

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

Open [http://<YOUR_HOST>:6068/docs](http://<YOUR_HOST>:6068/docs) for the interactive API docs.

## Proxmox Integration

Point your Proxmox cluster at the `/notify` endpoint so every alert is mirrored to Discord and archived.

### Configuration

The Discord webhook URL can be configured in two ways:

1. **Environment Variable** (Recommended): Set `DISCORD_WEBHOOK` in your Docker/environment
2. **Request Payload**: Include `discord_webhook` in each request (overrides environment variable)

#### Custom Base URL (Behind Proxy)

If your service is behind a reverse proxy or accessed via a custom domain, set the `BASE_URL` environment variable to ensure log URLs are generated correctly:

```bash
# Example for Docker
docker run -d \
  --name proxmox-discord-notifier \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e BASE_URL="https://your-domain.com" \
  -p 6068:6068 \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

Or in docker-compose:

```yaml
environment:
  - DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
  - BASE_URL=https://your-domain.com
```

Without `BASE_URL`, log URLs are generated from the incoming request, which may not work correctly behind a proxy.

#### Log Retention

By default, logs are kept for 30 days and then automatically deleted. You can configure this behavior using the `LOG_RETENTION_DAYS` environment variable:

- **Default**: `30` (keeps logs for 30 days)
- **Never delete**: Set to `0` to keep logs forever
- **Custom duration**: Set to any positive number of days

```bash
# Example: Keep logs for 7 days
docker run -d \
  --name proxmox-discord-notifier \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e LOG_RETENTION_DAYS=7 \
  -p 6068:6068 \
  ghcr.io/skulldorom/proxmox-discord-notifier:latest
```

Or in docker-compose:

```yaml
environment:
  - LOG_RETENTION_DAYS=0  # Never delete logs
```

The cleanup task runs automatically every 24 hours starting when the application launches.

### Setup with Environment Variable

If you set the `DISCORD_WEBHOOK` environment variable, you can omit it from the request body:

| UI Field          | Value / Example                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Endpoint Name** | `proxmox-discord-notifier`                                                                                                                                                           |
| **Method**        | `POST`                                                                                                                                                                               |
| **URL**           | `http://<API_SERVER_IP>:6068/api/notify`                                                                                                                                             |
| **Headers**       | `Content-Type: application/json`                                                                                                                                                     |
| **Body**          | <pre lang=json>{<br/> "title" : "{{ title }}",<br/> "message": "{{ escape message }}",<br/> "severity": "{{ severity }}",<br/> "mention_user_id":"{{ secrets.user_id }}"<br/>}</pre> |
| **Secrets**       | `user_id` → your Discord user ID (optional)                                                                                                                                          |
| **Enable**        | ✓                                                                                                                                                                                    |

### Setup with Request Payload (Original Method)

If you prefer to include the webhook in each request or need per-request webhooks:

| UI Field          | Value / Example                                                                                                                                                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Endpoint Name** | `proxmox-discord-notifier`                                                                                                                                                                                                                                                            |
| **Method**        | `POST`                                                                                                                                                                                                                                                                                |
| **URL**           | `http://<API_SERVER_IP>:6068/api/notify`                                                                                                                                                                                                                                              |
| **Headers**       | `Content-Type: application/json`                                                                                                                                                                                                                                                      |
| **Body**          | <pre lang=json>{<br/> "discord_webhook": "https://discord.com/api/webhooks/{{ secrets.id }}/{{ secrets.token }}",<br/> "title" : "{{ title }}",<br/> "message": "{{ escape message }}",<br/> "severity": "{{ severity }}",<br/> "mention_user_id":"{{ secrets.user_id }}"<br/>}</pre> |
| **Secrets**       | `id` → your Discord webhook **ID**<br>`token` → your Discord webhook **token** <br>`user_id` → your Discord user ID (optional)                                                                                                                                                        |
| **Enable**        | ✓                                                                                                                                                                                                                                                                                     |

> **Note**: If both environment variable and request payload contain a webhook URL, the request payload takes precedence.

## Credits

This project is maintained by [Skulldorom](https://github.com/Skulldorom). While this implementation represents a fresh approach to Proxmox-to-Discord notifications, it may build upon concepts and ideas from earlier community projects in the Proxmox ecosystem.

## License

Released under the [MIT License](LICENSE).

Copyright (c) 2025 Jordan Shaw
