"""
Clean up NASDAQ CSV files - standardize column names and format.
Converts NASDAQ format to standard OHLCV format.
"""
import pandas as pd
import os
from glob import glob

data_dir = "historical_data"

print("=" * 70)
print("Clean and Standardize Historical Data")
print("=" * 70)

# Find all CSV files
csv_files = glob(os.path.join(data_dir, "historical_data_*_nasdaq.csv"))

print(f"\n📁 Found {len(csv_files)} files to clean")

cleaned_count = 0
failed_count = 0

for csv_file in sorted(csv_files):
    filename = os.path.basename(csv_file)
    ticker = filename.replace("historical_data_", "").replace("_nasdaq.csv", "")
    
    try:
        print(f"\n🔧 Processing {ticker}...")
        
        # Read CSV
        df = pd.read_csv(csv_file)
        
        # Show original format
        print(f"   Original columns: {list(df.columns)}")
        
        # Clean column names
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
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].str.replace('$', '').str.replace(',', '').astype(float)
        
        # Convert Volume to integer
        if 'Volume' in df.columns and df['Volume'].dtype == 'object':
            df['Volume'] = df['Volume'].str.replace(',', '').astype(int)
        
        # Convert date to datetime
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Sort by date (NASDAQ downloads are newest first, we want oldest first)
        df = df.sort_values('Date')
        
        # Set date as index
        df = df.set_index('Date')
        
        # Reorder columns to standard OHLCV format
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Save cleaned file
        df.to_csv(csv_file)
        
        print(f"   ✅ Cleaned: {len(df)} rows")
        print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"   New columns: {list(df.columns)}")
        print(f"   Sample prices: ${df['Close'].iloc[0]:.2f} to ${df['Close'].iloc[-1]:.2f}")
        
        cleaned_count += 1
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        failed_count += 1

# Summary
print("\n" + "=" * 70)
print("Cleanup Summary")
print("=" * 70)
print(f"\n✅ Cleaned: {cleaned_count}/{len(csv_files)} files")
if failed_count > 0:
    print(f"❌ Failed: {failed_count} files")

# Now reload and create combined dataset
print("\n" + "=" * 70)
print("Creating Combined Dataset")
print("=" * 70)

historical_data = {}
tickers = []

for csv_file in sorted(csv_files):
    filename = os.path.basename(csv_file)
    ticker = filename.replace("historical_data_", "").replace("_nasdaq.csv", "")
    
    try:
        df = pd.read_csv(csv_file, index_col='Date', parse_dates=True)
        historical_data[ticker] = df
        tickers.append(ticker)
    except:
        pass

print(f"\n✅ Loaded {len(tickers)} tickers:")
print(f"   {', '.join(sorted(tickers))}")

# Show sample
if tickers:
    print(f"\n📊 Sample - {tickers[0]} (last 5 days):")
    print(historical_data[tickers[0]].tail(5))

# Create combined dataset
combined_list = []
for ticker, df in historical_data.items():
    df_copy = df.copy()
    df_copy['Ticker'] = ticker
    df_copy = df_copy.reset_index()
    combined_list.append(df_copy)

combined_df = pd.concat(combined_list, ignore_index=True)
combined_df = combined_df.sort_values(['Date', 'Ticker'])

output_file = "combined_historical_data.csv"
combined_df.to_csv(output_file, index=False)

print(f"\n✅ Combined dataset: {output_file}")
print(f"   Tickers: {len(tickers)}")
print(f"   Total rows: {len(combined_df):,}")

# Statistics
print("\n" + "=" * 70)
print("Data Statistics")
print("=" * 70)

for ticker in sorted(tickers):
    df = historical_data[ticker]
    print(f"\n{ticker}:")
    print(f"  Trading days: {len(df)}")
    print(f"  Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Price: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    print(f"  Avg volume: {df['Volume'].mean():,.0f}")

print("\n✅ All data cleaned and ready for backtesting!")
print("=" * 70)
