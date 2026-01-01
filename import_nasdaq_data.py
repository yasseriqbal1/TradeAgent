"""
Historical Data Downloader with Multiple Sources
- Option 1: Import manually downloaded NASDAQ CSV files
- Option 2: Download from yfinance (when it's working)
- Option 3: Download from Alpha Vantage (requires free API key)
"""
import pandas as pd
import os
from datetime import datetime

def import_nasdaq_csv(csv_file, ticker, save_standardized=True):
    """
    Import manually downloaded NASDAQ CSV file and convert to standard format.
    
    Args:
        csv_file: Path to NASDAQ CSV file (e.g., 'PLTR_5yr.csv')
        ticker: Ticker symbol (e.g., 'PLTR')
        save_standardized: Save in standardized format
    
    Returns:
        DataFrame with standardized columns (Open, High, Low, Close, Volume)
    """
    print(f"\n{'='*70}")
    print(f"Importing {ticker} from NASDAQ CSV")
    print('='*70)
    print(f"File: {csv_file}")
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return None
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    print(f"✅ File loaded: {len(df)} rows")
    print(f"   Original columns: {list(df.columns)}")
    
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
    
    # Remove $ signs from prices and convert to float
    for col in ['Close', 'Open', 'High', 'Low']:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.replace('$', '').str.replace(',', '').astype(float)
    
    # Convert Volume to integer
    if 'Volume' in df.columns:
        if df['Volume'].dtype == 'object':
            df['Volume'] = df['Volume'].str.replace(',', '').astype(int)
    
    # Convert date to datetime and set as index
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')
    
    # Sort by date (NASDAQ downloads are newest first)
    df = df.sort_index()
    
    # Reorder columns to match standard format
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    print(f"\n✅ Standardized format:")
    print(f"   Rows: {len(df):,}")
    print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"   Columns: {list(df.columns)}")
    
    # Show sample data
    print(f"\n📊 Sample data (last 5 days):")
    print(df.tail(5))
    
    # Show statistics
    print(f"\n📈 Statistics:")
    print(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    print(f"   Avg volume: {df['Volume'].mean():,.0f}")
    print(f"   Trading days: {len(df)}")
    
    # Save in standardized format
    if save_standardized:
        output_file = f"historical_data_{ticker}_nasdaq.csv"
        df.to_csv(output_file)
        print(f"\n💾 Saved standardized format: {output_file}")
    
    return df


def batch_import_nasdaq_csvs(csv_files_dict):
    """
    Import multiple NASDAQ CSV files at once.
    
    Args:
        csv_files_dict: Dictionary mapping ticker to CSV file path
                       e.g., {'PLTR': 'PLTR_5yr.csv', 'MU': 'MU_5yr.csv'}
    
    Returns:
        Dictionary mapping ticker to DataFrame
    """
    print("="*70)
    print("Batch Import from NASDAQ CSV Files")
    print("="*70)
    print(f"\nImporting {len(csv_files_dict)} tickers...")
    
    historical_data = {}
    successful = []
    failed = []
    
    for ticker, csv_file in csv_files_dict.items():
        try:
            df = import_nasdaq_csv(csv_file, ticker, save_standardized=True)
            if df is not None and len(df) > 0:
                historical_data[ticker] = df
                successful.append(ticker)
            else:
                failed.append(ticker)
        except Exception as e:
            print(f"\n❌ {ticker} failed: {e}")
            failed.append(ticker)
    
    # Summary
    print("\n" + "="*70)
    print("Import Summary")
    print("="*70)
    print(f"✅ Successful: {len(successful)}/{len(csv_files_dict)}")
    if successful:
        print(f"   Tickers: {', '.join(successful)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
    
    return historical_data


def create_combined_dataset(historical_data, output_file='combined_historical_data.csv'):
    """
    Combine multiple tickers into a single CSV file.
    Useful for backtesting across multiple stocks.
    
    Args:
        historical_data: Dictionary mapping ticker to DataFrame
        output_file: Output CSV file name
    """
    print(f"\n{'='*70}")
    print("Creating Combined Dataset")
    print('='*70)
    
    combined = []
    
    for ticker, df in historical_data.items():
        df_copy = df.copy()
        df_copy['Ticker'] = ticker
        df_copy = df_copy.reset_index()
        combined.append(df_copy)
    
    combined_df = pd.concat(combined, ignore_index=True)
    combined_df = combined_df.sort_values(['Date', 'Ticker'])
    
    combined_df.to_csv(output_file, index=False)
    
    print(f"✅ Combined dataset created:")
    print(f"   File: {output_file}")
    print(f"   Tickers: {combined_df['Ticker'].nunique()}")
    print(f"   Total rows: {len(combined_df):,}")
    print(f"   Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
    
    return combined_df


if __name__ == "__main__":
    print("="*70)
    print("Historical Data Import Tool")
    print("="*70)
    
    # OPTION 1: Single file import
    print("\n" + "="*70)
    print("OPTION 1: Single File Import")
    print("="*70)
    
    # If you have a NASDAQ CSV file, specify it here:
    csv_file = "PLTR_5yr.csv"  # Change this to your actual file name
    ticker = "PLTR"
    
    if os.path.exists(csv_file):
        df_pltr = import_nasdaq_csv(csv_file, ticker)
    else:
        print(f"\nℹ️  Example file '{csv_file}' not found.")
        print("   Download from: https://www.nasdaq.com/market-activity/stocks/pltr/historical")
        print("   Then update the 'csv_file' variable above and re-run.")
        df_pltr = None
    
    # OPTION 2: Batch import
    print("\n\n" + "="*70)
    print("OPTION 2: Batch Import Multiple Tickers")
    print("="*70)
    
    # Specify all your downloaded CSV files here:
    csv_files = {
        'PLTR': 'PLTR_5yr.csv',  # Update these with your actual file names
        'MU': 'MU_5yr.csv',
        # Add more tickers as you download them:
        # 'NVDA': 'NVDA_5yr.csv',
        # 'AMD': 'AMD_5yr.csv',
        # 'AAPL': 'AAPL_5yr.csv',
    }
    
    # Only import files that exist
    existing_files = {ticker: file for ticker, file in csv_files.items() if os.path.exists(file)}
    
    if existing_files:
        historical_data = batch_import_nasdaq_csvs(existing_files)
        
        # Create combined dataset
        if len(historical_data) > 1:
            combined_df = create_combined_dataset(historical_data)
    else:
        print("\nℹ️  No CSV files found.")
        print("\nTo use this tool:")
        print("  1. Go to NASDAQ.com for each ticker:")
        print("     https://www.nasdaq.com/market-activity/stocks/TICKER/historical")
        print("  2. Select '5 Years' timeline")
        print("  3. Click 'Download Data' button")
        print("  4. Save CSV files to this directory")
        print("  5. Update the 'csv_files' dictionary above")
        print("  6. Re-run this script")
        print("\nOR...")
        print("  Just save ONE file and import it individually!")
    
    print("\n" + "="*70)
    print("Done!")
    print("="*70)
    print("\nFiles created:")
    print("  - historical_data_TICKER_nasdaq.csv (for each ticker)")
    if existing_files and len(existing_files) > 1:
        print("  - combined_historical_data.csv (all tickers combined)")
    
    print("\n💡 Tip: Once you have standardized CSV files, you can use them")
    print("   directly with your backtesting system!")
