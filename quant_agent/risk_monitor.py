"""
Risk Monitor
Real-time portfolio risk assessment and limit enforcement
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pytz

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_positions: int = 3
    max_position_pct: float = 40.0  # Max % of capital per position
    max_daily_loss_pct: float = 2.0  # Max daily loss as % of capital
    max_sector_exposure_pct: float = 60.0  # Max % in one sector
    max_correlation: float = 0.7  # Max correlation between positions
    min_buying_power_pct: float = 20.0  # Minimum cash reserve %
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'max_positions': self.max_positions,
            'max_position_pct': self.max_position_pct,
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'max_sector_exposure_pct': self.max_sector_exposure_pct,
            'max_correlation': self.max_correlation,
            'min_buying_power_pct': self.min_buying_power_pct
        }


@dataclass
class RiskEvent:
    """Risk event/alert"""
    timestamp: datetime
    severity: str  # 'info', 'warning', 'critical'
    event_type: str
    message: str
    data: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'severity': self.severity,
            'event_type': self.event_type,
            'message': self.message,
            'data': self.data
        }


class RiskMonitor:
    """
    Real-time portfolio risk monitoring
    
    Features:
    - Position size validation
    - Daily loss limits
    - Sector exposure tracking
    - Buying power checks
    - Risk alerts
    - Emergency halt
    """
    
    def __init__(self,
                 initial_capital: float,
                 limits: RiskLimits = None,
                 position_manager=None):
        """
        Initialize risk monitor
        
        Args:
            initial_capital: Starting capital
            limits: Risk limits configuration
            position_manager: Position manager instance
        """
        self.initial_capital = initial_capital
        self.limits = limits or RiskLimits()
        self.position_manager = position_manager
        
        # Risk tracking
        self.daily_start_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.daily_pnl = 0.0
        
        # Risk events
        self.risk_events: List[RiskEvent] = []
        
        # Trading state
        self.trading_halted = False
        self.halt_reason = None
        
        logger.info(f"RiskMonitor initialized (capital=${initial_capital:,.2f})")
    
    def check_pre_trade_risk(self, 
                            ticker: str,
                            quantity: int,
                            price: float) -> Tuple[bool, str]:
        """
        Check if trade passes all risk checks
        
        Args:
            ticker: Ticker symbol
            quantity: Number of shares
            price: Entry price
            
        Returns:
            (can_trade: bool, reason: str)
        """
        # Check if trading is halted
        if self.trading_halted:
            return False, f"Trading halted: {self.halt_reason}"
        
        # Check position count
        if not self._check_max_positions():
            return False, f"Max positions limit reached ({self.limits.max_positions})"
        
        # Check position size
        position_value = quantity * price
        can_size, reason = self._check_position_size(position_value)
        if not can_size:
            return False, reason
        
        # Check buying power
        can_buy, reason = self._check_buying_power(position_value)
        if not can_buy:
            return False, reason
        
        # Check daily loss limit
        if not self._check_daily_loss_limit():
            return False, f"Daily loss limit reached ({self.limits.max_daily_loss_pct}%)"
        
        return True, "OK"
    
    def check_portfolio_risk(self) -> Dict:
        """
        Comprehensive portfolio risk assessment
        
        Returns:
            Dictionary with risk metrics
        """
        metrics = {
            'trading_halted': self.trading_halted,
            'halt_reason': self.halt_reason,
            'checks': {}
        }
        
        # Check each limit
        metrics['checks']['max_positions'] = self._check_max_positions()
        metrics['checks']['daily_loss_limit'] = self._check_daily_loss_limit()
        metrics['checks']['buying_power'] = self._check_min_buying_power()
        
        # Calculate exposure
        if self.position_manager:
            positions = self.position_manager.get_all_positions()
            total_value = sum(p.position_value for p in positions)
            metrics['total_exposure_pct'] = (total_value / self.current_capital * 100) if self.current_capital > 0 else 0
        else:
            metrics['total_exposure_pct'] = 0
        
        # Risk status
        all_checks_pass = all(metrics['checks'].values())
        metrics['risk_status'] = 'healthy' if all_checks_pass else 'warning'
        
        return metrics
    
    def update_capital(self, current_capital: float):
        """
        Update current capital and calculate daily P&L
        
        Args:
            current_capital: Current account value
        """
        self.current_capital = current_capital
        self.daily_pnl = current_capital - self.daily_start_capital
        
        # Update peak capital
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        # Check daily loss limit
        daily_loss_pct = (self.daily_pnl / self.daily_start_capital * 100) if self.daily_start_capital > 0 else 0
        
        if daily_loss_pct <= -self.limits.max_daily_loss_pct:
            self._trigger_risk_event(
                severity='critical',
                event_type='daily_loss_limit',
                message=f"Daily loss limit breached: {daily_loss_pct:.2f}%",
                data={'daily_loss_pct': daily_loss_pct, 'limit': self.limits.max_daily_loss_pct}
            )
            self.halt_trading("Daily loss limit exceeded")
    
    def reset_daily_tracking(self):
        """Reset daily tracking metrics (call at market open)"""
        self.daily_start_capital = self.current_capital
        self.daily_pnl = 0.0
        logger.info(f"Daily tracking reset (starting capital: ${self.current_capital:,.2f})")
    
    def halt_trading(self, reason: str):
        """
        Halt all trading
        
        Args:
            reason: Reason for halt
        """
        if not self.trading_halted:
            self.trading_halted = True
            self.halt_reason = reason
            
            self._trigger_risk_event(
                severity='critical',
                event_type='trading_halted',
                message=f"Trading halted: {reason}",
                data={'reason': reason}
            )
            
            logger.critical(f"🛑 TRADING HALTED: {reason}")
    
    def resume_trading(self):
        """Resume trading after halt"""
        if self.trading_halted:
            self.trading_halted = False
            old_reason = self.halt_reason
            self.halt_reason = None
            
            self._trigger_risk_event(
                severity='info',
                event_type='trading_resumed',
                message="Trading resumed",
                data={'previous_halt_reason': old_reason}
            )
            
            logger.info(f"✅ Trading resumed (was halted: {old_reason})")
    
    def calculate_var(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (simplified)
        
        Args:
            confidence: Confidence level (0.95 = 95%)
            
        Returns:
            VaR amount
        """
        # Simplified VaR - would need historical returns for proper calculation
        if not self.position_manager:
            return 0.0
        
        positions = self.position_manager.get_all_positions()
        total_value = sum(p.position_value for p in positions)
        
        # Assume 2% daily volatility (simplified)
        daily_vol = 0.02
        z_score = 1.645 if confidence == 0.95 else 1.96  # 95% or 99%
        
        var = total_value * daily_vol * z_score
        return var
    
    def get_risk_metrics(self) -> Dict:
        """
        Get comprehensive risk metrics
        
        Returns:
            Dictionary with all risk metrics
        """
        metrics = {
            'capital': {
                'initial': self.initial_capital,
                'current': self.current_capital,
                'peak': self.peak_capital,
                'daily_pnl': self.daily_pnl,
                'daily_pnl_pct': (self.daily_pnl / self.daily_start_capital * 100) if self.daily_start_capital > 0 else 0,
                'total_return_pct': ((self.current_capital / self.initial_capital - 1) * 100) if self.initial_capital > 0 else 0
            },
            'drawdown': {
                'current_dd': self.peak_capital - self.current_capital,
                'current_dd_pct': ((self.peak_capital - self.current_capital) / self.peak_capital * 100) if self.peak_capital > 0 else 0
            },
            'limits': self.limits.to_dict(),
            'trading_state': {
                'halted': self.trading_halted,
                'halt_reason': self.halt_reason
            }
        }
        
        # Add position metrics if available
        if self.position_manager:
            positions = self.position_manager.get_all_positions()
            total_value = sum(p.position_value for p in positions)
            
            metrics['positions'] = {
                'count': len(positions),
                'total_value': total_value,
                'exposure_pct': (total_value / self.current_capital * 100) if self.current_capital > 0 else 0,
                'buying_power': self.current_capital - total_value,
                'buying_power_pct': ((self.current_capital - total_value) / self.current_capital * 100) if self.current_capital > 0 else 0
            }
            
            # Calculate VaR
            metrics['var'] = {
                'var_95': self.calculate_var(0.95),
                'var_99': self.calculate_var(0.99)
            }
        
        return metrics
    
    def get_risk_events(self, 
                       severity: Optional[str] = None,
                       limit: int = 100) -> List[RiskEvent]:
        """
        Get recent risk events
        
        Args:
            severity: Filter by severity ('info', 'warning', 'critical')
            limit: Maximum number of events to return
            
        Returns:
            List of risk events
        """
        events = self.risk_events
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        return events[-limit:]
    
    def _check_max_positions(self) -> bool:
        """Check if below max positions limit"""
        if not self.position_manager:
            return True
        
        current_positions = len(self.position_manager.get_all_positions())
        return current_positions < self.limits.max_positions
    
    def _check_position_size(self, position_value: float) -> Tuple[bool, str]:
        """Check if position size is within limits"""
        max_position_value = self.current_capital * (self.limits.max_position_pct / 100)
        
        if position_value > max_position_value:
            return False, f"Position size ${position_value:,.2f} exceeds limit ${max_position_value:,.2f} ({self.limits.max_position_pct}%)"
        
        return True, "OK"
    
    def _check_buying_power(self, required: float) -> Tuple[bool, str]:
        """Check if sufficient buying power available"""
        if not self.position_manager:
            available = self.current_capital
        else:
            positions = self.position_manager.get_all_positions()
            total_value = sum(p.position_value for p in positions)
            available = self.current_capital - total_value
        
        if required > available:
            return False, f"Insufficient buying power: ${available:,.2f} available, ${required:,.2f} required"
        
        return True, "OK"
    
    def _check_min_buying_power(self) -> bool:
        """Check if maintaining minimum buying power reserve"""
        if not self.position_manager:
            return True
        
        positions = self.position_manager.get_all_positions()
        total_value = sum(p.position_value for p in positions)
        buying_power = self.current_capital - total_value
        
        min_buying_power = self.current_capital * (self.limits.min_buying_power_pct / 100)
        
        return buying_power >= min_buying_power
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit exceeded"""
        if self.daily_start_capital == 0:
            return True
        
        daily_loss_pct = abs(self.daily_pnl / self.daily_start_capital * 100)
        
        if self.daily_pnl < 0 and daily_loss_pct >= self.limits.max_daily_loss_pct:
            return False
        
        return True
    
    def _trigger_risk_event(self,
                           severity: str,
                           event_type: str,
                           message: str,
                           data: Dict):
        """
        Trigger a risk event
        
        Args:
            severity: 'info', 'warning', or 'critical'
            event_type: Type of event
            message: Event message
            data: Additional event data
        """
        event = RiskEvent(
            timestamp=datetime.now(pytz.timezone('America/New_York')),
            severity=severity,
            event_type=event_type,
            message=message,
            data=data
        )
        
        self.risk_events.append(event)
        
        # Log based on severity
        if severity == 'critical':
            logger.critical(f"🚨 {message}")
        elif severity == 'warning':
            logger.warning(f"⚠️ {message}")
        else:
            logger.info(f"ℹ️ {message}")
    
    def get_statistics(self) -> Dict:
        """
        Get risk monitor statistics
        
        Returns:
            Dictionary with stats
        """
        total_events = len(self.risk_events)
        critical_events = len([e for e in self.risk_events if e.severity == 'critical'])
        warning_events = len([e for e in self.risk_events if e.severity == 'warning'])
        
        return {
            'trading_halted': self.trading_halted,
            'current_capital': self.current_capital,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': (self.daily_pnl / self.daily_start_capital * 100) if self.daily_start_capital > 0 else 0,
            'total_risk_events': total_events,
            'critical_events': critical_events,
            'warning_events': warning_events,
            'limits_configured': self.limits.to_dict()
        }
    
    def __repr__(self) -> str:
        status = "HALTED" if self.trading_halted else "ACTIVE"
        return (f"RiskMonitor(status={status}, "
                f"capital=${self.current_capital:,.2f}, "
                f"daily_pnl=${self.daily_pnl:,.2f})")
