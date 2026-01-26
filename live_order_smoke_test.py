"""\
Questrade Live Order Smoke Test

Purpose:
- Place a *single* small live order to verify end-to-end order permissions.
- Optionally auto-cancel if not filled quickly.
- Optionally auto-flatten (sell) if buy fills.

Safety:
- Requires explicit env confirmation to run.
- Defaults to 1 share and tight caps.

Env vars:
- LIVE_TEST_CONFIRM: must equal "I_UNDERSTAND_LIVE_TRADING"
- LIVE_TEST_TICKER: default "AAPL"
- LIVE_TEST_QTY: default "1"
- LIVE_TEST_MAX_NOTIONAL_USD: default "25"
- LIVE_TEST_LIMIT_BUFFER_BPS: default "5" (buy: ask*(1+buffer), sell: bid*(1-buffer))
- LIVE_TEST_FILL_TIMEOUT_SECONDS: default "15"
- LIVE_TEST_CANCEL_IF_NOT_FILLED: default "1"
- LIVE_TEST_AUTO_FLATTEN: default "1" (if buy fills, submit sell to close)

You must set QUESTRADE_REFRESH_TOKEN in .env.
"""

import os
import time
from dotenv import load_dotenv
import requests

from quant_agent.questrade_loader import QuestradeAPI


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def main() -> int:
    load_dotenv()

    confirm = os.getenv("LIVE_TEST_CONFIRM", "")
    if confirm != "I_UNDERSTAND_LIVE_TRADING":
        print("REFUSING TO RUN: set LIVE_TEST_CONFIRM=I_UNDERSTAND_LIVE_TRADING")
        return 2

    ticker = os.getenv("LIVE_TEST_TICKER", "AAPL").strip().upper()
    qty = float(os.getenv("LIVE_TEST_QTY", "1"))
    max_notional = float(os.getenv("LIVE_TEST_MAX_NOTIONAL_USD", "25"))
    buffer_bps = float(os.getenv("LIVE_TEST_LIMIT_BUFFER_BPS", "5"))
    fill_timeout = int(os.getenv("LIVE_TEST_FILL_TIMEOUT_SECONDS", "15"))
    cancel_if_not_filled = _env_bool("LIVE_TEST_CANCEL_IF_NOT_FILLED", "1")
    auto_flatten = _env_bool("LIVE_TEST_AUTO_FLATTEN", "1")

    api = QuestradeAPI()

    # Safety: refuse to place "live" orders if we authenticated into the practice API server.
    # Practice servers typically contain '.iq.' in the hostname.
    allow_practice = _env_bool("LIVE_TEST_ALLOW_PRACTICE", "0")
    if api.api_server and ".iq." in str(api.api_server).lower() and not allow_practice:
        print(f"REFUSING: authenticated to practice server {api.api_server}")
        print("- To test true live trading, generate a LIVE refresh token (api_server should not include '.iq.').")
        print("- If you intentionally want to test practice order placement, set LIVE_TEST_ALLOW_PRACTICE=1")
        return 2
    accounts = api.get_accounts()
    if not accounts:
        print("No accounts returned by Questrade")
        return 3

    account_number = str(accounts[0].get("number") or accounts[0].get("accountNumber") or "")
    if not account_number:
        print(f"Could not determine account number from: {accounts[0]}")
        return 3

    symbol_id = api.search_symbols(ticker)
    if not symbol_id:
        print(f"Could not resolve symbolId for {ticker}")
        return 4

    quotes = api.get_quotes([int(symbol_id)])
    if not quotes:
        print(f"No quote returned for {ticker}")
        return 5

    q = quotes[0]
    ask = float(q.get("askPrice") or 0) or float(q.get("lastTradePrice") or 0)
    bid = float(q.get("bidPrice") or 0) or float(q.get("lastTradePrice") or 0)
    last = float(q.get("lastTradePrice") or 0)

    if ask <= 0 or bid <= 0 or last <= 0:
        print(f"Invalid quote for {ticker}: bid={bid}, ask={ask}, last={last}")
        return 6

    # Simple safety cap
    est_notional = qty * ask
    if est_notional > max_notional:
        print(f"Refusing: est_notional ${est_notional:.2f} > max ${max_notional:.2f}")
        return 7

    buffer = buffer_bps / 10_000.0
    buy_limit = round(ask * (1.0 + buffer), 2)

    print("=" * 80)
    print("LIVE ORDER SMOKE TEST")
    print(f"Account: {account_number}")
    print(f"Ticker: {ticker} (symbolId={symbol_id})")
    print(f"Quote: bid={bid} ask={ask} last={last}")
    print(f"Submitting BUY {qty} LIMIT @ {buy_limit} (buffer {buffer_bps} bps)")
    print("=" * 80)

    try:
        resp = api.place_order(
            account_number=account_number,
            symbol_id=int(symbol_id),
            quantity=qty,
            action="Buy",
            order_type="Limit",
            limit_price=buy_limit,
            comment="live_order_smoke_test",
        )
    except requests.exceptions.HTTPError as e:
        resp_text = None
        resp_json = None
        try:
            resp_text = e.response.text if e.response is not None else None
            if resp_text:
                try:
                    import json as _json
                    resp_json = _json.loads(resp_text)
                except Exception:
                    resp_json = None
        except Exception:
            resp_text = None
        print(f"Order placement failed: {e}")
        if resp_text:
            print(f"Response body: {resp_text}")

        if isinstance(resp_json, dict) and resp_json.get("code") == 1016:
            print("\nNEXT STEP: Your OAuth token does not include the trading scope.")
            print("- Generate a new Questrade refresh token that has TRADE permissions enabled.")
            print("- After updating .env, re-run this smoke test.")
            print(f"- Current api_server is {api.api_server} (practice servers usually include '.iq.').")
            print("  For true live trading, your token should authenticate to a non-iq api_server.")

        return 9

    order_id = resp.get("orderId") or resp.get("id")
    if not order_id:
        print(f"Order response did not include orderId: {resp}")
        return 8

    print(f"Submitted orderId={order_id}")

    filled_qty = 0.0
    filled_price = None

    t0 = time.time()
    while time.time() - t0 < fill_timeout:
        try:
            od = api.get_order(account_number, int(order_id))
        except requests.exceptions.HTTPError as e:
            print(f"Order status check failed: {e}")
            return 10
        # best-effort field parsing
        status = str(od.get("status") or od.get("state") or "")
        filled_qty = float(od.get("filledQuantity") or od.get("filledQty") or 0)
        filled_price = od.get("avgExecPrice") or od.get("averageExecutionPrice") or od.get("filledPrice")
        print(f"Status={status} filled={filled_qty} avg={filled_price}")
        if filled_qty and filled_qty > 0:
            break
        time.sleep(2)

    if (not filled_qty or filled_qty <= 0) and cancel_if_not_filled:
        print("Not filled in time; cancelling...")
        try:
            api.cancel_order(account_number, int(order_id))
            print("Cancel requested.")
        except requests.exceptions.HTTPError as e:
            print(f"Cancel failed: {e}")
        except Exception as e:
            print(f"Cancel failed: {e}")
        return 0

    if filled_qty and filled_qty > 0 and auto_flatten:
        # Submit a sell slightly below bid to encourage fill
        sell_limit = round(bid * (1.0 - buffer), 2)
        print(f"Auto-flatten: submitting SELL {filled_qty} LIMIT @ {sell_limit}")
        resp2 = api.place_order(
            account_number=account_number,
            symbol_id=int(symbol_id),
            quantity=filled_qty,
            action="Sell",
            order_type="Limit",
            limit_price=sell_limit,
            comment=f"live_order_smoke_test_flatten_{order_id}",
        )
        print(f"Sell response: {resp2}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
