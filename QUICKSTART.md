# Quick Start Guide - TradeAgent

## 🚀 Complete Setup in 15 Minutes

### Step 1: Start FastAPI (Terminal 1)

```bash
cd "C:\Users\training\Documents\Python Projects\TradeAgent"
.\venv\Scripts\Activate.ps1
python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000
```

**Verify it's running:**

```bash
curl http://127.0.0.1:8000/health
```

Expected response: `{"status":"healthy",...}`

---

### Step 2: Install and Start n8n (Terminal 2)

```bash
npx n8n
```

n8n will start on http://localhost:5678

**First time setup:**

1. Create local account (no cloud sync)
2. Skip tutorials

---

### Step 3: Configure Environment Variables

In n8n:

1. Click **Settings** (gear icon)
2. Go to **Environments**
3. Add these variables:

```
FAKE_GROQ_API_KEY = xxxxxxxx
FASTAPI_URL = http://127.0.0.1:8000
EMAIL_TO = yasser@theasdmom.com,yasseriqbal@yahoo.com
```

4. **Set Timezone**: Settings → General → Timezone = `America/New_York`

---

### Step 4: Configure Email Credentials

**Option A: Gmail (Recommended)**

1. Generate App Password:

   - https://myaccount.google.com/apppasswords
   - App: Mail, Device: Windows Computer
   - Copy 16-character password

2. In n8n:
   - **Credentials** → **Add Credential** → **SMTP**
   - Host: `smtp.gmail.com`
   - Port: `587`
   - SSL/TLS: ✅ Enable
   - User: `your-email@gmail.com`
   - Password: [App Password]
   - Save as "Gmail SMTP"

**Option B: Yahoo**

- Host: `smtp.mail.yahoo.com`
- Port: `587`
- User: `yasseriqbal@yahoo.com`
- Password: [Yahoo App Password from account.yahoo.com]

---

### Step 5: Import Workflows

1. Download workflow files from `n8n_workflows/` folder:

   - `premarket_scan_workflow.json`
   - `validation_scan_workflow.json`

2. In n8n:
   - Click **Workflows** → **Add Workflow**
   - Click **⋮** (menu) → **Import from File**
   - Select `premarket_scan_workflow.json`
   - Repeat for `validation_scan_workflow.json`

---

### Step 6: Update Email Nodes

**For EACH workflow:**

1. Open workflow
2. Click on **Send Email** node
3. Select your SMTP credential (created in Step 4)
4. Verify:
   - From Email: `your-email@gmail.com`
   - To Email: `yasser@theasdmom.com,yasseriqbal@yahoo.com`
5. Click **Save**

---

### Step 7: Test Premarket Workflow

1. Open **Premarket Scan** workflow
2. Click **Execute Workflow** (bottom button)
3. Wait 30-60 seconds
4. Check execution log:
   - ✅ All nodes green = success
   - ❌ Red node = error (click to see details)
5. **Check your email** for daily brief

**Expected result:**

- Email with "📊 TradeAgent Daily Brief"
- AI analysis of top 10 stocks
- HTML table with signals
- Should take ~45-60 seconds

---

### Step 8: Test Validation Workflow

1. Open **Validation Scan** workflow
2. Click **Execute Workflow**
3. Wait 30-60 seconds
4. Check execution log

**Expected result:**

- If changes detected: Email alert sent
- If no changes: "No Changes - Skip Email" node executed
- No email sent (normal if testing immediately after premarket)

---

### Step 9: Activate Workflows

**For EACH workflow:**

1. Open workflow
2. Toggle **Active** switch (top right)
3. Verify schedule shows as "Active"

**Schedules:**

- Premarket: Mon-Fri 9:00 AM EST
- Validation: Mon-Fri 10:00 AM EST

---

### Step 10: Monitor First Live Run

**Tomorrow morning:**

1. Check n8n **Executions** tab at 9:05 AM EST
2. Verify premarket scan succeeded
3. Check email for daily brief
4. Check n8n **Executions** tab at 10:05 AM EST
5. Verify validation scan succeeded

---

## 🔧 Troubleshooting

### FastAPI won't start

```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /F /PID [PID_NUMBER]
```

### n8n can't reach FastAPI

- Verify FastAPI is running: `curl http://127.0.0.1:8000/health`
- Check firewall isn't blocking port 8000

### Email not sending

- Verify SMTP credential is correct
- Check spam folder
- Test with just one recipient
- Check n8n execution log for error details

### Groq API error

- Verify API key is correct in environment variables
- Check quota at https://console.groq.com/
- Test API key: `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer YOUR_KEY"`

### No email at scheduled time

- Verify workflows are **Active** (toggle switch on)
- Check timezone is set to `America/New_York`
- Check n8n **Executions** tab for errors
- Verify both FastAPI and n8n are running

---

## 📊 What to Expect

### Daily Brief Email (9am EST)

- Subject: "📊 TradeAgent Daily Brief - Dec 28"
- Content:
  - Market summary (AI-generated)
  - Top 10 stocks with scores
  - Detailed factor breakdown
  - HTML formatted, professional styling
- Delivery time: 9:01-9:02 AM EST

### Validation Alert (10am EST)

- Only sent if changes detected:
  - Tickers dropped from top 10
  - New tickers added
  - Significant price moves (>2%)
  - Score changes (>0.5)
- If no changes: No email (silent)
- Delivery time: 10:01-10:02 AM EST

---

## 🎯 Success Checklist

- ✅ FastAPI health endpoint returns `{"status":"healthy"}`
- ✅ n8n running on http://localhost:5678
- ✅ Environment variables configured
- ✅ Email credentials configured and tested
- ✅ Both workflows imported
- ✅ Both workflows activated
- ✅ Manual test successful (email received)
- ✅ Database contains scan_runs records

**Verify database:**

```bash
# In PowerShell with activated venv
python -c "from quant_agent.database import db; print(db.get_scan_history(limit=5))"
```

---

## 🔄 Daily Operation

**Just keep both services running:**

- FastAPI terminal (Terminal 1)
- n8n terminal (Terminal 2)

**Both must be running for scheduled scans.**

**To stop:**

- Press `Ctrl+C` in each terminal

**To restart:**

- Run Step 1 and Step 2 again

---

## 📈 Next Steps

After everything works:

1. **Adjust Factor Weights** (optional):

   - Edit `quant_agent/config.py`
   - Modify `FACTOR_WEIGHTS` dict
   - Restart FastAPI

2. **Change Stock Universe**:

   - Edit `quant_agent/config.py`
   - Modify `STOCK_UNIVERSE` list
   - Add/remove tickers

3. **Tune AI Prompts**:

   - Edit workflow JSON files
   - Modify Groq API call parameters
   - Adjust temperature, max_tokens

4. **Add More Scans**:

   - Duplicate validation workflow
   - Change schedule (e.g., 2pm, 3pm)
   - Adjust notification logic

5. **Production Deployment**:
   - Use PM2 for process management
   - Set up Windows Task Scheduler
   - Configure auto-restart on failure

---

## 📞 Support

**Check logs:**

- FastAPI: Terminal output
- n8n: Executions tab
- Database: Query scan_runs table

**Common issues:**

- See full troubleshooting in `n8n_setup_guide.md`
- Email setup: `email_setup.md`
- Groq prompts: `groq_prompts.md`

---

**You're all set! 🎉**

Test manually now, then wait for tomorrow's 9am automatic run.
