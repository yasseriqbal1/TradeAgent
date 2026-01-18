/**
 * Trading Dashboard - Frontend JavaScript
 * Auto-refresh every 15 seconds
 * Handles all data fetching and UI updates
 */

// Refresh interval (15 seconds)
const REFRESH_INTERVAL = 15000;
let refreshTimer;

// Format currency
function formatCurrency(value) {
  const formatted = Math.abs(value).toFixed(2);
  return value >= 0 ? `$${formatted}` : `-$${formatted}`;
}

// Format percentage
function formatPercent(value) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

// Add animation class
function animateValue(element) {
  element.classList.add("value-update");
  setTimeout(() => element.classList.remove("value-update"), 500);
}

// Update summary data
async function updateSummary() {
  try {
    const response = await fetch("/api/summary");
    const data = await response.json();

    // Net P&L
    const netPnlEl = document.getElementById("netPnl");
    const netPnl = data.net_pnl;
    netPnlEl.textContent = formatCurrency(netPnl);
    netPnlEl.className = "metric-value";
    if (netPnl > 0) netPnlEl.classList.add("positive");
    else if (netPnl < 0) netPnlEl.classList.add("negative");
    animateValue(netPnlEl);

    // Realized/Unrealized
    document.getElementById("realizedPnl").textContent = formatCurrency(
      data.total_pnl
    );
    document.getElementById("unrealizedPnl").textContent = formatCurrency(
      data.unrealized_pnl
    );

    // Win Rate
    const winRateEl = document.getElementById("winRate");
    winRateEl.textContent = `${data.win_rate}%`;
    animateValue(winRateEl);

    document.getElementById("wins").textContent = data.wins;
    document.getElementById("sells").textContent = data.sells;

    // Current Equity
    const equityEl = document.getElementById("currentEquity");
    equityEl.textContent = formatCurrency(data.current_equity);
    animateValue(equityEl);

    document.getElementById("openPositions").textContent = data.open_positions;

    // Trades Today
    const tradesEl = document.getElementById("totalTrades");
    tradesEl.textContent = data.total_trades;
    animateValue(tradesEl);

    document.getElementById("buys").textContent = data.buys;
    document.getElementById("sellsCount").textContent = data.sells;

    // Session Info
    document.getElementById("firstTrade").textContent =
      data.first_trade || "--:--";
    document.getElementById("lastTrade").textContent =
      data.last_trade || "--:--";
    document.getElementById("avgPnl").textContent = formatCurrency(
      data.avg_pnl
    );

    // Last Update
    document.getElementById(
      "lastUpdate"
    ).textContent = `Last update: ${data.last_update}`;
  } catch (error) {
    console.error("Error updating summary:", error);
  }
}

// Update positions table
async function updatePositions() {
  try {
    const response = await fetch("/api/positions");
    const positions = await response.json();

    const tbody = document.getElementById("positionsTable");

    if (positions.length === 0) {
      tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-muted py-4">
                        <i class="bi bi-inbox fs-2 d-block mb-2"></i>
                        No open positions
                    </td>
                </tr>
            `;
      return;
    }

    tbody.innerHTML = positions
      .map((pos) => {
        const pnlClass =
          pos.unrealized_pnl > 0
            ? "pnl-positive"
            : pos.unrealized_pnl < 0
            ? "pnl-negative"
            : "pnl-neutral";

        return `
                <tr>
                    <td><span class="ticker-badge">${pos.ticker}</span></td>
                    <td class="text-end">${pos.quantity.toFixed(4)}</td>
                    <td class="text-end">$${pos.entry_price.toFixed(2)}</td>
                    <td class="text-end">$${pos.current_price.toFixed(2)}</td>
                    <td class="text-end ${pnlClass}">${formatCurrency(
          pos.unrealized_pnl
        )}</td>
                    <td class="text-end ${pnlClass}">${formatPercent(
          pos.unrealized_pnl_pct
        )}</td>
                    <td>${pos.hold_time}</td>
                </tr>
            `;
      })
      .join("");
  } catch (error) {
    console.error("Error updating positions:", error);
  }
}

// Update trades table
async function updateTrades() {
  try {
    const response = await fetch("/api/trades");
    const trades = await response.json();

    const tbody = document.getElementById("tradesTable");
    document.getElementById(
      "tradeCount"
    ).textContent = `${trades.length} trades`;

    if (trades.length === 0) {
      tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center text-muted py-4">
                        <i class="bi bi-inbox fs-2 d-block mb-2"></i>
                        No trades yet today
                    </td>
                </tr>
            `;
      return;
    }

    tbody.innerHTML = trades
      .map((trade) => {
        const actionClass =
          trade.action === "BUY" ? "action-buy" : "action-sell";
        const pnlClass =
          trade.action === "SELL"
            ? trade.pnl > 0
              ? "pnl-positive"
              : trade.pnl < 0
              ? "pnl-negative"
              : "pnl-neutral"
            : "";

        const pnlDisplay =
          trade.action === "SELL" ? formatCurrency(trade.pnl) : "—";
        const pctDisplay =
          trade.action === "SELL" ? formatPercent(trade.pnl_pct) : "—";

        return `
                <tr>
                    <td>${trade.time}</td>
                    <td><span class="ticker-badge">${trade.ticker}</span></td>
                    <td><span class="${actionClass}">${trade.action}</span></td>
                    <td class="text-end">${trade.shares.toFixed(4)}</td>
                    <td class="text-end">$${trade.price.toFixed(2)}</td>
                    <td class="text-end ${pnlClass}">${pnlDisplay}</td>
                    <td class="text-end ${pnlClass}">${pctDisplay}</td>
                    <td><small class="text-muted">${trade.notes}</small></td>
                </tr>
            `;
      })
      .join("");
  } catch (error) {
    console.error("Error updating trades:", error);
  }
}

