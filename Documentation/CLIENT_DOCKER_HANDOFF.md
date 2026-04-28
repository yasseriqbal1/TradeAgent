# TradeAgent — Client Quick Start (Docker)

This guide is written for a non-technical user. Follow it step-by-step.

## What you need (one-time)

1. Install **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop/
   - During install, allow **WSL2** when asked
   - After install, open Docker Desktop once and wait until it says **“Docker Desktop is running”**

2. Get the TradeAgent folder from us
   - You will receive a folder (or ZIP) containing this project.
   - If it’s a ZIP: right-click → **Extract All…**

## Start TradeAgent (normal daily use)

1. Open the TradeAgent folder
2. Double-click:

   `START_TRADEAGENT.bat`

If you prefer the terminal method instead:

- Right-click inside the folder → **Open in Terminal** (or open PowerShell and `cd` into the folder)
- Run: `powershell -ExecutionPolicy Bypass -File .\start_docker.ps1`

4. Open the dashboard in your browser:
   - http://localhost:5000

Note: the first start can take **1–2 minutes**. If you briefly see “page not reachable”, wait a bit and try again.

If you want a simple “is it running?” check, double-click:

`STATUS_TRADEAGENT.bat`

## Stop TradeAgent

Easiest:

- Double-click: `STOP_TRADEAGENT.bat`

Or from a terminal (inside the TradeAgent folder), run ONE of these:

- Stop everything (keeps data):
  - `docker compose stop`

- Fully shut down containers (still keeps database data):
  - `docker compose down`

## Questrade token (weekly / when requested)

Most of the time you do **not** need to do anything. The system automatically rotates and saves the newest token.

Only do this if you are asked to (or if the bot shows an authentication error).

1. Easiest: double-click `UPDATE_TOKEN.bat`

Or from a terminal, run: `powershell -ExecutionPolicy Bypass -File .\update_questrade_token.ps1`

2. When prompted, paste the **Questrade refresh token**
   - You can paste either:
     - the refresh token value itself, OR
     - the full URL you get from Questrade (the script will extract `refresh_token=...` automatically)

3. After updating, check bot logs:
   - `docker compose logs -f bot`

## Quick checks (if you want to confirm it’s running)

- Show running services:
  - `docker compose ps`

Expected:

- `redis`, `postgres`, `dashboard`, `bot` should be **Up**

## Troubleshooting

### “Docker Desktop is not running” / commands fail

- Open Docker Desktop from the Start Menu
- Wait until it shows **Running**, then try again

### Dashboard doesn’t open (http://localhost:5000)

1. Check if the dashboard container is running:
   - `docker compose ps`
2. View dashboard logs:
   - `docker compose logs --tail 200 dashboard`
3. If port 5000 is already used by something else, tell us and we will change it.

### Bot looks “stuck” or not trading

- Check bot logs:
  - `docker compose logs --tail 200 bot`
- Common causes:
  - Outside the trading window (it intentionally waits)
  - Questrade token needs updating (run the token step above)

### “403 Forbidden” during startup

This usually means Docker can’t download the prebuilt images.

Run:

- `docker login ghcr.io`

Then start again:

- `powershell -ExecutionPolicy Bypass -File .\start_docker.ps1`

If you don’t have credentials, send us the exact error message.

### Completely reset everything (last resort)

Warning: this wipes the local database used by TradeAgent.

- `docker compose down -v`
- Then start again:
  - `powershell -ExecutionPolicy Bypass -File .\start_docker.ps1`

## Important notes

- If the laptop sleeps/hibernates, trading will stop because the bot stops running.
- Keep Docker Desktop running while using TradeAgent.
