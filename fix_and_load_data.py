"""
Fix double .csv.csv extensions and load historical data.
"""
import pandas as pd
import os
from glob import glob

data_dir = "historical_data"

print("=" * 70)
print("Fix File Extensions and Load Data")
print("=" * 70)

# Find files with double .csv.csv extension
double_ext_files = glob(os.path.join(data_dir, "*.csv.csv"))

if double_ext_files:
    print(f"\n📁 Found {len(double_ext_files)} files with double .csv.csv extension")
    print("\n🔧 Fixing file extensions...")
    
    for old_file in double_ext_files:
        new_file = old_file.replace(".csv.csv", ".csv")
        os.rename(old_file, new_file)
        print(f"   ✅ Renamed: {os.path.basename(old_file)} → {os.path.basename(new_file)}")
    
    print("\n✅ All file extensions fixed!")

# Now find all CSV files
csv_files = glob(os.path.join(data_dir, "historical_data_*_nasdaq.csv"))

print(f"\n📁 Loading {len(csv_files)} data files...")

# Load all data files
historical_data = {}
tickers = []

for csv_file in sorted(csv_files):
    filename = os.path.basename(csv_file)
    ticker = filename.replace("historical_data_", "").replace("_nasdaq.csv", "")
    
    try:
        df = pd.read_csv(csv_file, index_col='Date', parse_dates=True)
        
        historical_data[ticker] = df
        tickers.append(ticker)
        
        print(f"\n✅ {ticker}:")
        print(f"   Rows: {len(df):,}")
        print(f"   Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    except Exception as e:
        print(f"\n❌ {ticker}: Failed to load - {e}")

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"\n✅ Loaded {len(historical_data)} tickers:")
print(f"   {', '.join(sorted(tickers))}")

total_rows = sum(len(df) for df in historical_data.values())
print(f"\n📊 Total data points: {total_rows:,}")

# Find date range
all_dates = set()
for df in historical_data.values():
    all_dates.update(df.index)

if all_dates:
    min_date = min(all_dates)
    max_date = max(all_dates)
    print(f"📅 Date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

# Show sample data
if tickers:
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

output_file = "combined_historical_data.csv"
combined_df.to_csv(output_file, index=False)

print(f"\n✅ Combined dataset created: {output_file}")
print(f"   Tickers: {len(tickers)}")
print(f"   Total rows: {len(combined_df):,}")

# Quick example code
print("\n" + "=" * 70)
print("Quick Usage Example")
print("=" * 70)
print("""
# Load single ticker:
import pandas as pd
df = pd.read_csv('historical_data/historical_data_AAPL_nasdaq.csv', 
                 index_col='Date', parse_dates=True)
print(df.tail())

# Load all tickers at once:
from glob import glob
data = {}
for file in glob('historical_data/historical_data_*_nasdaq.csv'):
    ticker = file.split('_')[2]
    data[ticker] = pd.read_csv(file, index_col='Date', parse_dates=True)

# Load combined dataset:
combined = pd.read_csv('combined_historical_data.csv', parse_dates=['Date'])
print(combined[combined['Ticker'] == 'AAPL'].tail())
""")

print("\n✅ Your data is ready for backtesting!")
print("=" * 70)
