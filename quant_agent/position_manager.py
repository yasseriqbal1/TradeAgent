"""
Position Manager
Tracks active positions, calculates P&L, manages exits
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import pytz

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position"""
    ticker: str
    quantity: int
    entry_price: float
    entry_date: datetime
    
    # Exit targets
    stop_loss: float
    take_profit: float
    max_hold_days: int
    
    # Current status
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    # Order tracking
    entry_order_id: str = ''
    stop_order_id: str = ''
    take_profit_order_id: str = ''
    
    # Metadata
    signal_id: Optional[str] = None
    notes: str = ''
    
    # Exit tracking
    exit_triggered: bool = False
    exit_reason: Optional[str] = None
    
    @property
    def position_value(self) -> float:
        """Current position value"""
        return self.quantity * self.current_price
    
    @property
    def entry_value(self) -> float:
        """Entry position value"""
        return self.quantity * self.entry_price
    
    @property
    def days_held(self) -> int:
        """Days position has been held"""
        return (datetime.now(pytz.timezone('America/New_York')) - self.entry_date).days
    
    @property
    def should_exit_max_hold(self) -> bool:
        """Check if max hold days reached"""
        return self.days_held >= self.max_hold_days
    
    @property
    def stop_hit(self) -> bool:
        """Check if stop loss hit"""
        return self.current_price <= self.stop_loss
    
    @property
    def target_hit(self) -> bool:
        """Check if take profit hit"""
        return self.current_price >= self.take_profit
    
    def update_price(self, price: float):
        """Update current price and recalculate P&L"""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity
        self.unrealized_pnl_pct = ((price / self.entry_price) - 1) * 100
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'ticker': self.ticker,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'max_hold_days': self.max_hold_days,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'position_value': self.position_value,
            'days_held': self.days_held,
            'entry_order_id': self.entry_order_id,
            'stop_order_id': self.stop_order_id,
            'take_profit_order_id': self.take_profit_order_id,
            'signal_id': self.signal_id,
            'notes': self.notes,
            'exit_triggered': self.exit_triggered,
            'exit_reason': self.exit_reason
        }
    
    def __repr__(self) -> str:
        return (f"Position({self.ticker} {self.quantity} @ ${self.entry_price:.2f}, "
                f"P&L: ${self.unrealized_pnl:.2f} ({self.unrealized_pnl_pct:+.2f}%))")