// Update bot status
async function updateBotStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();

    const indicator = document.querySelector(".status-indicator");
    const statusText = document.querySelector(".status-text");

    // Remove all status classes
    indicator.classList.remove(
      "status-live",
      "status-idle",
      "status-error",
      "status-loading"
    );

    if (status.is_running) {
      indicator.classList.add("status-live");
      statusText.textContent = "LIVE";
      statusText.style.color = "var(--success-color)";
    } else {
      indicator.classList.add("status-idle");
      statusText.textContent = "IDLE";
      statusText.style.color = "var(--warning-color)";
    }
  } catch (error) {
    console.error("Error updating bot status:", error);
    const indicator = document.querySelector(".status-indicator");
    const statusText = document.querySelector(".status-text");
    indicator.classList.remove("status-live", "status-idle", "status-loading");
    indicator.classList.add("status-error");
    statusText.textContent = "ERROR";
    statusText.style.color = "var(--danger-color)";
  }
}

// Update live stock ticker
async function updateLiveTicker() {
  try {
    const response = await fetch("/api/live-prices");
    const prices = await response.json();

    if (prices.length === 0) return;

    const tickerContent = document.getElementById("tickerContent");

    // Create ticker items (duplicate for seamless loop)
    const tickerItems = prices
      .map((stock) => {
        const changeClass =
          stock.change_pct > 0
            ? "positive"
            : stock.change_pct < 0
            ? "negative"
            : "neutral";
        const changeSign = stock.change_pct > 0 ? "+" : "";

        return `
                <div class="ticker-item">
                    <span class="ticker-symbol">${stock.ticker}</span>
                    <span class="ticker-price">$${stock.price.toFixed(2)}</span>
                    <span class="ticker-change ${changeClass}">
                        ${changeSign}${stock.change_pct.toFixed(2)}%
                    </span>
                </div>
            `;
      })
      .join("");

    // Duplicate content for seamless scrolling
    tickerContent.innerHTML = tickerItems + tickerItems;
  } catch (error) {
    console.error("Error updating live ticker:", error);
  }
}

// Refresh all data
async function refreshDashboard() {
  await Promise.all([
    updateSummary(),
    updatePositions(),
    updateTrades(),
    updateBotStatus(),
    updateLiveTicker(),
  ]);
}

// Start auto-refresh
function startAutoRefresh() {
  refreshDashboard(); // Initial load
  refreshTimer = setInterval(refreshDashboard, REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
}

// Initialize when page loads
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 Trading Dashboard initialized");
  console.log(`🔄 Auto-refresh: every ${REFRESH_INTERVAL / 1000} seconds`);
  startAutoRefresh();
});

// Stop refresh when page unloads
window.addEventListener("beforeunload", stopAutoRefresh);
