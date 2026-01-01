# Historical Data Download Guide

## Quick Answer: **Manual Download is Fine!**

You don't need to download programmatically. Manual downloads from NASDAQ.com work great.

---

## Option 1: Manual Download (RECOMMENDED for now)

### Why Manual?

- ✅ Reliable (no API issues)
- ✅ Fast for small number of tickers
- ✅ Free and unlimited
- ✅ Simple - just click download

### How to Download:

1. **Go to NASDAQ page for each ticker:**

   ```
   https://www.nasdaq.com/market-activity/stocks/TICKER/historical
   ```

   Replace `TICKER` with your stock (PLTR, MU, NVDA, etc.)

2. **Set timeline to "5 Years"** (or whatever you need)

3. **Click "Download Data"** button

4. **Save CSV file** to your TradeAgent directory

5. **Repeat for each ticker** you want

### Import Your Downloads:

Once you have CSV files, run:

```bash
python import_nasdaq_data.py
```

This will:

- Clean up the NASDAQ format (remove $ signs, fix dates)
- Convert to standard format (Open, High, Low, Close, Volume)
- Save as `historical_data_TICKER_nasdaq.csv`
- Create `combined_historical_data.csv` if you have multiple tickers

---

## Option 2: Automated Download (When APIs Work)

We tried yfinance but it's having issues right now. You can try again later:

```bash
python test_data_download.py
```

If it works, you can bulk download:

```bash
python download_historical_data.py
```

---

## Data Format

### NASDAQ Download Format:

```csv
Date,Close/Last,Volume,Open,High,Low
01/05/2021,$24.60,29050440,$23.18,$24.67,$22.89
```

### After Import (Standard Format):

```csv
Date,Open,High,Low,Close,Volume
2021-01-05,23.18,24.67,22.89,24.60,29050440
```

Changes made:

- ✅ Removed $ signs from prices
- ✅ Converted date format to YYYY-MM-DD
- ✅ Sorted chronologically (oldest to newest)
- ✅ Removed commas from volume
- ✅ Standardized column names

---

## How Many Tickers to Download?

For backtesting, you probably want **20-50 tickers** to have a good sample size.

### Suggested Universe:

**Tech Leaders (10):**

- NVDA, AMD, INTC, AVGO, QCOM, MU, AMAT, LRCX, KLAC, TSM

**Mega Caps (10):**

- AAPL, MSFT, GOOGL, AMZN, META, TSLA, NFLX, V, MA, COST

**Growth Stocks (10):**

- PLTR, SNOW, CRWD, ZS, NET, DDOG, MDB, SHOP, SQ, COIN

**Financials (10):**

- JPM, BAC, GS, MS, WFC, C, AXP, BLK, SCHW, USB

**Other (10):**

- DIS, NKE, SBUX, HD, LOW, TGT, WMT, UNH, JNJ, PG

Total: **50 tickers**

---

## Manual Download is Better When:

✅ You need < 50 tickers  
✅ You want reliable data  
✅ APIs are having issues  
✅ You only need to do it once

**Time estimate:** 2-3 minutes per ticker = 100-150 minutes for 50 tickers

---

## Automated Download is Better When:

✅ You need > 100 tickers  
✅ You need frequent updates  
✅ APIs are working properly  
✅ You're testing many different universes

---

## Your Next Steps:

1. **Download 5-10 tickers manually** from NASDAQ.com

   - Start with tickers you want to trade
   - Save CSV files to TradeAgent directory

2. **Run import script:**

   ```bash
   python import_nasdaq_data.py
   ```

3. **Verify data looks good:**

   - Check the `historical_data_TICKER_nasdaq.csv` files
   - Make sure dates and prices look correct

4. **Use for backtesting:**
   - You now have clean, standardized data
   - Ready to use with your backtesting system

---

## Files Created:

After importing, you'll have:

- `historical_data_PLTR_nasdaq.csv` - Standardized PLTR data
- `historical_data_MU_nasdaq.csv` - Standardized MU data
- (one file per ticker)
- `combined_historical_data.csv` - All tickers in one file

---

## Pro Tip:

**Don't overthink this!** Just download 5-10 tickers manually and start backtesting. You can always add more later.

Manual download is perfectly fine for 50-100 tickers. It's only when you need hundreds or thousands that automation becomes necessary.

---

## Questions?

**Q: How long does manual download take?**  
A: About 2-3 minutes per ticker (click, wait, save)

**Q: Is there a limit?**  
A: No limit on NASDAQ.com downloads

**Q: What if I need more than 5 years?**  
A: NASDAQ.com offers "10 Years" and "MAX" options

**Q: Can I automate this later?**  
A: Yes, once APIs are working properly

**Q: What format should I save?**  
A: Save as CSV (default from NASDAQ.com)

---

## Bottom Line:

**Just manually download 5-10 tickers from NASDAQ.com and use `import_nasdaq_data.py` to clean them up.**

It's simple, reliable, and takes 15-30 minutes total. Perfect for getting started!