class PositionManager:
    """
    Manages active trading positions
    
    Features:
    - Position tracking
    - P&L calculation
    - Exit condition monitoring
    - Position limits enforcement
    """
    
    def __init__(self, 
                 max_positions: int = 3,
                 realtime_handler=None,
                 order_manager=None):
        """
        Initialize position manager
        
        Args:
            max_positions: Maximum concurrent positions
            realtime_handler: Real-time data handler
            order_manager: Order manager for exit orders
        """
        self.max_positions = max_positions
        self.realtime_handler = realtime_handler
        self.order_manager = order_manager
        
        # Position storage
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        
        logger.info(f"PositionManager initialized (max_positions={max_positions})")
    
    def can_open_position(self, ticker: str) -> tuple[bool, str]:
        """
        Check if can open a new position
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            (can_open: bool, reason: str)
        """
        # Check if already have position in this ticker
        if ticker in self.positions:
            return False, f"Already have position in {ticker}"
        
        # Check max positions limit
        if len(self.positions) >= self.max_positions:
            return False, f"Max positions limit reached ({self.max_positions})"
        
        return True, "OK"
    
    def open_position(self,
                     ticker: str,
                     quantity: int,
                     entry_price: float,
                     stop_loss: float,
                     take_profit: float,
                     max_hold_days: int = 5,
                     entry_order_id: str = '',
                     signal_id: Optional[str] = None,
                     notes: str = '') -> Optional[Position]:
        """
        Open a new position
        
        Args:
            ticker: Ticker symbol
            quantity: Number of shares
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            max_hold_days: Maximum holding period
            entry_order_id: Associated entry order ID
            signal_id: Associated signal ID
            notes: Optional notes
            
        Returns:
            Position object or None if failed
        """
        # Check if can open
        can_open, reason = self.can_open_position(ticker)
        if not can_open:
            logger.warning(f"Cannot open position in {ticker}: {reason}")
            return None
        
        # Create position
        position = Position(
            ticker=ticker,
            quantity=quantity,
            entry_price=entry_price,
            entry_date=datetime.now(pytz.timezone('America/New_York')),
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_hold_days=max_hold_days,
            current_price=entry_price,
            entry_order_id=entry_order_id,
            signal_id=signal_id,
            notes=notes
        )
        
        # Submit stop loss and take profit orders if order manager available
        if self.order_manager:
            try:
                # Create stop loss order
                from .order_manager import OrderSide
                stop_order = self.order_manager.create_stop_loss_order(
                    ticker=ticker,
                    quantity=quantity,
                    stop_price=stop_loss,
                    signal_id=signal_id,
                    notes=f'stop_for_position_{ticker}'
                )
                self.order_manager.submit_order(stop_order.id)
                position.stop_order_id = stop_order.id
                
                # Create take profit order
                tp_order = self.order_manager.create_limit_order(
                    ticker=ticker,
                    side=OrderSide.SELL,
                    quantity=quantity,
                    limit_price=take_profit,
                    signal_id=signal_id,
                    notes=f'tp_for_position_{ticker}'
                )
                self.order_manager.submit_order(tp_order.id)
                position.take_profit_order_id = tp_order.id
                
                logger.info(f"Created exit orders: stop={stop_order.id}, tp={tp_order.id}")
                
            except Exception as e:
                logger.error(f"Failed to create exit orders: {e}")
        
        # Add to positions
        self.positions[ticker] = position
        
        logger.info(f"Opened position: {position}")
        return position
    
    def close_position(self, 
                      ticker: str, 
                      exit_price: float,
                      exit_reason: str = 'manual') -> Optional[Position]:
        """
        Close an existing position
        
        Args:
            ticker: Ticker symbol
            exit_price: Exit price
            exit_reason: Reason for exit
            
        Returns:
            Closed position or None if not found
        """
        position = self.positions.get(ticker)
        if not position:
            logger.warning(f"No position found for {ticker}")
            return None
        
        # Update final price
        position.update_price(exit_price)
        position.exit_triggered = True
        position.exit_reason = exit_reason
        
        # Cancel any pending exit orders
        if self.order_manager:
            if position.stop_order_id:
                self.order_manager.cancel_order(position.stop_order_id)
            if position.take_profit_order_id:
                self.order_manager.cancel_order(position.take_profit_order_id)
        
        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[ticker]
        
        logger.info(f"Closed position: {ticker} - {exit_reason} - "
                   f"P&L: ${position.unrealized_pnl:.2f} ({position.unrealized_pnl_pct:+.2f}%)")
        
        return position
    
    def update_positions(self):
        """Update all position prices and P&L"""
        if not self.realtime_handler:
            logger.warning("No realtime handler available for price updates")
            return
        
        for ticker, position in self.positions.items():
            try:
                current_price = self.realtime_handler.get_last_price(ticker)
                if current_price:
                    position.update_price(current_price)
                    logger.debug(f"Updated {ticker}: ${current_price:.2f}, "
                               f"P&L: ${position.unrealized_pnl:.2f}")
            except Exception as e:
                logger.error(f"Failed to update price for {ticker}: {e}")
    
    def check_exit_conditions(self) -> List[tuple[str, str]]:
        """
        Check if any positions should be exited
        
        Returns:
            List of (ticker, exit_reason) tuples
        """
        exits = []
        
        for ticker, position in self.positions.items():
            # Check stop loss
            if position.stop_hit:
                exits.append((ticker, 'stop_loss'))
                logger.info(f"{ticker} stop loss hit: ${position.current_price:.2f} <= ${position.stop_loss:.2f}")
            
            # Check take profit
            elif position.target_hit:
                exits.append((ticker, 'take_profit'))
                logger.info(f"{ticker} take profit hit: ${position.current_price:.2f} >= ${position.take_profit:.2f}")
            
            # Check max hold days
            elif position.should_exit_max_hold:
                exits.append((ticker, 'max_hold'))
                logger.info(f"{ticker} max hold days reached: {position.days_held} >= {position.max_hold_days}")
        
        return exits
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position by ticker"""
        return self.positions.get(ticker)
    
    def get_all_positions(self) -> List[Position]:
        """Get all active positions"""
        return list(self.positions.values())
    
    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions"""
        return self.closed_positions
    
    def calculate_portfolio_pnl(self) -> Dict:
        """
        Calculate portfolio-level P&L
        
        Returns:
            Dictionary with P&L metrics
        """
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_value = sum(p.position_value for p in self.positions.values())
        total_cost = sum(p.entry_value for p in self.positions.values())
        
        # Calculate realized P&L from closed positions
        total_realized = sum(p.unrealized_pnl for p in self.closed_positions)
        
        return {
            'unrealized_pnl': total_unrealized,
            'realized_pnl': total_realized,
            'total_pnl': total_unrealized + total_realized,
            'total_value': total_value,
            'total_cost': total_cost,
            'num_positions': len(self.positions),
            'num_closed': len(self.closed_positions)
        }
    
    def get_position_summary(self) -> Dict:
        """
        Get summary of all positions
        
        Returns:
            Dictionary with position details
        """
        summary = {
            'active_positions': [],
            'total_value': 0.0,
            'total_pnl': 0.0,
            'positions_count': len(self.positions)
        }
        
        for ticker, position in self.positions.items():
            summary['active_positions'].append({
                'ticker': ticker,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'pnl': position.unrealized_pnl,
                'pnl_pct': position.unrealized_pnl_pct,
                'days_held': position.days_held,
                'value': position.position_value
            })
            summary['total_value'] += position.position_value
            summary['total_pnl'] += position.unrealized_pnl
        
        return summary
    
    def get_statistics(self) -> Dict:
        """
        Get position manager statistics
        
        Returns:
            Dictionary with stats
        """
        pnl = self.calculate_portfolio_pnl()
        
        # Win/loss stats from closed positions
        winners = [p for p in self.closed_positions if p.unrealized_pnl > 0]
        losers = [p for p in self.closed_positions if p.unrealized_pnl < 0]
        
        win_rate = len(winners) / len(self.closed_positions) * 100 if self.closed_positions else 0
        
        avg_win = sum(p.unrealized_pnl for p in winners) / len(winners) if winners else 0
        avg_loss = sum(p.unrealized_pnl for p in losers) / len(losers) if losers else 0
        
        return {
            'max_positions': self.max_positions,
            'active_positions': len(self.positions),
            'closed_positions': len(self.closed_positions),
            'unrealized_pnl': pnl['unrealized_pnl'],
            'realized_pnl': pnl['realized_pnl'],
            'total_pnl': pnl['total_pnl'],
            'win_rate': win_rate,
            'total_winners': len(winners),
            'total_losers': len(losers),
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }
    
    def __repr__(self) -> str:
        pnl = sum(p.unrealized_pnl for p in self.positions.values())
        return (f"PositionManager(active={len(self.positions)}/{self.max_positions}, "
                f"P&L=${pnl:.2f})")
