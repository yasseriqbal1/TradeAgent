"""
Trading Dashboard - Flask Backend
Read-only access to trading database
Runs independently of trading bot
"""

from flask import Flask, render_template, jsonify
import psycopg2
from datetime import datetime, date
import os
from dotenv import load_dotenv
import redis
import json

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)

# Redis connection for live prices
def get_redis_connection():
    try:
        return redis.Redis(host='localhost', port=6379, decode_responses=True)
    except:
        return None

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'tradeagent'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'yasser')
    )

@app.route('/')
def index():
    """Render main dashboard page"""
    return render_template('index.html')

@app.route('/api/summary')
def get_summary():
    """Get today's trading summary"""
    try:
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
        first_trade = result[6]
        last_trade = result[7]
        
        win_rate = (wins / sells * 100) if sells > 0 else 0
        
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
        
        # Calculate total equity (you may need to adjust this based on your starting capital)
        # For now, using a placeholder - you can make this dynamic
        starting_capital = 96.36  # Get this from your config or first trade
        current_equity = starting_capital + total_pnl + unrealized_pnl
        
        conn.close()
        
        return jsonify({
            'total_trades': total_trades,
            'buys': buys,
            'sells': sells,
            'wins': wins,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(total_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'net_pnl': round(total_pnl + unrealized_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'current_equity': round(current_equity, 2),
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
    """Check if bot is running by looking at recent log activity"""
    try:
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
            data = r.get('live_prices')
            if data:
                parsed = json.loads(data)
                prices_dict = parsed.get('prices', {})
                
                # Format for frontend
                prices = []
                for ticker, price in prices_dict.items():
                    prices.append({
                        'ticker': ticker,
                        'price': round(price, 2),
                        'change_pct': 0  # Calculate if needed
                    })
                return jsonify(prices)
        
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
        
        return jsonify(prices)
    except Exception as e:
        print(f"Live prices error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 200

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 TRADING DASHBOARD STARTING")
    print("="*80)
    print(f"📊 Dashboard URL: http://localhost:5000")
    print(f"🔄 Auto-refresh: Every 15 seconds")
    print(f"📖 Read-only mode: Safe to run alongside trading bot")
    print(f"⏹️  Press Ctrl+C to stop")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
