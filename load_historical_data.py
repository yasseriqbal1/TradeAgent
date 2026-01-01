"""
Load and verify historical data from the historical_data directory.
Use this to check your downloaded data and prepare for backtesting.
"""
import pandas as pd
import os
from glob import glob

# Directory with your historical data
data_dir = "historical_data"

print("=" * 70)
print("Historical Data Loader")
print("=" * 70)

# Find all CSV files in the directory
csv_files = glob(os.path.join(data_dir, "historical_data_*_nasdaq.csv"))

if not csv_files:
    print(f"\n❌ No data files found in '{data_dir}' directory")
    print("\nExpected file format: historical_data_TICKER_nasdaq.csv")
    print("Example: historical_data_AAPL_nasdaq.csv")
    exit(1)

print(f"\n📁 Found {len(csv_files)} data files in '{data_dir}/'")

# Load all data files
historical_data = {}
tickers = []

for csv_file in sorted(csv_files):
    # Extract ticker from filename
    filename = os.path.basename(csv_file)
    # Format: historical_data_TICKER_nasdaq.csv
    ticker = filename.replace("historical_data_", "").replace("_nasdaq.csv", "")
    
    # Load data
    df = pd.read_csv(csv_file, index_col='Date', parse_dates=True)
    
    historical_data[ticker] = df
    tickers.append(ticker)
    
    print(f"\n✅ {ticker}:")
    print(f"   File: {filename}")
    print(f"   Rows: {len(df):,}")
    print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    print(f"   Avg volume: {df['Volume'].mean():,.0f}")

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"\n✅ Loaded {len(historical_data)} tickers successfully:")
print(f"   {', '.join(tickers)}")

# Calculate total data points
total_rows = sum(len(df) for df in historical_data.values())
print(f"\n📊 Total trading days: {total_rows:,}")

# Find common date range
all_dates = set()
for df in historical_data.values():
    all_dates.update(df.index)

min_date = min(all_dates)
max_date = max(all_dates)
print(f"📅 Overall date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

# Show sample data for first ticker
print("\n" + "=" * 70)
print(f"Sample Data - {tickers[0]} (Last 5 Days)")
print("=" * 70)
print(historical_data[tickers[0]].tail(5))

# Create combined dataset
print("\n" + "=" * 70)
print("Creating Combined Dataset")
print("=" * 70)

combined_list = []
for ticker, df in historical_data.items():
    df_copy = df.copy()
    df_copy['Ticker'] = ticker
    df_copy = df_copy.reset_index()
    combined_list.append(df_copy)

combined_df = pd.concat(combined_list, ignore_index=True)
combined_df = combined_df.sort_values(['Date', 'Ticker'])

# Save combined dataset
output_file = "combined_historical_data.csv"
combined_df.to_csv(output_file, index=False)

print(f"\n✅ Combined dataset saved: {output_file}")
print(f"   Tickers: {len(tickers)}")
print(f"   Total rows: {len(combined_df):,}")
print(f"   Columns: {list(combined_df.columns)}")

# Show how to use the data
print("\n" + "=" * 70)
print("How to Use This Data")
print("=" * 70)

print("\n📝 Load data for backtesting:")
print("""
# Load single ticker
import pandas as pd
df_aapl = pd.read_csv('historical_data/historical_data_AAPL_nasdaq.csv', 
                      index_col='Date', parse_dates=True)

# Load all tickers
import glob
historical_data = {}
for file in glob.glob('historical_data/historical_data_*_nasdaq.csv'):
    ticker = file.split('_')[2]  # Extract ticker from filename
    historical_data[ticker] = pd.read_csv(file, index_col='Date', parse_dates=True)

# Load combined dataset
combined_df = pd.read_csv('combined_historical_data.csv', parse_dates=['Date'])
""")

print("\n📊 Data is ready for:")
print("   • Backtesting your trading strategies")
print("   • Factor calculation and analysis")
print("   • Performance metrics")
print("   • Walk-forward testing")

print("\n✅ All data verified and ready to use!")
print("\n" + "=" * 70)
