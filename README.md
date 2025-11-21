# proxmox2discord

Reliable Proxmox Backup and VM Log Notifications in Discord

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

Discord enforces a 2000‑character limit per message, which can truncate lengthy Proxmox backup logs or VM events and obscure critical details. **Proxmox2Discord** solves this by:

- Capturing full Proxmox output in raw log files.
- Sending concise Discord notifications with a link to the complete log.

Whether you run nightly backups or ad‑hoc snapshots, Proxmox2Discord ensures you never miss important context.

## Features

- Raw Log Storage: Saves complete Proxmox logs in a configurable directory.
- Discord Embeds: Sends rich notifications with title, severity, and log link.
- Optional User Mentions: Include a Discord user ID to automatically @mention a specific user in the alert.
- Log Retention: Manual cleanup available; automatic retention planned. See [Log Management](#log-management) for details.
- Lightweight: Single Python package; minimal dependencies.
- Docker‑Ready: Official Dockerfile for fast deployment.

## Prerequisites

- Docker

## Quickstart

### Using Docker

Run with Docker.

```bash
docker run -d \
  --name proxmox2discord \
  --restart unless-stopped \
  -e TZ=UTC \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -p 6068:6068 \
  -v p2d_logs:/var/logs/p2d \
  ghcr.io/skulldorom/proxmox2discord:latest
```

Optionally you can use docker-compose as well.

```
version: "3.9"

services:
  proxmox2discord:
    container_name: proxmox2discord
    image: ghcr.io/skulldorom/proxmox2discord:latest
    restart: unless-stopped
    volumes:
      - p2d_logs:/var/logs/p2d
    environment:
      - TZ=UTC
      - DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
    ports:
      - "6068:6068"

volumes:
  p2d_logs:
    name: p2d_logs
```

```bash
docker compose up -d
```

### Run Manually

```bash
# Set the Discord webhook (optional if provided in request)
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
proxmox2discord
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
  --name proxmox2discord \
  -e DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN" \
  -e BASE_URL="https://your-domain.com" \
  -p 6068:6068 \
  ghcr.io/skulldorom/proxmox2discord:latest
```

Or in docker-compose:

```yaml
environment:
  - DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
  - BASE_URL=https://your-domain.com
```

Without `BASE_URL`, log URLs are generated from the incoming request, which may not work correctly behind a proxy.

### Setup with Environment Variable

If you set the `DISCORD_WEBHOOK` environment variable, you can omit it from the request body:

| UI Field          | Value / Example                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Endpoint Name** | `proxmox2discord `                                                                                                                                                                   |
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
| **Endpoint Name** | `proxmox2discord `                                                                                                                                                                                                                                                                    |
| **Method**        | `POST`                                                                                                                                                                                                                                                                                |
| **URL**           | `http://<API_SERVER_IP>:6068/api/notify`                                                                                                                                                                                                                                              |
| **Headers**       | `Content-Type: application/json`                                                                                                                                                                                                                                                      |
| **Body**          | <pre lang=json>{<br/> "discord_webhook": "https://discord.com/api/webhooks/{{ secrets.id }}/{{ secrets.token }}",<br/> "title" : "{{ title }}",<br/> "message": "{{ escape message }}",<br/> "severity": "{{ severity }}",<br/> "mention_user_id":"{{ secrets.user_id }}"<br/>}</pre> |
| **Secrets**       | `id` → your Discord webhook **ID**<br>`token` → your Discord webhook **token** <br>`user_id` → your Discord user ID (optional)                                                                                                                                                        |
| **Enable**        | ✓                                                                                                                                                                                                                                                                                     |

> **Note**: If both environment variable and request payload contain a webhook URL, the request payload takes precedence.

## Log Management

### Log Persistence

**Current Behavior**: Logs are stored indefinitely in the configured log directory (`/var/logs/p2d` by default in Docker). There is no automatic cleanup mechanism at this time.

### Manual Log Cleanup

If you need to manage disk space, you can manually clean up old logs:

#### Docker Volume

```bash
# View log files in the Docker volume
docker exec proxmox2discord ls -lh /var/logs/p2d

# Remove logs older than 30 days
docker exec proxmox2discord find /var/logs/p2d -name "*.log" -type f -mtime +30 -delete
```

#### Host System (Manual Installation)

```bash
# Remove logs older than 30 days from the default location
# Default: ./logs (relative to where the application is run)
find ./logs -name "*.log" -type f -mtime +30 -delete
```

You can also set up a cron job to automatically clean up old logs:

```bash
# Add to crontab (runs daily at 2 AM)
# Replace ./logs with your actual log directory path
0 2 * * * find /path/to/your/logs -name "*.log" -type f -mtime +30 -delete
```

### Future Plans

Automatic log retention with configurable cleanup after N days is planned for a future release. This will allow you to set a `LOG_RETENTION_DAYS` environment variable to automatically remove logs older than the specified number of days.

## License

Released under the [MIT License](LICENSE).
