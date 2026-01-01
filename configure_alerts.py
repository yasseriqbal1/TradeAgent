"""
Alert Configuration Helper
Helps set up email/Discord/Slack alerts for the trading system.
"""
import os
from dotenv import load_dotenv
from quant_agent.config_loader import ConfigLoader

# Load environment variables
load_dotenv()

def configure_email():
    """Guide through email configuration."""
    print("\n" + "=" * 60)
    print("Email Alert Configuration")
    print("=" * 60)
    
    print("\n📧 Email Options:")
    print("  1. Gmail (recommended)")
    print("  2. Yahoo Mail")
    print("  3. Outlook/Hotmail")
    print("  4. Skip email alerts")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '4':
        return None
    
    # Gmail settings
    if choice == '1':
        smtp_host = 'smtp.gmail.com'
        smtp_port = 587
        print("\n✅ Gmail selected")
        print("\nTo use Gmail:")
        print("  1. Enable 2-Factor Authentication")
        print("  2. Generate App Password at: https://myaccount.google.com/apppasswords")
        print("  3. Use the 16-character app password below")
    # Yahoo settings
    elif choice == '2':
        smtp_host = 'smtp.mail.yahoo.com'
        smtp_port = 587
        print("\n✅ Yahoo selected")
        print("\nTo use Yahoo:")
        print("  1. Generate App Password at: https://login.yahoo.com/account/security")
        print("  2. Use the app password below")
    # Outlook settings
    elif choice == '3':
        smtp_host = 'smtp-mail.outlook.com'
        smtp_port = 587
        print("\n✅ Outlook selected")
    else:
        print("\n❌ Invalid choice")
        return None
    
    print("\n📝 Enter your email settings:")
    smtp_user = input("  Email address: ").strip()
    smtp_password = input("  Password (or app password): ").strip()
    
    # Recipients
    recipients_input = input("  Send alerts to (comma-separated): ").strip()
    email_to = [email.strip() for email in recipients_input.split(',') if email.strip()]
    
    if not email_to:
        email_to = [smtp_user]  # Default to sending to self
    
    return {
        'email_enabled': True,
        'smtp_host': smtp_host,
        'smtp_port': smtp_port,
        'smtp_user': smtp_user,
        'smtp_password': smtp_password,
        'email_to': email_to,
        'min_level_email': 'info'
    }

def configure_discord():
    """Guide through Discord configuration."""
    print("\n" + "=" * 60)
    print("Discord Alert Configuration")
    print("=" * 60)
    
    print("\n📱 Discord Webhook Setup:")
    print("  1. Open your Discord server")
    print("  2. Go to Server Settings → Integrations → Webhooks")
    print("  3. Create New Webhook")
    print("  4. Copy the webhook URL")
    
    enable = input("\nEnable Discord alerts? (y/n): ").strip().lower()
    
    if enable != 'y':
        return None
    
    webhook_url = input("Discord webhook URL: ").strip()
    
    if not webhook_url:
        return None
    
    return {
        'discord_enabled': True,
        'discord_webhook_url': webhook_url,
        'min_level_discord': 'info'
    }

def configure_slack():
    """Guide through Slack configuration."""
    print("\n" + "=" * 60)
    print("Slack Alert Configuration")
    print("=" * 60)
    
    print("\n💬 Slack Webhook Setup:")
    print("  1. Go to: https://api.slack.com/messaging/webhooks")
    print("  2. Create a new Slack app")
    print("  3. Enable Incoming Webhooks")
    print("  4. Add webhook to workspace")
    print("  5. Copy the webhook URL")
    
    enable = input("\nEnable Slack alerts? (y/n): ").strip().lower()
    
    if enable != 'y':
        return None
    
    webhook_url = input("Slack webhook URL: ").strip()
    
    if not webhook_url:
        return None
    
    return {
        'slack_enabled': True,
        'slack_webhook_url': webhook_url,
        'min_level_slack': 'info'
    }

