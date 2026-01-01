"""
Order Management System
Handles order creation, submission, and tracking for paper/live trading
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import pytz
import uuid

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side"""
    BUY = 'buy'
    SELL = 'sell'


class OrderType(Enum):
    """Order types"""
    MARKET = 'market'
    LIMIT = 'limit'
    STOP_LOSS = 'stop_loss'
    TAKE_PROFIT = 'take_profit'


class OrderStatus(Enum):
    """Order status"""
    PENDING = 'pending'
    SUBMITTED = 'submitted'
    FILLED = 'filled'
    PARTIALLY_FILLED = 'partially_filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


@dataclass
class Order:
    """Order representation"""
    id: str
    ticker: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    status: OrderStatus
    
    # Pricing
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_price: Optional[float] = None
    
    # Execution
    filled_quantity: int = 0
    remaining_quantity: int = 0
    commission: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(pytz.timezone('America/New_York')))
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Metadata
    signal_id: Optional[str] = None
    notes: str = ''
    
    def __post_init__(self):
        """Initialize remaining quantity"""
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.quantity
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'ticker': self.ticker,
            'side': self.side.value,
            'quantity': self.quantity,
            'order_type': self.order_type.value,
            'status': self.status.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'filled_price': self.filled_price,
            'filled_quantity': self.filled_quantity,
            'remaining_quantity': self.remaining_quantity,
            'commission': self.commission,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'signal_id': self.signal_id,
            'notes': self.notes
        }
    
    def __repr__(self) -> str:
        return (f"Order({self.ticker} {self.side.value} {self.quantity} @ "
                f"{self.order_type.value}, status={self.status.value})")


