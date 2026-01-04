"""
Automated Historical Data Downloader using Stooq (FREE!)
Downloads 2 years of daily OHLCV data for all stocks in trading universe
Saves to historical_data/*.csv in clean format
"""
import pandas as pd
import time
from pathlib import Path
from datetime import datetime, timedelta

# Output directory
DATA_DIR = Path(__file__).parent / "historical_data"
DATA_DIR.mkdir(exist_ok=True)

# Trading Universe - MUST MATCH test_live_1hour_questrade.py
# (Expanded 55-Stock Universe - Diversified)
STOCK_UNIVERSE = [
    # Technology - FAANG + Cloud (13 stocks)
    'AAPL', 'AMD', 'CRWD', 'DDOG', 'GOOG', 'META', 'MSFT', 
    'MU', 'NET', 'NVDA', 'PLTR', 'SHOP', 'SNOW',
    
    # Quantum Computing (5 stocks)
    'IONQ', 'LAES', 'QBTS', 'QUBT', 'RGTI',
    
    # Semiconductors (5 stocks)
    'AVGO', 'QCOM', 'TXN', 'ADI', 'AMAT',
    
    # Cybersecurity + AI Infrastructure (5 stocks)
    'PANW', 'ZS', 'OKTA', 'MDB', 'S',
    
    # Healthcare - Pharma + Biotech (7 stocks)
    'ABBV', 'JNJ', 'UNH', 'PFE', 'LLY', 'MRNA', 'TMO',
    
    # Energy (5 stocks)
    'XOM', 'CVX', 'COP', 'EOG', 'SLB',
    
    # Industrials + Aerospace (5 stocks)
    'BA', 'CAT', 'GE', 'HON', 'RTX',
    
    # Consumer Discretionary (7 stocks)
    'AMZN', 'TSLA', 'HD', 'LOW', 'COST', 'TGT', 'NKE',
    
    # Consumer Staples + Entertainment (3 stocks)
    'WMT', 'DIS', 'SBUX',
]

def download_stock(ticker):
    """Download historical data for a single stock from Stooq"""
    try:
        print(f"📥 Downloading {ticker}...", end=" ")
        
        # Stooq requires .US suffix for US stocks
        symbol = f"{ticker}.US"
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        
        # Download data
        df = pd.read_csv(url, parse_dates=["Date"])
        
        # Check if we got valid data
        if df.empty or 'Date' not in df.columns:
            print(f"❌ No data returned")
            return False
        
        # Filter last 5 years
        end = pd.Timestamp.today()
        start = end - pd.Timedelta(days=5*365)
        df = df.set_index("Date")
        df = df.loc[start:end]
        
        # Check if we have enough data
        if len(df) < 200:
            print(f"⚠️  Only {len(df)} days (need 200+)")
            return False
        
        # Save to CSV (sorted by date, oldest first)
        df = df.sort_index()
        output_file = DATA_DIR / f"historical_data_{ticker}.csv"
        df.to_csv(output_file)
        
        print(f"✅ {len(df)} days saved")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:50]}")
        return False

def main():
    print("=" * 80)
    print("📊 AUTOMATED HISTORICAL DATA DOWNLOADER (STOOQ)")
    print("=" * 80)
    print(f"\n📂 Output Directory: {DATA_DIR}")
    print(f"📋 Stocks to Download: {len(STOCK_UNIVERSE)}")
    print(f"📅 Date Range: ~2 years of daily data")
    print(f"🌐 Source: Stooq.com (FREE)")
    print("\n" + "─" * 80 + "\n")
    
    successful = []
    failed = []
    
    for i, ticker in enumerate(STOCK_UNIVERSE, 1):
        print(f"[{i}/{len(STOCK_UNIVERSE)}] ", end="")
        
        if download_stock(ticker):
            successful.append(ticker)
        else:
            failed.append(ticker)
        
        # Be nice to the server - small delay between requests
        if i < len(STOCK_UNIVERSE):
            time.sleep(0.5)
    
    # Summary
    print("\n" + "─" * 80)
    print("\n📊 DOWNLOAD SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {len(successful)}/{len(STOCK_UNIVERSE)}")
    print(f"❌ Failed: {len(failed)}/{len(STOCK_UNIVERSE)}")
    
    if successful:
        print(f"\n✅ Successfully downloaded:")
        print(f"   {', '.join(successful)}")
    
    if failed:
        print(f"\n❌ Failed downloads:")
        print(f"   {', '.join(failed)}")
        print(f"\n💡 Tip: Failed stocks may not be available on Stooq or may have ticker issues")
    
    print("\n" + "=" * 80)
    print(f"✅ Done! All files saved to: {DATA_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
