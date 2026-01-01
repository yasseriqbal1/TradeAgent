"""
Bulk Historical Data Downloader
Downloads 5 years of historical data for multiple tickers using yfinance.
Much faster than manual downloads from NASDAQ.com!
"""
from datetime import datetime, timedelta
from quant_agent.historical_data import HistoricalDataManager
import pandas as pd

def download_bulk_data(tickers, years=5, save_to_csv=True):
    """
    Download historical data for multiple tickers.
    
    Args:
        tickers: List of ticker symbols
        years: Number of years of history to download (default: 5)
        save_to_csv: Save individual CSV files for each ticker
    """
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years*365)
    
    print("=" * 70)
    print("Bulk Historical Data Download")
    print("=" * 70)
    print(f"\nTickers: {', '.join(tickers)}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Period: {years} years")
    print(f"Data source: yfinance (free, unlimited)")
    
    # Initialize data manager
    print("\nInitializing data manager...")
    data_manager = HistoricalDataManager()
    
    # Download data
    print(f"\nDownloading data for {len(tickers)} tickers...")
    print("This may take a minute...\n")
    
    historical_data = data_manager.download_historical_data(
        tickers=tickers,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        force_refresh=True  # Use yfinance, not Questrade
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("Download Summary")
    print("=" * 70)
    
    successful = []
    failed = []
    
    for ticker in tickers:
        if ticker in historical_data and len(historical_data[ticker]) > 0:
            df = historical_data[ticker]
            successful.append(ticker)
            
            print(f"\n✅ {ticker}:")
            print(f"   Rows: {len(df):,}")
            print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
            print(f"   Columns: {', '.join(df.columns)}")
            
            # Save to CSV if requested
            if save_to_csv:
                filename = f"historical_data_{ticker}_{years}yr.csv"
                df.to_csv(filename)
                print(f"   Saved: {filename}")
        else:
            failed.append(ticker)
            print(f"\n❌ {ticker}: Download failed")
    
    print("\n" + "=" * 70)
    print(f"✅ Successful: {len(successful)}/{len(tickers)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
    
    return historical_data


def import_nasdaq_csv(csv_file, ticker):
    """
    Import manually downloaded NASDAQ CSV file.
    Converts NASDAQ format to standard format.
    
    Args:
        csv_file: Path to NASDAQ CSV file
        ticker: Ticker symbol
    
    Returns:
        DataFrame with standardized columns
    """
    print(f"\nImporting {csv_file}...")
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    # NASDAQ format: Date, Close/Last, Volume, Open, High, Low
    # Clean up column names
    df.columns = df.columns.str.strip()
    
    # Rename columns to standard format
    column_mapping = {
        'Date': 'Date',
        'Close/Last': 'Close',
        'Volume': 'Volume',
        'Open': 'Open',
        'High': 'High',
        'Low': 'Low'
    }
    df = df.rename(columns=column_mapping)
    
    # Remove $ signs from prices
    for col in ['Close', 'Open', 'High', 'Low']:
        if df[col].dtype == 'object':
            df[col] = df[col].str.replace('$', '').str.replace(',', '').astype(float)
    
    # Convert Volume to integer
    if df['Volume'].dtype == 'object':
        df['Volume'] = df['Volume'].str.replace(',', '').astype(int)
    
    # Convert date to datetime and set as index
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')
    
    # Sort by date (NASDAQ downloads are newest first)
    df = df.sort_index()
    
    # Reorder columns to match standard format
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    print(f"✅ Imported {len(df)} rows")
    print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    
    # Save in standardized format
    output_file = f"historical_data_{ticker}_5yr.csv"
    df.to_csv(output_file)
    print(f"   Saved: {output_file}")
    
    return df


if __name__ == "__main__":
    # Example 1: Bulk download (RECOMMENDED)
    print("=" * 70)
    print("OPTION 1: Automated Bulk Download (RECOMMENDED)")
    print("=" * 70)
    
    # Your tickers - add as many as you want!
    tickers = [
        'PLTR',  # Palantir (you already downloaded this manually)
        'MU',    # Micron
        'NVDA',  # NVIDIA
        'AMD',   # AMD
        'AAPL',  # Apple
        'MSFT',  # Microsoft
        'GOOGL', # Google
        'TSLA',  # Tesla
        'META',  # Meta
        'AMZN',  # Amazon
    ]
    
    # Download all at once - much faster than manual!
    historical_data = download_bulk_data(tickers, years=5, save_to_csv=True)
    
    # Example 2: Import manually downloaded NASDAQ CSV (if you prefer)
    print("\n\n" + "=" * 70)
    print("OPTION 2: Import Manual NASDAQ Downloads")
    print("=" * 70)
    print("\nIf you already downloaded CSV files from NASDAQ.com:")
    print("  df = import_nasdaq_csv('PLTR_5yr.csv', 'PLTR')")
    print("\nBut automated download is faster and easier!")
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review the CSV files created")
    print("  2. Use them for backtesting")
    print("  3. Add more tickers to the list above and re-run")