class OrderManager:
    """
    Manages order lifecycle for paper/live trading
    
    Features:
    - Order creation and validation
    - Paper trading simulation
    - Order status tracking
    - Fill simulation
    - Commission calculation
    """
    
    def __init__(self, 
                 mode: str = 'paper',
                 realtime_handler=None,
                 commission_per_trade: float = 1.0,
                 slippage_pct: float = 0.05):
        """
        Initialize order manager
        
        Args:
            mode: 'paper' or 'live' trading mode
            realtime_handler: Real-time data handler for price quotes
            commission_per_trade: Commission per trade in dollars
            slippage_pct: Slippage percentage for market orders
        """
        self.mode = mode
        self.realtime_handler = realtime_handler
        self.commission_per_trade = commission_per_trade
        self.slippage_pct = slippage_pct
        
        # Order storage
        self.orders: Dict[str, Order] = {}
        self.pending_orders: List[str] = []
        self.filled_orders: List[str] = []
        
        logger.info(f"OrderManager initialized (mode={mode})")
    
    def create_market_order(self, 
                           ticker: str, 
                           side: OrderSide, 
                           quantity: int,
                           signal_id: Optional[str] = None,
                           notes: str = '') -> Order:
        """
        Create a market order
        
        Args:
            ticker: Ticker symbol
            side: OrderSide.BUY or OrderSide.SELL
            quantity: Number of shares
            signal_id: Associated signal ID
            notes: Optional notes
            
        Returns:
            Order object
        """
        order_id = self._generate_order_id()
        
        order = Order(
            id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            signal_id=signal_id,
            notes=notes
        )
        
        self.orders[order_id] = order
        self.pending_orders.append(order_id)
        
        logger.info(f"Created market order: {order}")
        return order
    
    def create_limit_order(self,
                          ticker: str,
                          side: OrderSide,
                          quantity: int,
                          limit_price: float,
                          signal_id: Optional[str] = None,
                          notes: str = '') -> Order:
        """
        Create a limit order
        
        Args:
            ticker: Ticker symbol
            side: OrderSide.BUY or OrderSide.SELL
            quantity: Number of shares
            limit_price: Limit price
            signal_id: Associated signal ID
            notes: Optional notes
            
        Returns:
            Order object
        """
        order_id = self._generate_order_id()
        
        order = Order(
            id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            limit_price=limit_price,
            signal_id=signal_id,
            notes=notes
        )
        
        self.orders[order_id] = order
        self.pending_orders.append(order_id)
        
        logger.info(f"Created limit order: {order}")
        return order
    
    def create_stop_loss_order(self,
                              ticker: str,
                              quantity: int,
                              stop_price: float,
                              signal_id: Optional[str] = None,
                              notes: str = '') -> Order:
        """
        Create a stop loss order
        
        Args:
            ticker: Ticker symbol
            quantity: Number of shares
            stop_price: Stop price trigger
            signal_id: Associated signal ID
            notes: Optional notes
            
        Returns:
            Order object
        """
        order_id = self._generate_order_id()
        
        order = Order(
            id=order_id,
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=OrderType.STOP_LOSS,
            status=OrderStatus.PENDING,
            stop_price=stop_price,
            signal_id=signal_id,
            notes=notes
        )
        
        self.orders[order_id] = order
        self.pending_orders.append(order_id)
        
        logger.info(f"Created stop loss order: {order}")
        return order
    
    def create_bracket_order(self,
                            ticker: str,
                            quantity: int,
                            entry_price: float,
                            stop_loss: float,
                            take_profit: float,
                            signal_id: Optional[str] = None) -> Dict[str, Order]:
        """
        Create bracket order (entry + stop loss + take profit)
        
        Args:
            ticker: Ticker symbol
            quantity: Number of shares
            entry_price: Entry limit price
            stop_loss: Stop loss price
            take_profit: Take profit price
            signal_id: Associated signal ID
            
        Returns:
            Dictionary with 'entry', 'stop_loss', 'take_profit' orders
        """
        # Create entry order
        entry = self.create_limit_order(
            ticker=ticker,
            side=OrderSide.BUY,
            quantity=quantity,
            limit_price=entry_price,
            signal_id=signal_id,
            notes='bracket_entry'
        )
        
        # Create stop loss order
        stop = self.create_stop_loss_order(
            ticker=ticker,
            quantity=quantity,
            stop_price=stop_loss,
            signal_id=signal_id,
            notes=f'bracket_stop_for_{entry.id}'
        )
        
        # Create take profit order
        take_profit_order = self.create_limit_order(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=quantity,
            limit_price=take_profit,
            signal_id=signal_id,
            notes=f'bracket_tp_for_{entry.id}'
        )
        
        logger.info(f"Created bracket order for {ticker}: entry={entry.id}, sl={stop.id}, tp={take_profit_order.id}")
        
        return {
            'entry': entry,
            'stop_loss': stop,
            'take_profit': take_profit_order
        }
    
    def submit_order(self, order_id: str) -> bool:
        """
        Submit an order for execution
        
        Args:
            order_id: Order ID
            
        Returns:
            True if submitted successfully
        """
        order = self.orders.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found")
            return False
        
        if order.status != OrderStatus.PENDING:
            logger.warning(f"Order {order_id} already submitted (status={order.status.value})")
            return False
        
        try:
            if self.mode == 'paper':
                # Paper trading - simulate immediate fill for market orders
                if order.order_type == OrderType.MARKET:
                    return self._simulate_market_fill(order)
                else:
                    # Limit/stop orders - mark as submitted and wait
                    order.status = OrderStatus.SUBMITTED
                    order.submitted_at = datetime.now(pytz.timezone('America/New_York'))
                    logger.info(f"Order {order_id} submitted (paper mode)")
                    return True
            
            elif self.mode == 'live':
                # Live trading - submit to broker API
                # TODO: Implement live trading submission
                logger.error("Live trading not yet implemented")
                return False
            
        except Exception as e:
            logger.error(f"Failed to submit order {order_id}: {e}")
            order.status = OrderStatus.REJECTED
            return False
        
        return False
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order
        
        Args:
            order_id: Order ID
            
        Returns:
            True if cancelled successfully
        """
        order = self.orders.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found")
            return False
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            logger.warning(f"Cannot cancel order {order_id} (status={order.status.value})")
            return False
        
        order.status = OrderStatus.CANCELLED
        
        if order_id in self.pending_orders:
            self.pending_orders.remove(order_id)
        
        logger.info(f"Order {order_id} cancelled")
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return self.orders.get(order_id)
    
    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders"""
        return [self.orders[oid] for oid in self.pending_orders if oid in self.orders]
    
    def get_filled_orders(self) -> List[Order]:
        """Get all filled orders"""
        return [self.orders[oid] for oid in self.filled_orders if oid in self.orders]
    
    def get_orders_by_ticker(self, ticker: str) -> List[Order]:
        """Get all orders for a ticker"""
        return [order for order in self.orders.values() if order.ticker == ticker]
    
    def check_limit_orders(self) -> List[str]:
        """
        Check if any limit orders should be filled
        
        Returns:
            List of filled order IDs
        """
        if not self.realtime_handler:
            return []
        
        filled = []
        
        for order_id in self.pending_orders.copy():
            order = self.orders.get(order_id)
            if not order or order.order_type != OrderType.LIMIT:
                continue
            
            # Get current price
            current_price = self.realtime_handler.get_last_price(order.ticker)
            if not current_price:
                continue
            
            # Check if limit price reached
            should_fill = False
            if order.side == OrderSide.BUY and current_price <= order.limit_price:
                should_fill = True
            elif order.side == OrderSide.SELL and current_price >= order.limit_price:
                should_fill = True
            
            if should_fill:
                if self._simulate_fill(order, order.limit_price):
                    filled.append(order_id)
        
        return filled
    
    def check_stop_orders(self) -> List[str]:
        """
        Check if any stop loss orders should be triggered
        
        Returns:
            List of filled order IDs
        """
        if not self.realtime_handler:
            return []
        
        filled = []
        
        for order_id in self.pending_orders.copy():
            order = self.orders.get(order_id)
            if not order or order.order_type != OrderType.STOP_LOSS:
                continue
            
            # Get current price
            current_price = self.realtime_handler.get_last_price(order.ticker)
            if not current_price:
                continue
            
            # Check if stop price triggered
            if current_price <= order.stop_price:
                # Stop triggered - fill at current price (with slippage)
                fill_price = current_price * (1 - self.slippage_pct / 100)
                if self._simulate_fill(order, fill_price):
                    filled.append(order_id)
        
        return filled
    
    def _simulate_market_fill(self, order: Order) -> bool:
        """
        Simulate immediate fill for market order
        
        Args:
            order: Order to fill
            
        Returns:
            True if filled successfully
        """
        if not self.realtime_handler:
            logger.error("No realtime handler available for price")
            return False
        
        # Get current price
        current_price = self.realtime_handler.get_last_price(order.ticker)
        if not current_price:
            logger.error(f"No price available for {order.ticker}")
            order.status = OrderStatus.REJECTED
            return False
        
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = current_price * (1 + self.slippage_pct / 100)
        else:
            fill_price = current_price * (1 - self.slippage_pct / 100)
        
        return self._simulate_fill(order, fill_price)
    
    def _simulate_fill(self, order: Order, fill_price: float) -> bool:
        """
        Simulate order fill
        
        Args:
            order: Order to fill
            fill_price: Fill price
            
        Returns:
            True if filled successfully
        """
        order.filled_price = fill_price
        order.filled_quantity = order.quantity
        order.remaining_quantity = 0
        order.commission = self.commission_per_trade
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now(pytz.timezone('America/New_York'))
        
        # Move from pending to filled
        if order.id in self.pending_orders:
            self.pending_orders.remove(order.id)
        
        if order.id not in self.filled_orders:
            self.filled_orders.append(order.id)
        
        logger.info(f"Order {order.id} filled: {order.ticker} {order.side.value} "
                   f"{order.quantity} @ ${fill_price:.2f}")
        
        return True
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        return f"ORD_{uuid.uuid4().hex[:8].upper()}"
    
    def get_statistics(self) -> Dict:
        """
        Get order manager statistics
        
        Returns:
            Dictionary with stats
        """
        return {
            'mode': self.mode,
            'total_orders': len(self.orders),
            'pending_orders': len(self.pending_orders),
            'filled_orders': len(self.filled_orders),
            'commission_per_trade': self.commission_per_trade,
            'slippage_pct': self.slippage_pct
        }
    
    def __repr__(self) -> str:
        return (f"OrderManager(mode={self.mode}, "
                f"total={len(self.orders)}, "
                f"pending={len(self.pending_orders)}, "
                f"filled={len(self.filled_orders)})")
