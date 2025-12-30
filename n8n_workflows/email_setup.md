# Email Configuration Guide for TradeAgent

## Overview

TradeAgent sends two types of emails:

1. **Daily Brief (9am EST)**: Full market analysis with top 10 picks
2. **Alert (10am EST)**: Only when significant changes detected

**Recipients:**

- yasser@theasdmom.com
- yasseriqbal@yahoo.com

---

## Option 1: Gmail (Recommended)

### Setup Steps

1. **Enable 2-Factor Authentication**

   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Generate App Password**

   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Click "Generate"
   - Copy the 16-character password

3. **Configure in n8n**

   - In n8n, go to **Credentials** → **Add Credential**
   - Select **SMTP**
   - Enter:
     - **Host**: `smtp.gmail.com`
     - **Port**: `587`
     - **SSL/TLS**: Enable
     - **User**: `your-email@gmail.com`
     - **Password**: [App Password from step 2]

4. **Test Connection**
   - Save credential
   - Open either workflow
   - Click "Test" on Send Email node

---

## Option 2: Outlook/Hotmail

### SMTP Settings

- **Host**: `smtp-mail.outlook.com`
- **Port**: `587`
- **SSL/TLS**: Enable
- **User**: `your-email@outlook.com`
- **Password**: Your Outlook password

### Notes

- Works with personal accounts
- May need to enable "Less secure apps" in settings

---

## Option 3: Yahoo Mail

### SMTP Settings

- **Host**: `smtp.mail.yahoo.com`
- **Port**: `587` or `465` (SSL)
- **SSL/TLS**: Enable
- **User**: `yasseriqbal@yahoo.com`
- **Password**: App Password (generate at account.yahoo.com)

### Generate Yahoo App Password

1. Go to https://login.yahoo.com/account/security
2. Click "Generate app password"
3. Select "Other App" → "n8n"
4. Copy password

---

## Option 4: SendGrid (Free Tier)

### Why SendGrid?

- 100 emails/day free
- No SMTP authentication issues
- Professional email delivery
- API-based (more reliable)

### Setup Steps

1. **Create Account**

   - Go to https://sendgrid.com
   - Sign up for free tier

2. **Get API Key**

   - Dashboard → Settings → API Keys
   - Create API Key → Full Access
   - Copy the key

3. **Verify Sender Email**

   - Settings → Sender Authentication
   - Verify single sender: `tradeagent@yourdomain.com`
   - Or use your personal email

4. **Configure in n8n**
   - Use HTTP Request node instead of Email node
   - POST to: `https://api.sendgrid.com/v3/mail/send`
   - Headers:
     - `Authorization: Bearer YOUR_API_KEY`
     - `Content-Type: application/json`
   - Body:
     ```json
     {
       "personalizations": [
         {
           "to": [
             { "email": "yasser@theasdmom.com" },
             { "email": "yasseriqbal@yahoo.com" }
           ]
         }
       ],
       "from": { "email": "tradeagent@yourdomain.com" },
       "subject": "{{ $json.subject }}",
       "content": [
         {
           "type": "text/html",
           "value": "{{ $json.body }}"
         }
       ]
     }
     ```

---

## Option 5: n8n Cloud Email (Easiest)

### Setup

1. Just enter recipient emails in Send Email node
2. n8n handles all SMTP configuration
3. No credentials needed

### Limitations

- Only works with n8n Cloud (not self-hosted)
- 100 emails/month free

---

## Email Template Customization

### Daily Brief Email Includes:

- 📊 Header with date
- 📈 Key stats (stocks scanned, execution time)
- 🤖 AI-generated analysis
- 📋 Table of top 10 signals
- ⚠️ Risk disclaimer
- Professional HTML styling

### Alert Email Includes:

- ⚠️ Alert header
- 📊 Change statistics
- 🤖 AI analysis of changes
- ❌ Dropped tickers
- ✅ Added tickers
- 📈 Price moves
- 📊 Score changes

---

## Troubleshooting

### "Authentication failed"

- **Gmail**: Use App Password, not regular password
- **Yahoo**: Generate App Password
- **Outlook**: Enable "Less secure apps"

### "Connection timeout"

- Check firewall/antivirus
- Try different port (587 vs 465)
- Verify SMTP host is correct

### "Emails not received"

- Check spam folder
- Verify recipient emails are correct
- Test with single recipient first

### "n8n says 'Email sent' but nothing received"

- Check email service logs
- Verify sender email is valid
- Try different email provider

---

## Testing Email Before Production

### Manual Test

1. Open workflow in n8n
2. Click "Execute Workflow"
3. Check execution log for errors
4. Verify email received

### Test with Fake Data

```javascript
// In "Format Email" node, use test data:
const testData = {
  signals: [{ rank: 1, ticker: "TEST", score: 1.234, price: 100.5 }],
  stats: { tickers_loaded: 100, passed_filters: 25, top_n: 10 },
};
```

---

## Production Best Practices

1. **Use App Passwords**: Never use main account passwords
2. **Monitor Deliverability**: Check spam scores
3. **Set Reply-To**: Add your main email as reply-to
4. **HTML + Plain Text**: Include both formats
5. **Unsubscribe Link**: For compliance (if scaling)
6. **Rate Limiting**: Don't exceed provider limits
7. **Backup Provider**: Have second email service ready

---

## Cost Comparison

| Provider  | Free Tier                | Cost/Month           |
| --------- | ------------------------ | -------------------- |
| Gmail     | Unlimited (personal use) | $0                   |
| Outlook   | Unlimited (personal use) | $0                   |
| Yahoo     | Unlimited (personal use) | $0                   |
| SendGrid  | 100/day                  | $0 (up to 3k emails) |
| n8n Cloud | 100/month                | $0                   |
| Mailgun   | 1,000/month              | $0                   |

**For TradeAgent (2 emails/day):** Any free tier works

---

## Recommended Setup for You

**For immediate testing:**

```
Provider: Gmail
From: your-gmail@gmail.com
To: yasser@theasdmom.com, yasseriqbal@yahoo.com
Auth: App Password
```

**For production (long-term):**

```
Provider: SendGrid
From: tradeagent@theasdmom.com (if you own domain)
To: yasser@theasdmom.com, yasseriqbal@yahoo.com
Auth: API Key
Backup: Gmail SMTP
```

This ensures:

- High deliverability
- No authentication issues
- Professional sender address
- Reliable daily operation
