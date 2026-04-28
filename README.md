# VA_notification

Simple Frigate → Telegram notifier for `person` detections.

## What it does

- polls Frigate events
- filters for `person` events on a chosen camera
- sends a Telegram message with a snapshot
- deduplicates by Frigate `event_id`
- optionally adds an acknowledgement link

## Files

- `notifier.py` — main polling notifier
- `ack_event.py` — mark a specific event as acknowledged
- `ack_latest.py` — acknowledge the most recent event

## Required environment variables

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FRIGATE_URL` (default: `http://host.docker.internal:5000`)
- `CAMERA` (default: `front_camera`)

## Optional environment variables

- `POLL_SECONDS`
- `STATE_FILE`
- `SENT_FILE`
- `ACK_FILE`
- `MESSAGE_PREFIX`
- `BOT_USERNAME`
- `ACK_BASE_URL`

## Run with Docker

```bash
docker run -d \
  --name frigate-telegram-notifier \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  -e TELEGRAM_BOT_TOKEN=... \
  -e TELEGRAM_CHAT_ID=... \
  -e FRIGATE_URL=http://host.docker.internal:5000 \
  -e CAMERA=front_camera \
  -v $(pwd):/app \
  -w /app \
  python:3.11-slim python notifier.py
```

## CI/CD + DevSecOps

This repo includes a GitHub Actions workflow at `.github/workflows/ci-cd-devsecops.yml`.

It runs:
- Python syntax checks
- `ruff` linting
- Snyk code security scanning

### Required GitHub secret

Add this repository secret in GitHub before expecting the Snyk stage to run:

- `SNYK_TOKEN`

Without `SNYK_TOKEN`, the quality job still runs, but the Snyk security job is skipped.
