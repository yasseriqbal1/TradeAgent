"""
Simplified Workflow Setup Script (No API Dependencies)
Automatically configures n8n workflow with correct paths for current installation
This version doesn't require the FastAPI service to be running
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
    """
    Generate n8n workflow JSON with correct paths
    Uses wrapper scripts for portability
    NO API DEPENDENCIES - All monitoring via log files
    """
    # Escape paths for JSON
    project_root_json = str(project_root).replace('\\', '\\\\')
    
    workflow = {
        "name": "TradeAgent Production (Simplified)",
        "nodes": [
            # Schedule 1: Data Refresh (8 AM)
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "0 8 * * 1-5"}]
                    }
                },
                "name": "Schedule: Data Refresh (8AM)",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 200],
                "id": "schedule-data"
            },
            {
                "parameters": {
                    "command": f"powershell.exe -ExecutionPolicy Bypass -File \"{project_root_json}\\\\run_download.ps1\""
                },
                "name": "Download Stock Data",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [450, 200]
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": discord_webhook,
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "content", "value": "📥 **Data Refresh Complete**\\n\\nTime: {{ $now.toFormat('h:mm a') }} EST\\nStatus: All stock data updated\\n✅ System ready for trading"}
                        ]
                    },
                    "options": {}
                },
                "name": "Discord: Data Ready",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [650, 200]
            },
            # Schedule 2: Start Trading (9:30 AM)
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "30 9 * * 1-5"}]
                    }
                },
                "name": "Schedule: Start Trading (9:30AM)",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 400],
                "id": "schedule-trading"
            },
            {
                "parameters": {
                    "command": f"powershell.exe -ExecutionPolicy Bypass -File \"{project_root_json}\\\\run_trading.ps1\""
                },
                "name": "Start Trading",
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
                            {"name": "content", "value": "🟢 **Live Trading Started**\\n\\nTime: {{ $now.toFormat('h:mm a') }} EST\\nMode: Paper Trading\\nStocks: 25 momentum leaders\\n\\n⏰ Auto-stop: 4:00 PM EST"}
                        ]
                    },
                    "options": {}
                },
                "name": "Discord: Trading Started",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.1,
                "position": [650, 400]
            },
            # Schedule 3: Market Close (4 PM) - Read log only
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "cronExpression", "expression": "0 16 * * 1-5"}]
                    }
                },
                "name": "Schedule: Market Close (4PM)",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1.1,
                "position": [250, 600],
                "id": "schedule-close"
            },
            {
                "parameters": {
                    "command": f"powershell.exe -Command \"Get-Content '{project_root_json}\\\\logs\\\\trades_log_*.txt' | Select-Object -Last 100\""
                },
                "name": "Read Trade Log",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [450, 600]
            },
            {
                "parameters": {
                    "jsCode": "// Parse trade log and generate daily summary\nconst logContent = $input.item.json.stdout || '';\n\n// Extract key metrics from log\nconst equityMatch = logContent.match(/Ending Equity:\\s+\\$([\\d,]+\\.\\d{2})/);\nconst pnlMatch = logContent.match(/Net P\\/L:\\s+\\$([+-]?[\\d,]+\\.\\d{2})/);\nconst returnMatch = logContent.match(/Return:\\s+([+-]?[\\d.]+)%/);\nconst tradesMatch = logContent.match(/TRADES EXECUTED: (\\d+)/);\nconst buysMatch = logContent.match(/Buys: (\\d+)/);\nconst sellsMatch = logContent.match(/Sells: (\\d+)/);\n\nconst endingEquity = equityMatch ? equityMatch[1] : '100,000.00';\nconst netPnl = pnlMatch ? pnlMatch[1] : '+0.00';\nconst returnPct = returnMatch ? returnMatch[1] : '+0.00';\nconst totalTrades = tradesMatch ? tradesMatch[1] : '0';\nconst buys = buysMatch ? buysMatch[1] : '0';\nconst sells = sellsMatch ? sellsMatch[1] : '0';\n\nconst emoji = parseFloat(returnPct) >= 0 ? '🟢' : '🔴';\n\nreturn {\n  summary: `${emoji} **Daily Trading Summary**\\n\\n**Date**: ${new Date().toLocaleDateString('en-US', {timeZone: 'America/New_York'})}\\n**Duration**: 9:30 AM - 4:00 PM EST\\n\\n**Performance**:\\n• Ending Equity: $${endingEquity}\\n• Net P/L: $${netPnl}\\n• Return: ${returnPct}%\\n\\n**Activity**:\\n• Total Trades: ${totalTrades}\\n• Buys: ${buys}\\n• Sells: ${sells}\\n\\n✅ Trading stopped for the day`\n};"
                },
                "name": "Generate Daily Summary",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [650, 600]
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
                "position": [850, 600]
            },
            # Schedule 4: Webhook for real-time trade alerts
            {
                "parameters": {
                    "path": "trade-alerts",
                    "responseMode": "onReceived"
                },
                "name": "Webhook: Trade Alerts",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 800],
                "webhookId": "trade-alerts"
            },
            {
                "parameters": {
                    "jsCode": "// Format trade alert for Discord\nconst trade = $input.item.json;\n\nconst emoji = trade.action === 'BUY' ? '🟢' : '🔴';\nconst action = trade.action;\nconst ticker = trade.ticker;\nconst price = trade.price?.toFixed(2);\nconst shares = trade.shares;\n\nlet message = `${emoji} **${action} ${ticker}**\\n\\n`;\n\nif (action === 'BUY') {\n  message += `Price: $${price}\\nShares: ${shares}\\nCost: $${(price * shares).toFixed(2)}\\nMomentum: ${trade.momentum?.toFixed(4)}`;\n} else {\n  const pnl = trade.pnl?.toFixed(2);\n  const pnlPct = trade.pnl_pct?.toFixed(2);\n  message += `Entry: $${trade.entry_price?.toFixed(2)}\\nExit: $${price}\\nShares: ${shares}\\nP/L: ${pnl >= 0 ? '+' : ''}$${pnl} (${pnlPct}%)\\nReason: ${trade.reason}`;\n}\n\nreturn { message };"
                },
                "name": "Format Trade Alert",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [450, 800]
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
                "position": [650, 800]
            }
        ],
        "connections": {
            "Schedule: Data Refresh (8AM)": {"main": [[{"node": "Download Stock Data", "type": "main", "index": 0}]]},
            "Download Stock Data": {"main": [[{"node": "Discord: Data Ready", "type": "main", "index": 0}]]},
            "Schedule: Start Trading (9:30AM)": {"main": [[{"node": "Start Trading", "type": "main", "index": 0}]]},
            "Start Trading": {"main": [[{"node": "Discord: Trading Started", "type": "main", "index": 0}]]},
            "Schedule: Market Close (4PM)": {"main": [[{"node": "Read Trade Log", "type": "main", "index": 0}]]},
            "Read Trade Log": {"main": [[{"node": "Generate Daily Summary", "type": "main", "index": 0}]]},
            "Generate Daily Summary": {"main": [[{"node": "Discord: Daily Summary", "type": "main", "index": 0}]]},
            "Webhook: Trade Alerts": {"main": [[{"node": "Format Trade Alert", "type": "main", "index": 0}]]},
            "Format Trade Alert": {"main": [[{"node": "Discord: Trade Alert", "type": "main", "index": 0}]]}
        },
        "active": False,
        "settings": {
            "timezone": "America/New_York"
        }
    }
    
    return workflow

def main():
    print("\n" + "=" * 60)
    print("TradeAgent Workflow Setup (Simplified - No API)")
    print("=" * 60)
    print()
    
    # Get paths
    project_root = get_project_root()
    python_path = get_python_path()
    
    print(f"✓ Project Root: {project_root}")
    print(f"✓ Python: {python_path}")
    print()
    
    # Get Discord webhook
    discord_webhook = get_discord_webhook()
    print(f"✓ Discord Webhook: {discord_webhook[:50]}...")
    print()
    
    # Generate workflow
    print("Generating workflow JSON...")
    workflow = generate_workflow(project_root, python_path, discord_webhook)
    
    # Save to file
    output_dir = project_root / "n8n_workflows"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "production_workflow_SIMPLIFIED.json"
    with open(output_file, 'w') as f:
        json.dump(workflow, f, indent=2)
    
    print(f"✓ Workflow saved: {output_file}")
    print()
    print("=" * 60)
    print("Setup Complete! Next Steps:")
    print("=" * 60)
    print()
    print("1. Open n8n (http://localhost:5678)")
    print("2. Click 'Import from File'")
    print(f"3. Select: {output_file}")
    print("4. Click 'Save' to activate workflow")
    print()
    print("Workflow Features (No API Required):")
    print("  • 8:00 AM - Download fresh stock data")
    print("  • 9:30 AM - Start live trading")
    print("  • 4:00 PM - Daily summary (reads trade log)")
    print("  • Real-time - Webhook for trade alerts")
    print()
    print("✅ This version works without FastAPI service running!")
    print()

if __name__ == "__main__":
    main()
