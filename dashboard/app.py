"""
Trading Dashboard - Flask Backend
Read-only access to trading database
Runs independently of trading bot
"""

from flask import Flask, render_template, jsonify
import psycopg2
from datetime import datetime, date, time
import os
from dotenv import load_dotenv
try:
    import redis  # type: ignore
except Exception:
    redis = None
import json

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from dip_suggestions import compute_dip_suggestions
from critical_monitor import build_critical_monitor_payload

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)

# Redis connection for live prices
def get_redis_connection():
    try:
        if redis is None:
            return None
        r = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=int(os.getenv('REDIS_PORT', '6379')), decode_responses=True)
        # Fail fast if the server is unreachable so callers can fall back cleanly
        r.ping()
        return r
    except Exception:
        return None

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'tradeagent'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )

def get_bot_status_from_redis():
    """Fetch bot_status JSON from Redis if available."""
    try:
        r = get_redis_connection()
        if not r:
            return None
        # Prefer v2 payload when present (avoids legacy bot processes publishing older schemas)
        data = r.get('bot_status_v2') or r.get('bot_status')
        if not data:
            return None
        return json.loads(data)
    except Exception:
        return None


def get_now_eastern() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("America/New_York"))


def is_us_market_open(now_et: datetime) -> bool:
    """Best-effort regular session check (no holiday calendar)."""
    if now_et.weekday() >= 5:
        return False
    session_open = time(9, 30)
    session_close = time(16, 0)
    return session_open <= now_et.time() < session_close


def get_live_prices_from_redis_raw(r):
    """Return (parsed_payload, reason) from Redis live_prices key."""
    if not r:
        return None, "redis_unavailable"
    try:
        raw = r.get('live_prices')
    except Exception:
        raw = None
    if not raw:
        return None, "no_live_prices"
    try:
        parsed = json.loads(raw)
    except Exception:
        return None, "invalid_live_prices"
    if not isinstance(parsed, dict):
        return None, "invalid_live_prices"
    if not parsed.get('prices'):
        return None, "empty_live_prices"
    return parsed, None

@app.route('/')
def index():
    """Render main dashboard page"""
    return render_template('index.html')

