"""
Trade Executor
Main orchestrator for live trading - connects all components
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import time
import pytz

logger = logging.getLogger(__name__)


class ExecutorState(Enum):
    """Executor state"""
    STOPPED = 'stopped'
    RUNNING = 'running'
    PAUSED = 'paused'
    ERROR = 'error'


class TradeExecutor:
    """
    Main trading system orchestrator
    
    Coordinates:
    - Signal generation
    - Risk checks
    - Order execution
    - Position monitoring
    - Exit management
    """
    
    def __init__(self,
                 signal_generator,
                 order_manager,
                 position_manager,
                 risk_monitor,
                 realtime_handler,
                 alert_system=None):
        """
        Initialize trade executor
        
        Args:
            signal_generator: LiveSignalGenerator instance
            order_manager: OrderManager instance
            position_manager: PositionManager instance
            risk_monitor: RiskMonitor instance
            realtime_handler: RealtimeDataHandler instance
            alert_system: AlertSystem instance (optional)
        """
        self.signal_generator = signal_generator
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.risk_monitor = risk_monitor
        self.realtime_handler = realtime_handler
        self.alert_system = alert_system
        
        # Executor state
        self.state = ExecutorState.STOPPED
        self.error_message = None
        
        # Execution tracking
        self.signals_processed = 0
        self.trades_executed = 0
        self.trades_rejected = 0
        
        logger.info("TradeExecutor initialized")
    
    def start(self):
        """Start the trading system"""
        if self.state == ExecutorState.RUNNING:
            logger.warning("Executor already running")
            return
        
        self.state = ExecutorState.RUNNING
        logger.info("🚀 Trade Executor STARTED")
    
    def stop(self):
        """Stop the trading system"""
        if self.state == ExecutorState.STOPPED:
            logger.warning("Executor already stopped")
            return
        
        self.state = ExecutorState.STOPPED
        logger.info("🛑 Trade Executor STOPPED")
    
    def pause(self):
        """Pause trading (maintain positions but don't open new)"""
        if self.state == ExecutorState.RUNNING:
            self.state = ExecutorState.PAUSED
            logger.info("⏸️ Trade Executor PAUSED")
    
    def resume(self):
        """Resume trading from pause"""
        if self.state == ExecutorState.PAUSED:
            self.state = ExecutorState.RUNNING
            logger.info("▶️ Trade Executor RESUMED")
    
    def process_signals(self, tickers: List[str]) -> Dict:
        """
        Generate and process trading signals
        
        Args:
            tickers: List of tickers to scan
            
        Returns:
            Dictionary with results
        """
        if self.state != ExecutorState.RUNNING:
            logger.warning(f"Executor not running (state={self.state.value})")
            return {'success': False, 'reason': f'Executor state: {self.state.value}'}
        
        if self.risk_monitor.trading_halted:
            logger.warning("Trading halted by risk monitor")
            return {'success': False, 'reason': 'Trading halted'}
        
        try:
            # Generate signals
            logger.info(f"Generating signals for {len(tickers)} tickers...")
            signals = self.signal_generator.run_scan(tickers, scan_type='on_demand')
            
            self.signals_processed += len(signals)
            
            if not signals:
                logger.info("No signals generated")
                return {
                    'success': True,
                    'signals_generated': 0,
                    'trades_executed': 0
                }
            
            logger.info(f"Generated {len(signals)} signals")
            
            # Process each signal
            trades_executed = 0
            trades_rejected = 0
            
            for signal in signals:
                result = self.execute_entry(signal)
                if result['success']:
                    trades_executed += 1
                else:
                    trades_rejected += 1
            
            return {
                'success': True,
                'signals_generated': len(signals),
                'trades_executed': trades_executed,
                'trades_rejected': trades_rejected
            }
            
        except Exception as e:
            logger.error(f"Error processing signals: {e}", exc_info=True)
            self.state = ExecutorState.ERROR
            self.error_message = str(e)
            return {'success': False, 'error': str(e)}
    
    def execute_entry(self, signal) -> Dict:
        """
        Execute entry for a signal
        
        Args:
            signal: Signal object
            
        Returns:
            Dictionary with execution result
        """
        ticker = signal.ticker
        
        try:
            # Check if can open position
            can_open, reason = self.position_manager.can_open_position(ticker)
            if not can_open:
                logger.info(f"Cannot open {ticker}: {reason}")
                self.trades_rejected += 1
                return {'success': False, 'reason': reason}
            
            # Check risk
            can_trade, reason = self.risk_monitor.check_pre_trade_risk(
                ticker=ticker,
                quantity=signal.shares,
                price=signal.price
            )
            
            if not can_trade:
                logger.info(f"Risk check failed for {ticker}: {reason}")
                self.trades_rejected += 1
                return {'success': False, 'reason': reason}
            
            # Create and submit market order
            logger.info(f"Executing entry: {ticker} {signal.shares} @ ${signal.price:.2f}")
            
            from .order_manager import OrderSide
            order = self.order_manager.create_market_order(
                ticker=ticker,
                side=OrderSide.BUY,
                quantity=signal.shares,
                signal_id=signal.timestamp.isoformat(),
                notes=f'entry_from_signal_score_{signal.composite_score:.1f}'
            )
            
            # Submit order
            if self.order_manager.submit_order(order.id):
                logger.info(f"✅ Order {order.id} submitted and filled")
                
                # Open position
                position = self.position_manager.open_position(
                    ticker=ticker,
                    quantity=signal.shares,
                    entry_price=order.filled_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    max_hold_days=signal.max_hold_days,
                    entry_order_id=order.id,
                    signal_id=signal.timestamp.isoformat()
                )
                
                if position:
                    logger.info(f"📈 Position opened: {position}")
                    self.trades_executed += 1
                    
                    # Send alert
                    if self.alert_system:
                        self.alert_system.alert_position_opened(
                            ticker=ticker,
                            quantity=signal.shares,
                            price=order.filled_price,
                            stop_loss=signal.stop_loss,
                            take_profit=signal.take_profit
                        )
                    
                    return {
                        'success': True,
                        'order_id': order.id,
                        'ticker': ticker,
                        'entry_price': order.filled_price,
                        'quantity': signal.shares
                    }
                else:
                    logger.error(f"Failed to create position for {ticker}")
                    return {'success': False, 'reason': 'Position creation failed'}
            else:
                logger.error(f"Failed to submit order for {ticker}")
                self.trades_rejected += 1
                return {'success': False, 'reason': 'Order submission failed'}
                
        except Exception as e:
            logger.error(f"Error executing entry for {ticker}: {e}", exc_info=True)
            self.trades_rejected += 1
            return {'success': False, 'error': str(e)}
    
    def monitor_positions(self) -> Dict:
        """
        Monitor active positions and execute exits
        
        Returns:
            Dictionary with monitoring results
        """
        if self.state == ExecutorState.STOPPED:
            return {'success': False, 'reason': 'Executor stopped'}
        
        try:
            # Update position prices
            self.position_manager.update_positions()
            
            # Check exit conditions
            exits = self.position_manager.check_exit_conditions()
            
            if not exits:
                return {
                    'success': True,
                    'positions_monitored': len(self.position_manager.get_all_positions()),
                    'exits_triggered': 0
                }
            
            # Execute exits
            exits_executed = 0
            for ticker, reason in exits:
                result = self.execute_exit(ticker, reason)
                if result['success']:
                    exits_executed += 1
            
            return {
                'success': True,
                'positions_monitored': len(self.position_manager.get_all_positions()),
                'exits_triggered': len(exits),
                'exits_executed': exits_executed
            }
            
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def execute_exit(self, ticker: str, reason: str) -> Dict:
        """
        Execute exit for a position
        
        Args:
            ticker: Ticker symbol
            reason: Exit reason
            
        Returns:
            Dictionary with execution result
        """
        try:
            position = self.position_manager.get_position(ticker)
            if not position:
                return {'success': False, 'reason': 'Position not found'}
            
            # Get current price
            current_price = self.realtime_handler.get_last_price(ticker)
            if not current_price:
                logger.error(f"No price available for {ticker}")
                return {'success': False, 'reason': 'No price available'}
            
            logger.info(f"Executing exit: {ticker} - {reason} @ ${current_price:.2f}")
            
            # Create and submit sell order
            from .order_manager import OrderSide
            order = self.order_manager.create_market_order(
                ticker=ticker,
                side=OrderSide.SELL,
                quantity=position.quantity,
                notes=f'exit_{reason}'
            )
            
            if self.order_manager.submit_order(order.id):
                logger.info(f"✅ Exit order {order.id} filled")
                
                # Close position
                closed = self.position_manager.close_position(
                    ticker=ticker,
                    exit_price=order.filled_price,
                    exit_reason=reason
                )
                
                if closed:
                    logger.info(f"📉 Position closed: {ticker} - "
                              f"P&L: ${closed.unrealized_pnl:.2f} ({closed.unrealized_pnl_pct:+.2f}%)")
                    
                    # Send alert
                    if self.alert_system:
                        if reason in ['stop_loss', 'stop_hit']:
                            self.alert_system.alert_stop_hit(
                                ticker=ticker,
                                price=order.filled_price,
                                loss=closed.unrealized_pnl
                            )
                        elif reason in ['take_profit', 'target_hit']:
                            self.alert_system.alert_target_hit(
                                ticker=ticker,
                                price=order.filled_price,
                                profit=closed.unrealized_pnl
                            )
                        else:
                            self.alert_system.alert_position_closed(
                                ticker=ticker,
                                pnl=closed.unrealized_pnl,
                                pnl_pct=closed.unrealized_pnl_pct,
                                reason=reason
                            )
                    
                    return {
                        'success': True,
                        'ticker': ticker,
                        'exit_price': order.filled_price,
                        'pnl': closed.unrealized_pnl,
                        'pnl_pct': closed.unrealized_pnl_pct,
                        'reason': reason
                    }
                else:
                    return {'success': False, 'reason': 'Position close failed'}
            else:
                logger.error(f"Failed to submit exit order for {ticker}")
                return {'success': False, 'reason': 'Order submission failed'}
                
        except Exception as e:
            logger.error(f"Error executing exit for {ticker}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def close_all_positions(self, reason: str = 'manual') -> Dict:
        """
        Close all open positions
        
        Args:
            reason: Reason for closing
            
        Returns:
            Dictionary with results
        """
        positions = self.position_manager.get_all_positions()
        
        if not positions:
            return {
                'success': True,
                'positions_closed': 0,
                'message': 'No open positions'
            }
        
        logger.info(f"Closing all {len(positions)} positions - reason: {reason}")
        
        closed_count = 0
        for position in positions:
            result = self.execute_exit(position.ticker, reason)
            if result['success']:
                closed_count += 1
        
        return {
            'success': True,
            'positions_closed': closed_count,
            'total_positions': len(positions)
        }
    
    def update_risk_metrics(self):
        """Update risk monitor with current capital"""
        try:
            # Calculate current capital from positions
            pnl = self.position_manager.calculate_portfolio_pnl()
            current_capital = self.risk_monitor.daily_start_capital + pnl['total_pnl']
            
            self.risk_monitor.update_capital(current_capital)
            
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")
    
    def run_trading_cycle(self, tickers: List[str]) -> Dict:
        """
        Run complete trading cycle: signals -> entries -> monitoring -> exits
        
        Args:
            tickers: List of tickers to scan
            
        Returns:
            Dictionary with cycle results
        """
        if self.state != ExecutorState.RUNNING:
            return {'success': False, 'reason': f'Executor state: {self.state.value}'}
        
        logger.info("=" * 70)
        logger.info("Running Trading Cycle")
        logger.info("=" * 70)
        
        results = {
            'timestamp': datetime.now(pytz.timezone('America/New_York')).isoformat(),
            'state': self.state.value
        }
        
        try:
            # Step 1: Monitor existing positions
            logger.info("Step 1: Monitor positions...")
            monitor_result = self.monitor_positions()
            results['monitoring'] = monitor_result
            
            # Step 2: Update risk metrics
            logger.info("Step 2: Update risk metrics...")
            self.update_risk_metrics()
            risk_metrics = self.risk_monitor.get_risk_metrics()
            results['risk'] = {
                'daily_pnl': risk_metrics['capital']['daily_pnl'],
                'daily_pnl_pct': risk_metrics['capital']['daily_pnl_pct'],
                'trading_halted': risk_metrics['trading_state']['halted']
            }
            
            # Step 3: Process new signals (if not halted)
            if not self.risk_monitor.trading_halted:
                logger.info("Step 3: Process signals...")
                signal_result = self.process_signals(tickers)
                results['signals'] = signal_result
            else:
                logger.warning("Skipping signal processing - trading halted")
                results['signals'] = {'skipped': True, 'reason': 'Trading halted'}
            
            # Step 4: Check limit/stop orders
            logger.info("Step 4: Check pending orders...")
            self.order_manager.check_limit_orders()
            self.order_manager.check_stop_orders()
            
            results['success'] = True
            
            logger.info("Trading cycle complete")
            logger.info("=" * 70)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
            self.state = ExecutorState.ERROR
            self.error_message = str(e)
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> Dict:
        """
        Get executor status
        
        Returns:
            Dictionary with current status
        """
        status = {
            'state': self.state.value,
            'error_message': self.error_message,
            'statistics': {
                'signals_processed': self.signals_processed,
                'trades_executed': self.trades_executed,
                'trades_rejected': self.trades_rejected
            }
        }
        
        # Add component status
        if self.position_manager:
            positions = self.position_manager.get_all_positions()
            status['positions'] = {
                'active': len(positions),
                'tickers': [p.ticker for p in positions]
            }
        
        if self.risk_monitor:
            status['risk'] = {
                'trading_halted': self.risk_monitor.trading_halted,
                'daily_pnl': self.risk_monitor.daily_pnl
            }
        
        if self.order_manager:
            status['orders'] = {
                'pending': len(self.order_manager.get_pending_orders()),
                'filled': len(self.order_manager.get_filled_orders())
            }
        
        return status
    
    def get_statistics(self) -> Dict:
        """
        Get comprehensive statistics
        
        Returns:
            Dictionary with stats from all components
        """
        stats = {
            'executor': {
                'state': self.state.value,
                'signals_processed': self.signals_processed,
                'trades_executed': self.trades_executed,
                'trades_rejected': self.trades_rejected,
                'success_rate': (self.trades_executed / (self.trades_executed + self.trades_rejected) * 100) 
                               if (self.trades_executed + self.trades_rejected) > 0 else 0
            }
        }
        
        # Add component stats
        if self.position_manager:
            stats['positions'] = self.position_manager.get_statistics()
        
        if self.risk_monitor:
            stats['risk'] = self.risk_monitor.get_statistics()
        
        if self.order_manager:
            stats['orders'] = self.order_manager.get_statistics()
        
        return stats
    
    def __repr__(self) -> str:
        return (f"TradeExecutor(state={self.state.value}, "
                f"executed={self.trades_executed}, "
                f"rejected={self.trades_rejected})")
