# TradeAgent (Docker)

This is the lowest-friction way to run TradeAgent on a Windows laptop **without installing Python/Redis/Postgres/Node**.

Client-friendly quick start: see [Documentation/CLIENT_DOCKER_HANDOFF.md](../../Documentation/CLIENT_DOCKER_HANDOFF.md).

## Prereqs

- Docker Desktop (Windows, WSL2 backend)

## Quick start

1. Copy your env:
   - Copy `.env.template` → `.env`
   - Fill in `QUESTRADE_REFRESH_TOKEN`, `DB_PASSWORD`, etc.

2. Add Questrade token file (recommended for Docker):

- Create folder: `secrets/`
- Create file: `secrets/questrade_refresh_token.txt` containing ONLY the refresh token
- Or run: `./update_questrade_token.ps1` and paste the token when prompted

3. Start:

- PowerShell: `./start_docker.ps1`

This runs `docker compose pull` (downloads prebuilt images) and then `docker compose up -d`.

4. Open:

- http://localhost:5000

## Optional: RSS news monitor

Run:

- `docker compose --profile news up -d`

## Optional: n8n

Run:

- `docker compose --profile n8n up -d`

## Stop

- `docker compose down`

## Notes

- Postgres data persists in the `tradeagent_postgres_data` Docker volume.
- First boot initializes DB tables using `schema.sql`.

### Image size / lightweight builds

- The bot image uses `requirements.bot.txt` (a minimal dependency set) to keep downloads smaller and avoid optional research/backtest dependencies.

## Questrade refresh token rotation

Questrade refresh tokens rotate. In this Docker setup, the bot persists the newest token into:

- `secrets/questrade_refresh_token.txt`

If the customer ever needs to manually update it (ex: token revoked / new app token generated), they can run:

- `./update_questrade_token.ps1`

### About the images

- `dashboard` / `bot` are configured to pull prebuilt images from GHCR:
  - `ghcr.io/yasseriqbal1/tradeagent-dashboard:latest`
  - `ghcr.io/yasseriqbal1/tradeagent-bot:latest`
- Even if the GitHub repo is public, GHCR _packages_ can still be private. If the client gets `403 Forbidden` on pull:
  - Preferred: make the GHCR packages public
  - Alternative: client runs `docker login ghcr.io` with credentials that can read packages
- You can still build locally for development with: `docker compose up -d --build`
