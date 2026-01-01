"""
Workflow Setup Script
Automatically configures n8n workflow with correct paths for current installation
Run this after installing on a new system
"""

import os
import sys
import json
from pathlib import Path

def get_project_root():
    """Auto-detect project root (where this script is located)"""
    return Path(__file__).parent.resolve()

def get_python_path():
    """Get path to venv Python executable"""
    project_root = get_project_root()
    python_exe = project_root / "venv" / "Scripts" / "python.exe"
    
    if not python_exe.exists():
        print(f"⚠️  WARNING: Python venv not found at {python_exe}")
        print("Please create virtual environment first:")
        print("  python -m venv venv")
        print("  .\\venv\\Scripts\\Activate.ps1")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    return str(python_exe)

def get_discord_webhook():
    """Get Discord webhook URL from user or .env"""
    # Try to read from .env first
    env_file = get_project_root() / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('DISCORD_WEBHOOK_URL='):
                    url = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if url and url != "YOUR_DISCORD_WEBHOOK_URL_HERE":
                        return url
    
    # Ask user for webhook URL
    print("\n" + "=" * 60)
    print("Discord Webhook Configuration")
    print("=" * 60)
    print()
    print("Please enter your Discord webhook URL.")
    print("You can find this in Discord:")
    print("  1. Server Settings > Integrations > Webhooks")
    print("  2. Create new webhook or copy existing one")
    print()
    
    webhook_url = input("Discord Webhook URL: ").strip()
    
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        print("⚠️  Invalid Discord webhook URL!")
        print("Should start with: https://discord.com/api/webhooks/")
        sys.exit(1)
    
    return webhook_url