@app.route('/api/summary')
def get_summary():
    """Get today's trading summary"""
    try:
        bot_status = get_bot_status_from_redis()
        paper_capital_source = os.getenv('PAPER_CAPITAL_SOURCE', 'db').strip().lower()
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get today's trades
        cur.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN action='BUY' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) as sells,
                SUM(CASE WHEN action='SELL' AND pnl > 0 THEN 1 ELSE 0 END) as wins,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(AVG(CASE WHEN action='SELL' THEN pnl END), 0) as avg_pnl,
                COALESCE(SUM(CASE WHEN action='SELL' AND pnl > 0 THEN pnl ELSE 0 END), 0) as gross_profit,
                COALESCE(ABS(SUM(CASE WHEN action='SELL' AND pnl < 0 THEN pnl ELSE 0 END)), 0) as gross_loss,
                COALESCE(AVG(CASE WHEN action='SELL' AND pnl > 0 THEN pnl END), 0) as avg_win,
                COALESCE(AVG(CASE WHEN action='SELL' AND pnl < 0 THEN pnl END), 0) as avg_loss,
                MIN(trade_date) as first_trade,
                MAX(trade_date) as last_trade
            FROM trades_history
            WHERE DATE(trade_date) = CURRENT_DATE
        """)
        
        result = cur.fetchone()
        total_trades = result[0] or 0
        buys = result[1] or 0
        sells = result[2] or 0
        wins = result[3] or 0
        total_pnl = float(result[4]) if result[4] else 0.0
        avg_pnl = float(result[5]) if result[5] else 0.0
        gross_profit = float(result[6]) if result[6] else 0.0
        gross_loss = float(result[7]) if result[7] else 0.0
        avg_win = float(result[8]) if result[8] else 0.0
        avg_loss = float(result[9]) if result[9] else 0.0
        first_trade = result[10]
        last_trade = result[11]
        
        win_rate = (wins / sells * 100) if sells > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
        
        cash_value = 0.0
        invested_value = 0.0
        trading_mode = None
        equity_source = None

        if bot_status:
            trading_mode = bot_status.get('mode')

            is_paper_mode = str(trading_mode or '').lower() == 'paper'

            unrealized_pnl = float(bot_status.get('unrealized_pnl', 0))
            realized_pnl = float(bot_status.get('realized_pnl', total_pnl))
            # Prefer broker (Questrade) balances when available
            broker_equity = bot_status.get('broker_equity')
            broker_cash = bot_status.get('broker_cash')

            # In paper mode, optionally display broker balances (for showing true account value).
            allow_broker_in_paper = is_paper_mode and paper_capital_source in ('broker', 'broker_cash', 'broker_equity')

            use_broker_equity = (allow_broker_in_paper or (not is_paper_mode)) and broker_equity is not None and float(broker_equity) > 0
            use_broker_cash = (allow_broker_in_paper or (not is_paper_mode)) and broker_cash is not None and float(broker_cash) >= 0

            equity_source = 'broker' if use_broker_equity else (bot_status.get('equity_source') or 'paper')

            if is_paper_mode and (not use_broker_equity) and bot_status.get('paper_equity') is not None:
                current_equity = float(bot_status.get('paper_equity', 0))
            else:
                current_equity = float(broker_equity) if use_broker_equity else float(bot_status.get('equity', 0))
            open_positions_count = int(bot_status.get('open_positions', 0))
            total_pnl = realized_pnl

            if is_paper_mode and (not use_broker_cash) and bot_status.get('paper_cash') is not None:
                cash_value = float(bot_status.get('paper_cash', 0))
            elif use_broker_cash:
                cash_value = float(broker_cash)
            elif bot_status.get('cash') is not None:
                cash_value = float(bot_status.get('cash', 0))

            # If we have broker equity/cash, derive invested as a residual.
            if use_broker_equity and cash_value != 0.0 and current_equity != 0.0:
                invested_value = max(current_equity - cash_value, 0.0)
            elif bot_status.get('invested_value') is not None:
                invested_value = float(bot_status.get('invested_value', 0))

            if invested_value == 0.0 and cash_value != 0.0 and current_equity != 0.0:
                invested_value = max(current_equity - cash_value, 0.0)
            if cash_value == 0.0 and invested_value != 0.0 and current_equity != 0.0:
                cash_value = max(current_equity - invested_value, 0.0)
        else:
            # Get open positions unrealized P&L
            cur.execute("""
                SELECT 
                    ticker,
                    quantity,
                    entry_price,
                    current_price,
                    unrealized_pnl
                FROM positions
                WHERE quantity > 0
            """)
            
            positions = cur.fetchall()
            unrealized_pnl = sum(float(pos[4]) if pos[4] else 0.0 for pos in positions)
            open_positions_count = len(positions)

            invested_value = sum(
                (float(pos[1]) if pos[1] else 0.0) * (float(pos[3]) if pos[3] else float(pos[2]))
                for pos in positions
            )

            # Use last known capital_after as a fallback equity base
            cur.execute("""
                SELECT capital_after
                FROM trades_history
                WHERE DATE(trade_date) = CURRENT_DATE
                ORDER BY trade_date DESC
                LIMIT 1
            """)
            cap_row = cur.fetchone()
            cash_estimate = float(cap_row[0]) if cap_row and cap_row[0] is not None else 0.0
            cash_value = cash_estimate
            current_equity = cash_estimate + invested_value

        exposure_pct = (invested_value / current_equity * 100) if current_equity > 0 else 0.0
        
        conn.close()
        
        return jsonify({
            'source': 'redis' if bot_status else 'db',
            'trading_mode': trading_mode,
            'equity_source': equity_source,
            'total_trades': total_trades,
            'buys': buys,
            'sells': sells,
            'wins': wins,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(total_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'net_pnl': round(total_pnl + unrealized_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor is not None else None,
            'avg_win': round(avg_win, 2),
            'avg_loss': round(abs(avg_loss), 2),
            'current_equity': round(current_equity, 2),
            'cash_value': round(cash_value, 2),
            'invested_value': round(invested_value, 2),
            'exposure_pct': round(exposure_pct, 1),
            'open_positions': open_positions_count,
            'first_trade': first_trade.strftime('%I:%M %p') if first_trade else None,
            'last_trade': last_trade.strftime('%I:%M %p') if last_trade else None,
            'last_update': datetime.now().strftime('%I:%M:%S %p')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions')
def get_positions():
    """Get current open positions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                ticker,
                quantity,
                entry_price,
                current_price,
                stop_loss,
                take_profit,
                unrealized_pnl,
                unrealized_pnl_pct,
                entry_date
            FROM positions
            WHERE quantity > 0
            ORDER BY entry_date DESC
        """)
        
        positions = []
        for row in cur.fetchall():
            # Calculate hold time
            entry_time = row[8]
            if entry_time:
                hold_duration = datetime.now() - entry_time
                hours = int(hold_duration.total_seconds() // 3600)
                minutes = int((hold_duration.total_seconds() % 3600) // 60)
                hold_time = f"{hours}h {minutes}m"
            else:
                hold_time = "N/A"
            
            positions.append({
                'ticker': row[0],
                'quantity': float(row[1]),
                'entry_price': float(row[2]),
                'current_price': float(row[3]) if row[3] else float(row[2]),
                'stop_loss': float(row[4]) if row[4] else None,
                'take_profit': float(row[5]) if row[5] else None,
                'unrealized_pnl': round(float(row[6]) if row[6] else 0.0, 2),
                'unrealized_pnl_pct': round(float(row[7]) if row[7] else 0.0, 2),
                'hold_time': hold_time,
                'entry_time': entry_time.strftime('%I:%M %p') if entry_time else 'N/A'
            })
        
        conn.close()
        return jsonify(positions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """Get today's trade history"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                trade_date,
                ticker,
                action,
                shares,
                price,
                pnl,
                pnl_pct,
                notes
            FROM trades_history
            WHERE DATE(trade_date) = CURRENT_DATE
            ORDER BY trade_date DESC
            LIMIT 50
        """)
        
        trades = []
        for row in cur.fetchall():
            trades.append({
                'time': row[0].strftime('%I:%M %p'),
                'ticker': row[1],
                'action': row[2],
                'shares': float(row[3]),
                'price': float(row[4]),
                'pnl': round(float(row[5]) if row[5] else 0.0, 2),
                'pnl_pct': round(float(row[6]) if row[6] else 0.0, 2),
                'notes': row[7] or ''
            })
        
        conn.close()
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def get_bot_status():
    """Prefer Redis bot_status heartbeat for true bot state; fall back to DB timestamps."""
    try:
        bot_status = get_bot_status_from_redis()
        if bot_status:
            ts = bot_status.get('timestamp')
            heartbeat_age_s = None
            is_running = False

            if ts:
                try:
                    # bot writes ISO timestamps; accept 'Z' suffix
                    parsed = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                    heartbeat_age_s = (datetime.now(parsed.tzinfo) - parsed).total_seconds()
                    is_running = heartbeat_age_s < 120
                except Exception:
                    heartbeat_age_s = None

            breakers = bot_status.get('breakers') or {}
            market_open = breakers.get('market_open')
            market_reason = breakers.get('market_reason')
            next_open = breakers.get('next_open')
            next_close = breakers.get('next_close')
            data_feed_ok = breakers.get('data_feed_ok')
            data_feed_reason = breakers.get('data_feed_reason')
            prices_from_cache = breakers.get('prices_from_cache')
            stale_position_quote_count = breakers.get('stale_position_quote_count')
            stale_position_quote_tickers = breakers.get('stale_position_quote_tickers')
            mode = bot_status.get('mode')

            if is_running and market_open is False:
                status = 'IDLE'
            elif is_running:
                status = 'LIVE'
            else:
                status = 'IDLE'

            return jsonify({
                'is_running': is_running,
                'status': status,
                'heartbeat_age_s': round(heartbeat_age_s, 1) if heartbeat_age_s is not None else None,
                'mode': mode,
                'market_open': market_open,
                'market_reason': market_reason,
                'next_open': next_open,
                'next_close': next_close,
                'data_feed_ok': data_feed_ok,
                'data_feed_reason': data_feed_reason,
                'prices_from_cache': prices_from_cache,
                'stale_position_quote_count': stale_position_quote_count,
                'stale_position_quote_tickers': stale_position_quote_tickers,
            })

        # Check if there are recent trades (within last 5 minutes)
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT MAX(trade_date)
            FROM trades_history
            WHERE DATE(trade_date) = CURRENT_DATE
        """)
        
        last_trade = cur.fetchone()[0]
        
        # Check positions table update time
        cur.execute("""
            SELECT MAX(updated_at)
            FROM positions
        """)
        
        last_update = cur.fetchone()[0]
        
        conn.close()
        
        # Determine if bot is likely running
        is_running = False
        if last_update:
            time_diff = (datetime.now() - last_update).total_seconds()
            is_running = time_diff < 120  # Active within last 2 minutes
        
        return jsonify({
            'is_running': is_running,
            'last_trade': last_trade.strftime('%I:%M %p') if last_trade else 'No trades today',
            'last_update': last_update.strftime('%I:%M:%S %p') if last_update else 'Unknown',
            'status': 'LIVE' if is_running else 'IDLE'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'is_running': False, 'status': 'ERROR'}), 500

