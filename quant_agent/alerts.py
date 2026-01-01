"""
Alert System
Sends notifications for trading events via email, SMS, and webhooks
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import requests
import pytz

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class AlertType(Enum):
    """Alert event types"""
    POSITION_OPENED = 'position_opened'
    POSITION_CLOSED = 'position_closed'
    STOP_HIT = 'stop_hit'
    TARGET_HIT = 'target_hit'
    RISK_BREACH = 'risk_breach'
    TRADING_HALTED = 'trading_halted'
    SIGNAL_GENERATED = 'signal_generated'
    ORDER_FILLED = 'order_filled'
    ORDER_REJECTED = 'order_rejected'
    SYSTEM_ERROR = 'system_error'
    DAILY_SUMMARY = 'daily_summary'


@dataclass
class AlertConfig:
    """Alert system configuration"""
    # Email settings
    email_enabled: bool = False
    smtp_host: str = 'smtp.gmail.com'
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    email_to: List[str] = None
    
    # SMS settings (Twilio)
    sms_enabled: bool = False
    twilio_account_sid: str = ''
    twilio_auth_token: str = ''
    twilio_from_number: str = ''
    sms_to: List[str] = None
    
    # Discord webhook
    discord_enabled: bool = False
    discord_webhook_url: str = ''
    
    # Slack webhook
    slack_enabled: bool = False
    slack_webhook_url: str = ''
    
    # Alert level filters
    min_level_email: AlertLevel = AlertLevel.INFO
    min_level_sms: AlertLevel = AlertLevel.CRITICAL
    min_level_discord: AlertLevel = AlertLevel.INFO
    min_level_slack: AlertLevel = AlertLevel.INFO
    
    # Rate limiting (max alerts per hour)
    rate_limit_per_hour: int = 10
    
    def __post_init__(self):
        if self.email_to is None:
            self.email_to = []
        if self.sms_to is None:
            self.sms_to = []


class AlertSystem:
    """
    Multi-channel alert system for trading notifications
    
    Features:
    - Email notifications via SMTP
    - SMS via Twilio (optional)
    - Discord webhook
    - Slack webhook
    - Alert level filtering
    - Rate limiting
    """
    
    def __init__(self, config: AlertConfig = None):
        """
        Initialize alert system
        
        Args:
            config: Alert configuration
        """
        self.config = config or AlertConfig()
        
        # Alert tracking
        self.alerts_sent: List[Dict] = []
        self.last_hour_count = 0
        self.rate_limit_reset_time = datetime.now() + timedelta(hours=1)
        
        logger.info("AlertSystem initialized")
        if self.config.email_enabled:
            logger.info("  Email alerts enabled")
        if self.config.sms_enabled:
            logger.info("  SMS alerts enabled")
        if self.config.discord_enabled:
            logger.info("  Discord alerts enabled")
        if self.config.slack_enabled:
            logger.info("  Slack alerts enabled")
    
    def send_alert(self,
                   alert_type: AlertType,
                   level: AlertLevel,
                   message: str,
                   data: Dict = None) -> Dict:
        """
        Send alert through configured channels
        
        Args:
            alert_type: Type of alert
            level: Alert severity level
            message: Alert message
            data: Additional alert data
            
        Returns:
            Dictionary with send results
        """
        # Check rate limit
        if not self._check_rate_limit():
            logger.warning("Alert rate limit exceeded, skipping alert")
            return {
                'success': False,
                'reason': 'rate_limit_exceeded',
                'message': 'Too many alerts sent this hour'
            }
        
        # Format alert
        timestamp = datetime.now(pytz.timezone('America/New_York'))
        alert_data = {
            'timestamp': timestamp,
            'type': alert_type.value,
            'level': level.value,
            'message': message,
            'data': data or {}
        }
        
        # Track alert
        self.alerts_sent.append(alert_data)
        self.last_hour_count += 1
        
        # Send to channels
        results = {}
        
        if self.config.email_enabled and self._should_send(level, self.config.min_level_email):
            results['email'] = self._send_email(alert_data)
        
        if self.config.sms_enabled and self._should_send(level, self.config.min_level_sms):
            results['sms'] = self._send_sms(alert_data)
        
        if self.config.discord_enabled and self._should_send(level, self.config.min_level_discord):
            results['discord'] = self._send_discord(alert_data)
        
        if self.config.slack_enabled and self._should_send(level, self.config.min_level_slack):
            results['slack'] = self._send_slack(alert_data)
        
        return {
            'success': True,
            'alert_type': alert_type.value,
            'level': level.value,
            'channels': results
        }
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows sending"""
        # Reset counter if hour has passed
        if datetime.now() >= self.rate_limit_reset_time:
            self.last_hour_count = 0
            self.rate_limit_reset_time = datetime.now() + timedelta(hours=1)
        
        return self.last_hour_count < self.config.rate_limit_per_hour
    
    def _should_send(self, alert_level: AlertLevel, min_level) -> bool:
        """Check if alert level meets minimum threshold"""
        level_order = {
            AlertLevel.INFO: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.CRITICAL: 2,
            'info': 0,
            'warning': 1,
            'critical': 2
        }
        
        # Convert string to enum if needed
        if isinstance(min_level, str):
            min_level = min_level.lower()
        
        return level_order.get(alert_level, 0) >= level_order.get(min_level, 0)
    
    def _send_email(self, alert_data: Dict) -> Dict:
        """Send email alert"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert_data['level'].upper()}] {alert_data['type']}"
            msg['From'] = self.config.smtp_user
            msg['To'] = ', '.join(self.config.email_to)
            
            # Format body
            body = self._format_email_body(alert_data)
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent: {alert_data['type']}")
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_sms(self, alert_data: Dict) -> Dict:
        """Send SMS alert via Twilio"""
        try:
            from twilio.rest import Client
            
            client = Client(
                self.config.twilio_account_sid,
                self.config.twilio_auth_token
            )
            
            # Format message (SMS has character limit)
            sms_message = self._format_sms_body(alert_data)
            
            # Send to all numbers
            results = []
            for to_number in self.config.sms_to:
                message = client.messages.create(
                    body=sms_message,
                    from_=self.config.twilio_from_number,
                    to=to_number
                )
                results.append(message.sid)
            
            logger.info(f"SMS alert sent: {alert_data['type']}")
            return {'success': True, 'message_ids': results}
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_discord(self, alert_data: Dict) -> Dict:
        """Send Discord webhook alert"""
        try:
            # Format Discord embed
            embed = self._format_discord_embed(alert_data)
            
            # Send webhook
            response = requests.post(
                self.config.discord_webhook_url,
                json={'embeds': [embed]},
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Discord alert sent: {alert_data['type']}")
                return {'success': True}
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")
                return {'success': False, 'status_code': response.status_code}
                
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_slack(self, alert_data: Dict) -> Dict:
        """Send Slack webhook alert"""
        try:
            # Format Slack message
            payload = self._format_slack_payload(alert_data)
            
            # Send webhook
            response = requests.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {alert_data['type']}")
                return {'success': True}
            else:
                logger.error(f"Slack webhook failed: {response.status_code}")
                return {'success': False, 'status_code': response.status_code}
                
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return {'success': False, 'error': str(e)}
    
    def _format_email_body(self, alert_data: Dict) -> str:
        """Format email body"""
        body = f"""
