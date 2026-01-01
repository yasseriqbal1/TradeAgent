import pandas as pd
import datetime

symbol = "AAPL.US"  # append .US for US stocks
url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"

df = pd.read_csv(url, parse_dates=["Date"])
df = df.set_index("Date")

# filter last 2 years
end = pd.Timestamp.today()
start = end - pd.Timedelta(days=2*365)
df = df.loc[start:end]

print(df.head())
print(df.tail())