def configure_sms():
    """Guide through SMS configuration."""
    print("\n" + "=" * 60)
    print("SMS Alert Configuration (Twilio)")
    print("=" * 60)
    
    print("\n📲 SMS Setup:")
    print("  Note: SMS requires Twilio account")
    print("  Free tier: 15.50 credits")
    print("  Cost: ~$0.0075 per SMS")
    
    enable = input("\nEnable SMS alerts? (y/n): ").strip().lower()
    
    if enable != 'y':
        return None
    
    print("\n📝 Enter Twilio credentials:")
    account_sid = input("  Account SID: ").strip()
    auth_token = input("  Auth Token: ").strip()
    from_number = input("  From number (e.g., +1234567890): ").strip()
    to_numbers_input = input("  To numbers (comma-separated): ").strip()
    
    sms_to = [num.strip() for num in to_numbers_input.split(',') if num.strip()]
    
    if not all([account_sid, auth_token, from_number, sms_to]):
        print("❌ Missing required fields")
        return None
    
    return {
        'sms_enabled': True,
        'twilio_account_sid': account_sid,
        'twilio_auth_token': auth_token,
        'twilio_from_number': from_number,
        'sms_to': sms_to,
        'min_level_sms': 'critical'
    }

def main():
    """Interactive alert configuration."""
    print("=" * 60)
    print("TradeAgent Alert Configuration")
    print("=" * 60)
    
    print("\n📌 This wizard will help you set up trading alerts.")
    print("   You can enable multiple alert channels.")
    
    # Load current config
    config = ConfigLoader('config/live_trading.yaml')
    
    # Configure each channel
    email_config = configure_email()
    discord_config = configure_discord()
    slack_config = configure_slack()
    sms_config = configure_sms()
    
    # Update config
    has_alerts = False
    
    if email_config:
        for key, value in email_config.items():
            config.update(f'alerts.{key}', value)
        has_alerts = True
        print("\n✅ Email alerts configured")
    
    if discord_config:
        for key, value in discord_config.items():
            config.update(f'alerts.{key}', value)
        has_alerts = True
        print("✅ Discord alerts configured")
    
    if slack_config:
        for key, value in slack_config.items():
            config.update(f'alerts.{key}', value)
        has_alerts = True
        print("✅ Slack alerts configured")
    
    if sms_config:
        for key, value in sms_config.items():
            config.update(f'alerts.{key}', value)
        has_alerts = True
        print("✅ SMS alerts configured")
    
    if not has_alerts:
        print("\n⚠️  No alerts configured. System will run without notifications.")
        return
    
    # Save config
    config.save()
    
    print("\n" + "=" * 60)
    print("Configuration Saved!")
    print("=" * 60)
    
    print("\n📋 Summary:")
    if email_config:
        print(f"  ✉️  Email: {email_config['smtp_user']} → {', '.join(email_config['email_to'])}")
    if discord_config:
        print("  📱 Discord: Enabled")
    if slack_config:
        print("  💬 Slack: Enabled")
    if sms_config:
        print(f"  📲 SMS: {', '.join(sms_config['sms_to'])}")
    
    print("\n📌 Next Steps:")
    print("  1. Test alerts: python test_alerts.py")
    print("  2. Run integration test: python test_integration.py")
    print("  3. Start paper trading!")
    
    # Test connection
    print("\n" + "=" * 60)
    test = input("\nWould you like to send a test alert now? (y/n): ").strip().lower()
    
    if test == 'y':
        from quant_agent.alerts import AlertSystem, AlertConfig, AlertType, AlertLevel
        
        # Create alert config from saved settings
        alert_settings = config.get('alerts')
        alert_config = AlertConfig(**alert_settings)
        
        # Initialize alert system
        alerts = AlertSystem(alert_config)
        
        print("\n📤 Sending test alert...")
        
        try:
            alerts.send_alert(
                alert_type=AlertType.SYSTEM_ERROR,
                level=AlertLevel.INFO,
                message='TradeAgent Alert System Test - Configuration Successful',
                data={
                    'status': 'Configuration successful',
                    'channels_enabled': [
                        'email' if email_config else None,
                        'discord' if discord_config else None,
                        'slack' if slack_config else None,
                        'sms' if sms_config else None
                    ]
                }
            )
            
            print("✅ Test alert sent!")
            print("   Check your Discord/Slack/Email/SMS")
        except Exception as e:
            print(f"⚠️  Alert send failed: {e}")
            print("   Alert system is configured but test failed")
            print("   Alerts will still work during trading")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Configuration cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