def generate_workflow(project_root, python_path, discord_webhook):
    """Generate workflow JSON with correct paths - using wrapper scripts for portability"""
    
    # Convert Windows paths to JSON-safe format (escape backslashes)
    project_root_json = str(project_root).replace('\\', '\\\\')
    
    workflow = {
        "name": "TradeAgent - Full Production Workflow (Enhanced)",
        "nodes": [
            # Schedule 1: 8:00 AM Data Refresh
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "0 8 * * 1-5"}]
                    }
                },
                "name": "Schedule: 8:00 AM - Data Refresh",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 200],
                "id": "schedule-data-refresh"
            },
            {
                "parameters": {
                    "command": f"powershell.exe -ExecutionPolicy Bypass -File \"{project_root_json}\\\\run_download.ps1\""
                },
                "name": "Download Latest Data (Stooq)",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [450, 200]
            },
            # Schedule 2: 9:30 AM Start Trading
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "30 9 * * 1-5"}]
                    }
                },
                "name": "Schedule: 9:30 AM - Start Trading",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 400],
                "id": "schedule-start-trading"
            },
            {
                "parameters": {
                    "command": f"powershell.exe -ExecutionPolicy Bypass -File \"{project_root_json}\\\\run_trading.ps1\""
                },
                "name": "Start Live Trading",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [450, 400]
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": discord_webhook,
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "content", "value": "🟢 **Live Trading Started**\\n\\nTime: {{ $now.toFormat('h:mm a') }}\\nMarket: OPEN\\nCapital: $100,000\\nPositions: 0/3\\nStatus: Monitoring 25 stocks"}
                        ]
                    },
                    "options": {}
                },
                "name": "Discord: Trading Started",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [650, 400]
            },

            # Schedule 4: 4:00 PM Market Close
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "0 16 * * 1-5"}]
                    }
                },
                "name": "Schedule: 4:00 PM - Market Close",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 800],
                "id": "schedule-close"
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": "http://127.0.0.1:8000/trading/stop",
                    "options": {"timeout": 5000}
                },
                "name": "Stop Trading (API)",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [450, 800]
            },
            {
                "parameters": {
                    "command": f"Get-Content '{project_root_json}\\\\trades_log_*.txt' | Select-Object -Last 100"
                },
                "name": "Read Trade Log",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [650, 800]
            },
            {
                "parameters": {
                    "jsCode": "// Parse trade log and generate daily summary\nconst logContent = $input.item.json.stdout;\n\n// Extract key metrics from log\nconst equityMatch = logContent.match(/Ending Equity:\\s+\\$([\\d,]+\\.\\d{2})/);\nconst pnlMatch = logContent.match(/Net P\\/L:\\s+\\$([+-]?[\\d,]+\\.\\d{2})/);\nconst returnMatch = logContent.match(/Return:\\s+([+-]?[\\d.]+)%/);\nconst tradesMatch = logContent.match(/TRADES EXECUTED: (\\d+)/);\nconst buysMatch = logContent.match(/Buys: (\\d+)/);\nconst sellsMatch = logContent.match(/Sells: (\\d+)/);\n\nconst endingEquity = equityMatch ? equityMatch[1] : '100,000.00';\nconst netPnl = pnlMatch ? pnlMatch[1] : '+0.00';\nconst returnPct = returnMatch ? returnMatch[1] : '+0.00';\nconst totalTrades = tradesMatch ? tradesMatch[1] : '0';\nconst buys = buysMatch ? buysMatch[1] : '0';\nconst sells = sellsMatch ? sellsMatch[1] : '0';\n\nconst emoji = parseFloat(returnPct) >= 0 ? '🟢' : '🔴';\n\nreturn {\n  summary: `${emoji} **Daily Trading Summary**\\n\\n**Date**: ${new Date().toLocaleDateString('en-US', {timeZone: 'America/New_York'})}\\n**Duration**: 9:30 AM - 4:00 PM EST\\n\\n**Performance**:\\n• Ending Equity: $${endingEquity}\\n• Net P/L: $${netPnl}\\n• Return: ${returnPct}%\\n\\n**Activity**:\\n• Total Trades: ${totalTrades}\\n• Buys: ${buys}\\n• Sells: ${sells}\\n\\n✅ Trading stopped for the day`\n};"
                },
                "name": "Generate Daily Summary",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [850, 800]
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": discord_webhook,
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "content", "value": "={{ $json.summary }}"}
                        ]
                    },
                    "options": {}
                },
                "name": "Discord: Daily Summary",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [1050, 800]
            },
            # Schedule 5: Webhook
            {
                "parameters": {
                    "path": "trade-alerts",
                    "responseMode": "onReceived"
                },
                "name": "Webhook: Trade Alerts",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 1000],
                "webhookId": "trade-alerts"
            },
            {
                "parameters": {
                    "jsCode": "// Format trade alert for Discord\nconst trade = $input.item.json;\n\nconst emoji = trade.action === 'BUY' ? '🟢' : '🔴';\nconst action = trade.action;\nconst ticker = trade.ticker;\nconst price = trade.price?.toFixed(2);\nconst shares = trade.shares;\n\nlet message = `${emoji} **${action} ${ticker}**\\n\\n`;\n\nif (action === 'BUY') {\n  message += `Price: $${price}\\nShares: ${shares}\\nCost: $${(price * shares).toFixed(2)}\\nMomentum: ${trade.momentum?.toFixed(4)}`;\n} else {\n  const pnl = trade.pnl?.toFixed(2);\n  const pnlPct = trade.pnl_pct?.toFixed(2);\n  message += `Entry: $${trade.entry_price?.toFixed(2)}\\nExit: $${price}\\nShares: ${shares}\\nP/L: ${pnl >= 0 ? '+' : ''}$${pnl} (${pnlPct}%)\\nReason: ${trade.reason}`;\n}\n\nreturn { message };"
                },
                "name": "Format Trade Alert",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [450, 1000]
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": discord_webhook,
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "content", "value": "={{ $json.message }}"}
                        ]
                    },
                    "options": {}
                },
                "name": "Discord: Trade Alert",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [650, 1000]
            }
        ],
        "connections": {
            "Schedule: 8:00 AM - Data Refresh": {
                "main": [[{"node": "Download Latest Data (Stooq)", "type": "main", "index": 0}]]
            },
            "Schedule: 9:30 AM - Start Trading": {
                "main": [[{"node": "Start Live Trading", "type": "main", "index": 0}]]
            },
            "Start Live Trading": {
                "main": [[{"node": "Discord: Trading Started", "type": "main", "index": 0}]]
            },
            "Schedule: Hourly Checks (10AM-3PM)": {
                "main": [[{"node": "Get Current Status (API)", "type": "main", "index": 0}]]
            },
            "Get Current Status (API)": {
                "main": [[{"node": "Format Status Message", "type": "main", "index": 0}]]
            },
            "Format Status Message": {
                "main": [[{"node": "Discord: Hourly Update", "type": "main", "index": 0}]]
            },
            "Schedule: 4:00 PM - Market Close": {
                "main": [[{"node": "Stop Trading (API)", "type": "main", "index": 0}]]
            },
            "Stop Trading (API)": {
                "main": [[{"node": "Read Trade Log", "type": "main", "index": 0}]]
            },
            "Read Trade Log": {
                "main": [[{"node": "Generate Daily Summary", "type": "main", "index": 0}]]
            },
            "Generate Daily Summary": {
                "main": [[{"node": "Discord: Daily Summary", "type": "main", "index": 0}]]
            },
            "Webhook: Trade Alerts": {
                "main": [[{"node": "Format Trade Alert", "type": "main", "index": 0}]]
            },
            "Format Trade Alert": {
                "main": [[{"node": "Discord: Trade Alert", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"},
        "active": False,
        "tags": []
    }
    
    return workflow

def main():
    print()
    print("=" * 60)
    print("TradeAgent - Workflow Setup")
    print("=" * 60)
    print()
    
    # Detect paths
    project_root = get_project_root()
    python_path = get_python_path()
    
    print(f"✅ Project Root: {project_root}")
    print(f"✅ Python Path: {python_path}")
    print()
    
    # Get Discord webhook
    discord_webhook = get_discord_webhook()
    print(f"✅ Discord Webhook: {discord_webhook[:50]}...")
    print()
    
    # Generate workflow
    print("Generating workflow with detected paths...")
    workflow = generate_workflow(project_root, python_path, discord_webhook)
    
    # Save to file
    output_file = project_root / "n8n_workflows" / "production_workflow_READY.json"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Workflow saved to: {output_file}")
    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Open n8n in your browser (usually http://localhost:5678)")
    print("  2. Click Import from File")
    print(f"  3. Select: {output_file.name}")
    print("  4. Activate the workflow")
    print()
    print("The workflow will run automatically:")
    print("  • 8:00 AM - Download fresh data")
    print("  • 9:30 AM - Start live trading")
    print("  • 10 AM-3 PM - Hourly position updates")
    print("  • 4:00 PM - Daily summary")
    print()

if __name__ == "__main__":
    main()
