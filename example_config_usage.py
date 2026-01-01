"""
Example: Initialize Trading System from Config
Shows how to use config file to set up all components
"""

import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from quant_agent.config_loader import ConfigLoader
from quant_agent.risk_monitor import RiskLimits
from quant_agent.alerts import AlertConfig, AlertLevel


def demo_config_usage():
    """Demonstrate config-based initialization"""
    print("\n" + "=" * 60)
    print("Config-Based System Initialization Demo")
    print("=" * 60)
    
    # Load config
    print("\n📌 Loading configuration...")
    config = ConfigLoader()
    print("✅ Config loaded")
    
    # Trading settings
    print("\n📊 Trading Configuration:")
    trading = config.get_trading_config()
    print(f"  Mode: {trading['mode']}")
    print(f"  Capital: ${trading['initial_capital']:,.2f}")
    print(f"  Max Positions: {trading['max_positions']}")
    print(f"  Commission: ${trading['commission_per_trade']}")
    
    # Risk settings - create RiskLimits from config
    print("\n⚠️ Risk Configuration:")
    risk_config = config.get_risk_config()
    
    risk_limits = RiskLimits(
        max_positions=trading['max_positions'],
        max_position_pct=risk_config['max_position_pct'],
        max_daily_loss_pct=risk_config['max_daily_loss_pct'],
        max_sector_exposure_pct=risk_config['max_sector_exposure_pct'],
        max_correlation=risk_config['max_correlation'],
        min_buying_power_pct=risk_config['min_buying_power_pct']
    )
    
    print(f"  Max Position: {risk_limits.max_position_pct}%")
    print(f"  Daily Loss Limit: {risk_limits.max_daily_loss_pct}%")
    print(f"  Min Buying Power: {risk_limits.min_buying_power_pct}%")
    print(f"✅ RiskLimits created from config")
    
    # Alert settings - create AlertConfig from config
    print("\n🔔 Alert Configuration:")
    alerts_config = config.get_alerts_config()
    
    # Map string alert levels to AlertLevel enum
    level_map = {
        'info': AlertLevel.INFO,
        'warning': AlertLevel.WARNING,
        'critical': AlertLevel.CRITICAL
    }
    
    alert_config = AlertConfig(
        email_enabled=alerts_config['email_enabled'],
        smtp_host=alerts_config['smtp_host'],
        smtp_port=alerts_config['smtp_port'],
        smtp_user=alerts_config['smtp_user'],
        smtp_password=alerts_config['smtp_password'],
        email_to=alerts_config['email_to'],
        discord_enabled=alerts_config['discord_enabled'],
        discord_webhook_url=alerts_config['discord_webhook_url'],
        slack_enabled=alerts_config['slack_enabled'],
        slack_webhook_url=alerts_config['slack_webhook_url'],
        sms_enabled=alerts_config['sms_enabled'],
        twilio_account_sid=alerts_config['twilio_account_sid'],
        twilio_auth_token=alerts_config['twilio_auth_token'],
        twilio_from_number=alerts_config['twilio_from_number'],
        sms_to=alerts_config['sms_to'],
        min_level_email=level_map[alerts_config['min_level_email']],
        min_level_sms=level_map[alerts_config['min_level_sms']],
        min_level_discord=level_map[alerts_config['min_level_discord']],
        min_level_slack=level_map[alerts_config['min_level_slack']],
        rate_limit_per_hour=alerts_config['rate_limit_per_hour']
    )
    
    print(f"  Email: {alert_config.email_enabled}")
    print(f"  Discord: {alert_config.discord_enabled}")
    print(f"  Rate Limit: {alert_config.rate_limit_per_hour}/hour")
    print(f"✅ AlertConfig created from config")
    
    # Schedule
    print("\n📅 Schedule Configuration:")
    schedule = config.get_schedule_config()
    print(f"  Premarket Scan: {schedule['premarket_scan']} {schedule['timezone']}")
    print(f"  Market Scan: {schedule['market_scan']} {schedule['timezone']}")
    print(f"  Enabled: {schedule['enabled']}")
    
    # Filters
    print("\n🔍 Filter Configuration:")
    filters = config.get_filters_config()
    print(f"  Regime Filter: {filters['enable_regime_filter']}")
    print(f"  Correlation Filter: {filters['enable_correlation_filter']}")
    print(f"  Earnings Filter: {filters['enable_earnings_filter']}")
    print(f"  Min Score: {filters['min_score_threshold']}")
    
    # Database
    print("\n💾 Database Configuration:")
    db = config.get_database_config()
    print(f"  Enabled: {db['enabled']}")
    print(f"  Connection: {db['connection_string']}")
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("""
✅ Configuration system working!

Benefits:
- Single config file for all settings
- Easy to modify without code changes
- Can switch between paper/live modes
- Separate configs for dev/prod environments

To use in your trading system:
1. Load config: config = ConfigLoader()
2. Pass settings to components
3. Update config.yaml for different environments
4. No code changes needed!

Next: Set up your email/Discord webhooks in config.yaml
      and enable alerts for production use.
""")


if __name__ == '__main__':
    demo_config_usage()