Trading Alert: {alert_data['type'].replace('_', ' ').title()}
Level: {alert_data['level'].upper()}
Time: {alert_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')}

{alert_data['message']}

"""
        
        if alert_data['data']:
            body += "Additional Details:\n"
            for key, value in alert_data['data'].items():
                body += f"  {key}: {value}\n"
        
        body += "\n---\nAutomated alert from QuantAgent Trading System"
        
        return body
    
    def _format_sms_body(self, alert_data: Dict) -> str:
        """Format SMS body (keep it short)"""
        return (f"[{alert_data['level'].upper()}] "
                f"{alert_data['type'].replace('_', ' ').title()}: "
                f"{alert_data['message'][:100]}")
    
    def _format_discord_embed(self, alert_data: Dict) -> Dict:
        """Format Discord embed"""
        # Color based on level
        colors = {
            'info': 3447003,      # Blue
            'warning': 16776960,  # Yellow
            'critical': 15158332  # Red
        }
        
        embed = {
            'title': f"{alert_data['type'].replace('_', ' ').title()}",
            'description': alert_data['message'],
            'color': colors.get(alert_data['level'], 3447003),
            'timestamp': alert_data['timestamp'].isoformat(),
            'footer': {'text': 'QuantAgent Trading System'}
        }
        
        # Add fields for additional data
        if alert_data['data']:
            embed['fields'] = []
            for key, value in alert_data['data'].items():
                embed['fields'].append({
                    'name': key.replace('_', ' ').title(),
                    'value': str(value),
                    'inline': True
                })
        
        return embed
    
    def _format_slack_payload(self, alert_data: Dict) -> Dict:
        """Format Slack payload"""
        # Emoji based on level
        emojis = {
            'info': ':information_source:',
            'warning': ':warning:',
            'critical': ':rotating_light:'
        }
        
        payload = {
            'text': f"{emojis.get(alert_data['level'], '')} *{alert_data['type'].replace('_', ' ').title()}*",
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': alert_data['message']
                    }
                }
            ]
        }
        
        # Add fields for additional data
        if alert_data['data']:
            fields = []
            for key, value in alert_data['data'].items():
                fields.append({
                    'type': 'mrkdwn',
                    'text': f"*{key.replace('_', ' ').title()}:*\n{value}"
                })
            
            payload['blocks'].append({
                'type': 'section',
                'fields': fields
            })
        
        return payload
    
    # Convenience methods for common alerts
    
    def alert_position_opened(self, ticker: str, quantity: int, price: float, **kwargs):
        """Alert for position opened"""
        message = f"Opened position: {ticker} - {quantity} shares @ ${price:.2f}"
        data = {'ticker': ticker, 'quantity': quantity, 'entry_price': f'${price:.2f}'}
        data.update(kwargs)
        
        return self.send_alert(
            AlertType.POSITION_OPENED,
            AlertLevel.INFO,
            message,
            data
        )
    
    def alert_position_closed(self, ticker: str, pnl: float, pnl_pct: float, reason: str, **kwargs):
        """Alert for position closed"""
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        message = f"{pnl_emoji} Closed position: {ticker} - P&L: ${pnl:.2f} ({pnl_pct:+.2f}%) - {reason}"
        data = {
            'ticker': ticker,
            'pnl': f'${pnl:.2f}',
            'pnl_pct': f'{pnl_pct:+.2f}%',
            'exit_reason': reason
        }
        data.update(kwargs)
        
        level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
        
        return self.send_alert(
            AlertType.POSITION_CLOSED,
            level,
            message,
            data
        )
    
    def alert_stop_hit(self, ticker: str, price: float, loss: float):
        """Alert for stop loss hit"""
        message = f"Stop loss hit: {ticker} @ ${price:.2f} - Loss: ${loss:.2f}"
        data = {'ticker': ticker, 'price': f'${price:.2f}', 'loss': f'${loss:.2f}'}
        
        return self.send_alert(
            AlertType.STOP_HIT,
            AlertLevel.WARNING,
            message,
            data
        )
    
    def alert_target_hit(self, ticker: str, price: float, profit: float):
        """Alert for take profit hit"""
        message = f"Take profit hit: {ticker} @ ${price:.2f} - Profit: ${profit:.2f}"
        data = {'ticker': ticker, 'price': f'${price:.2f}', 'profit': f'${profit:.2f}'}
        
        return self.send_alert(
            AlertType.TARGET_HIT,
            AlertLevel.INFO,
            message,
            data
        )
    
    def alert_risk_breach(self, breach_type: str, current: float, limit: float):
        """Alert for risk limit breach"""
        message = f"Risk limit breached: {breach_type} - Current: {current:.2f} | Limit: {limit:.2f}"
        data = {'breach_type': breach_type, 'current_value': current, 'limit': limit}
        
        return self.send_alert(
            AlertType.RISK_BREACH,
            AlertLevel.CRITICAL,
            message,
            data
        )
    
    def alert_trading_halted(self, reason: str, loss_pct: float = None):
        """Alert for trading halt"""
        message = f"Trading HALTED: {reason}"
        data = {'reason': reason}
        if loss_pct is not None:
            data['daily_loss'] = f'{loss_pct:+.2f}%'
        
        return self.send_alert(
            AlertType.TRADING_HALTED,
            AlertLevel.CRITICAL,
            message,
            data
        )
    
    def alert_system_error(self, error: str, component: str = None):
        """Alert for system error"""
        message = f"System error: {error}"
        data = {'error': error}
        if component:
            data['component'] = component
        
        return self.send_alert(
            AlertType.SYSTEM_ERROR,
            AlertLevel.CRITICAL,
            message,
            data
        )
    
    def alert_daily_summary(self, trades: int, pnl: float, win_rate: float, **kwargs):
        """Alert for daily summary"""
        message = f"Daily Summary: {trades} trades | P&L: ${pnl:.2f} | Win Rate: {win_rate:.1f}%"
        data = {
            'total_trades': trades,
            'total_pnl': f'${pnl:.2f}',
            'win_rate': f'{win_rate:.1f}%'
        }
        data.update(kwargs)
        
        level = AlertLevel.INFO if pnl >= 0 else AlertLevel.WARNING
        
        return self.send_alert(
            AlertType.DAILY_SUMMARY,
            level,
            message,
            data
        )
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return self.alerts_sent[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get alert statistics"""
        total = len(self.alerts_sent)
        
        if total == 0:
            return {
                'total_alerts': 0,
                'by_level': {},
                'by_type': {},
                'rate_limit_status': {
                    'current_hour_count': self.last_hour_count,
                    'limit': self.config.rate_limit_per_hour,
                    'reset_time': self.rate_limit_reset_time.isoformat()
                }
            }
        
        # Count by level
        by_level = {}
        for alert in self.alerts_sent:
            level = alert['level']
            by_level[level] = by_level.get(level, 0) + 1
        
        # Count by type
        by_type = {}
        for alert in self.alerts_sent:
            atype = alert['type']
            by_type[atype] = by_type.get(atype, 0) + 1
        
        return {
            'total_alerts': total,
            'by_level': by_level,
            'by_type': by_type,
            'rate_limit_status': {
                'current_hour_count': self.last_hour_count,
                'limit': self.config.rate_limit_per_hour,
                'reset_time': self.rate_limit_reset_time.isoformat()
            }
        }
    
    def __repr__(self) -> str:
        enabled = []
        if self.config.email_enabled:
            enabled.append('email')
        if self.config.sms_enabled:
            enabled.append('sms')
        if self.config.discord_enabled:
            enabled.append('discord')
        if self.config.slack_enabled:
            enabled.append('slack')
        
        return f"AlertSystem(channels={enabled}, alerts_sent={len(self.alerts_sent)})"