@app.route('/api/live-prices')
def get_live_prices():
    """Get live stock prices from Redis (real-time from bot's Questrade feed)"""
    try:
        # Try Redis first (real-time prices from bot)
        r = get_redis_connection()
        if r:
            try:
                data = r.get('live_prices')
            except Exception:
                data = None
            if data:
                parsed = json.loads(data)
                prices_dict = parsed.get('prices', {})
                source = parsed.get('source', 'redis')
                ts = parsed.get('timestamp')

                # Compute % change vs previous snapshot, and cache the computed deltas so they don't
                # flicker to 0 on subsequent dashboard refreshes for the same timestamp.
                change_cache = None
                try:
                    change_cache_raw = r.get('live_prices_change_cache')
                    if change_cache_raw:
                        change_cache = json.loads(change_cache_raw)
                except Exception:
                    change_cache = None

                changes = {}
                if change_cache and change_cache.get('timestamp') == ts:
                    changes = change_cache.get('changes', {}) or {}
                else:
                    prev_prices = None
                    try:
                        prev_raw = r.get('live_prices_prev_snapshot')
                        if prev_raw:
                            prev_parsed = json.loads(prev_raw)
                            prev_prices = prev_parsed.get('prices') or {}
                    except Exception:
                        prev_prices = None

                    if isinstance(prev_prices, dict) and prev_prices:
                        for ticker, price in prices_dict.items():
                            try:
                                prev_price = float(prev_prices.get(ticker))
                                cur_price = float(price)
                                if prev_price and prev_price > 0:
                                    changes[ticker] = round(((cur_price - prev_price) / prev_price) * 100.0, 2)
                                else:
                                    changes[ticker] = 0.0
                            except Exception:
                                changes[ticker] = 0.0
                    else:
                        # First snapshot: no change baseline
                        changes = {ticker: 0.0 for ticker in prices_dict.keys()}

                    try:
                        r.setex('live_prices_prev_snapshot', 300, json.dumps({'timestamp': ts, 'prices': prices_dict}))
                        r.setex('live_prices_change_cache', 300, json.dumps({'timestamp': ts, 'changes': changes}))
                    except Exception:
                        pass
                
                # Format for frontend
                prices = []
                for ticker, price in prices_dict.items():
                    try:
                        price_value = float(price)
                    except Exception:
                        price_value = 0.0
                    prices.append({
                        'ticker': ticker,
                        'price': round(price_value, 2),
                        'change_pct': float(changes.get(ticker, 0.0))
                    })
                prices.sort(key=lambda x: x['ticker'])
                return jsonify({'source': source, 'prices': prices})
        
        # Fallback to database if Redis unavailable
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT ON (ticker)
                ticker,
                price,
                trade_date
            FROM trades_history
            WHERE DATE(trade_date) = CURRENT_DATE
            ORDER BY ticker, trade_date DESC
        """)
        
        prices = []
        for row in cur.fetchall():
            ticker = row[0]
            price = float(row[1])
            
            cur.execute("""
                SELECT price 
                FROM trades_history 
                WHERE ticker = %s AND DATE(trade_date) = CURRENT_DATE AND action = 'BUY'
                ORDER BY trade_date ASC 
                LIMIT 1
            """, (ticker,))
            
            entry_result = cur.fetchone()
            entry_price = float(entry_result[0]) if entry_result else price
            
            change_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            prices.append({
                'ticker': ticker,
                'price': round(price, 2),
                'change_pct': round(change_pct, 2)
            })
        
        cur.execute("""
            SELECT ticker, current_price, entry_price
            FROM positions
            WHERE quantity > 0
        """)
        
        for row in cur.fetchall():
            ticker = row[0]
            if any(p['ticker'] == ticker for p in prices):
                continue
                
            current = float(row[1]) if row[1] else float(row[2])
            entry = float(row[2])
            change_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            
            prices.append({
                'ticker': ticker,
                'price': round(current, 2),
                'change_pct': round(change_pct, 2)
            })
        
        conn.close()
        
        # Sort by ticker
        prices.sort(key=lambda x: x['ticker'])
        
        return jsonify({'source': 'db', 'prices': prices})
    except Exception as e:
        print(f"Live prices error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'source': 'error', 'prices': []}), 200


@app.route('/api/dip-suggestions')
def get_dip_suggestions():
    """Get lightweight dip suggestions computed from existing live prices."""
    try:
        now_et = get_now_eastern()
        require_market_open = os.getenv('DIP_SUGGEST_REQUIRE_MARKET_OPEN', 'true').lower() in ('1', 'true', 'yes')
        require_live_redis = os.getenv('DIP_SUGGEST_REQUIRE_LIVE_REDIS', 'true').lower() in ('1', 'true', 'yes')
        max_age_seconds = int(os.getenv('DIP_SUGGEST_MAX_AGE_SECONDS', '90') or '90')

        if require_market_open and not is_us_market_open(now_et):
            return jsonify({'enabled': False, 'generated_at': now_et.strftime('%I:%M:%S %p'), 'items': [], 'reason': 'market_closed'}), 200

        r = get_redis_connection()
        live_raw, reason = get_live_prices_from_redis_raw(r)
        if require_live_redis and not live_raw:
            return jsonify({'enabled': False, 'generated_at': now_et.strftime('%I:%M:%S %p'), 'items': [], 'reason': reason or 'no_live_data'}), 200

        prices_dict = (live_raw or {}).get('prices') or {}
        ts = (live_raw or {}).get('timestamp')
        if require_live_redis and ts:
            try:
                parsed_ts = datetime.fromisoformat(ts)
                age = (datetime.now() - parsed_ts).total_seconds()
                if age > max_age_seconds:
                    return jsonify({'enabled': False, 'generated_at': now_et.strftime('%I:%M:%S %p'), 'items': [], 'reason': 'stale_live_data'}), 200
            except Exception:
                pass

        # Convert into the same shape as /api/live-prices output.
        live_prices = []
        for ticker, price in prices_dict.items():
            try:
                price_value = float(price)
            except Exception:
                price_value = 0.0
            live_prices.append({'ticker': ticker, 'price': price_value, 'change_pct': 0.0})

        payload = compute_dip_suggestions(live_prices, redis_client=r, now=now_et)
        payload['enabled'] = True
        payload['price_source'] = (live_raw or {}).get('source', 'redis')
        return jsonify(payload)
    except Exception as e:
        return jsonify({'enabled': False, 'generated_at': get_now_eastern().strftime('%I:%M:%S %p'), 'items': [], 'error': str(e)}), 200


@app.route('/api/critical-monitor')
def get_critical_monitor():
    """Macro/context monitoring: VIX, WTI, and externally pushed critical alerts."""
    try:
        r = get_redis_connection()
        payload = build_critical_monitor_payload(redis_client=r, now=get_now_eastern())
        return jsonify(payload)
    except Exception as e:
        return jsonify({'generated_at': get_now_eastern().strftime('%I:%M:%S %p'), 'overall': 'unknown', 'indicators': [], 'alerts': [], 'error': str(e)}), 200

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 TRADING DASHBOARD STARTING")
    print("="*80)
    print(f"📊 Dashboard URL: http://localhost:5000")
    print(f"🔄 Auto-refresh: Every 15 seconds")
    print(f"📖 Read-only mode: Safe to run alongside trading bot")
    print(f"⏹️  Press Ctrl+C to stop")
    print("="*80 + "\n")
    
    port = int(os.getenv('DASHBOARD_PORT', '5000'))
    debug = os.getenv('DASHBOARD_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
