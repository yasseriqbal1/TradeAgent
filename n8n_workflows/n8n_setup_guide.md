# n8n Setup Guide for TradeAgent

## Prerequisites

- Node.js installed (v18 or higher)
- FastAPI service running on http://127.0.0.1:8000
- Groq API key configured in .env

## Step 1: Install n8n

```bash
# Install n8n globally via npx (no Docker needed)
npx n8n
```

n8n will start on http://localhost:5678

## Step 2: Initial Setup

1. Open http://localhost:5678 in your browser
2. Create an account (local, no cloud sync)
3. Go to **Settings** → **Environments** and add:
   - `FAKE_GROQ_API_KEY` = `xxxxx`
   - `FASTAPI_URL` = `http://127.0.0.1:8000`
   - `EMAIL_TO` = `yasser@theasdmom.com,yasseriqbal@yahoo.com`

## Step 3: Import Workflows

**Import both workflow files:**

1. Click **Workflows** → **Add Workflow** → **Import from File**
2. Import `premarket_scan_workflow.json` (9am EST scan)
3. Import `validation_scan_workflow.json` (10am EST scan)

## Step 4: Configure Email Node

**For each workflow, configure the Send Email node:**

1. Click on the **Send Email** node
2. Select email service:
   - **Gmail**: Use App Password (not regular password)
   - **Outlook/Yahoo**: Use SMTP settings
   - **SendGrid/Mailgun**: Use API key

**Gmail Setup (Recommended):**

- Email: your-email@gmail.com
- Password: Generate an [App Password](https://myaccount.google.com/apppasswords)
- SMTP: smtp.gmail.com:587

**Or use n8n Cloud Email (easiest):**

- Just enter recipient emails, n8n handles sending

## Step 5: Set Timezone

1. Go to **Settings** → **General**
2. Set **Timezone** to `America/New_York` (EST)
3. Save settings

## Step 6: Activate Workflows

1. Open **Premarket Scan** workflow
2. Click **Active** toggle (top right)
3. Repeat for **Validation Scan** workflow

## Step 7: Test Workflows

**Manual Test (before 9am):**

1. Open **Premarket Scan** workflow
2. Click **Execute Workflow** (bottom)
3. Check execution results
4. Verify email received

**Check Logs:**

- Click **Executions** (left sidebar)
- View success/failure status
- Debug any errors

## Workflow Schedule

- **Premarket Scan**: Every weekday at 9:00 AM EST
- **Validation Scan**: Every weekday at 10:00 AM EST

## Troubleshooting

**n8n won't start:**

```bash
# Kill existing n8n process
taskkill /F /IM node.exe
npx n8n
```

**FastAPI not reachable:**

```bash
# Ensure FastAPI is running
python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000
```

**Email not sending:**

- Check SMTP credentials
- Enable "Less secure app access" (Gmail)
- Use App Password instead of regular password

**Groq API error:**

- Verify API key is correct
- Check Groq API quota/limits
- Test at https://console.groq.com/

## Running Both Services Together

**Terminal 1 - FastAPI:**

```bash
cd "C:\Users\training\Documents\Python Projects\TradeAgent"
.\venv\Scripts\Activate.ps1
python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000
```

**Terminal 2 - n8n:**

```bash
npx n8n
```

Keep both running for automated daily scans.

## Production Deployment

**Keep services running 24/7:**

Option 1: **Windows Task Scheduler**

- Schedule PowerShell scripts to start on boot
- Restart on failure

Option 2: **PM2 (Process Manager)**

```bash
npm install -g pm2
pm2 start "python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000"
pm2 start "npx n8n"
pm2 save
pm2 startup
```

Option 3: **Docker Compose** (advanced)

- Containerize both services
- Auto-restart policies
