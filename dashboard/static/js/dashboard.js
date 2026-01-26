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
      data.total_pnl,
    );
    document.getElementById("unrealizedPnl").textContent = formatCurrency(
      data.unrealized_pnl,
    );

    // Win Rate
    const winRateEl = document.getElementById("winRate");
    winRateEl.textContent = `${data.win_rate}%`;
    animateValue(winRateEl);

    document.getElementById("wins").textContent = data.wins;
    document.getElementById("sells").textContent = data.sells;

    // Trade quality extras
    const pfEl = document.getElementById("profitFactor");
    if (pfEl)
      pfEl.textContent = data.profit_factor == null ? "—" : data.profit_factor;

    const avgWinEl = document.getElementById("avgWin");
    if (avgWinEl) avgWinEl.textContent = formatCurrency(data.avg_win || 0);

    const avgLossEl = document.getElementById("avgLoss");
    if (avgLossEl) avgLossEl.textContent = formatCurrency(data.avg_loss || 0);

    // Current Equity
    const equityEl = document.getElementById("currentEquity");
    equityEl.textContent = formatCurrency(data.current_equity);
    animateValue(equityEl);

    const cashEl = document.getElementById("cashValue");
    if (cashEl) cashEl.textContent = formatCurrency(data.cash_value || 0);

    const investedEl = document.getElementById("investedValue");
    if (investedEl)
      investedEl.textContent = formatCurrency(data.invested_value || 0);

    const exposureEl = document.getElementById("exposurePct");
    if (exposureEl) exposureEl.textContent = `${data.exposure_pct || 0}%`;

    document.getElementById("openPositions").textContent = data.open_positions;

    // Equity source / mode label
    const equitySourceEl = document.getElementById("equitySource");
    if (equitySourceEl) {
      const src = data.equity_source || data.source || "—";
      const mode = data.trading_mode ? ` • ${data.trading_mode}` : "";
      equitySourceEl.textContent = `Source: ${src}${mode}`;
    }

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

    const lastTradeTimeEl = document.getElementById("lastTradeTime");
    if (lastTradeTimeEl)
      lastTradeTimeEl.textContent = data.last_trade || "--:--";
    document.getElementById("avgPnl").textContent = formatCurrency(
      data.avg_pnl,
    );

    // Last Update
    document.getElementById("lastUpdate").textContent =
      `Last update: ${data.last_update}`;
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
                      pos.unrealized_pnl,
                    )}</td>
                    <td class="text-end ${pnlClass}">${formatPercent(
                      pos.unrealized_pnl_pct,
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
    document.getElementById("tradeCount").textContent =
      `${trades.length} trades`;

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

    // Data feed / quote freshness banner
    const feedRow = document.getElementById("feedAlertRow");
    const feedEl = document.getElementById("feedAlert");
    if (feedRow && feedEl) {
      const feedOk = status.data_feed_ok;
      const reason = status.data_feed_reason;
      if (feedOk === false) {
        const details = reason ? ` — ${reason}` : "";
        feedEl.textContent = `Trading paused: quotes not fresh${details}`;
        feedRow.style.display = "";
      } else {
        feedRow.style.display = "none";
      }
    }

    const indicator = document.querySelector(".status-indicator");
    const statusText = document.querySelector(".status-text");

    // Remove all status classes
    indicator.classList.remove(
      "status-live",
      "status-idle",
      "status-error",
      "status-loading",
    );

    const effectiveStatus =
      status.status || (status.is_running ? "LIVE" : "IDLE");

    if (effectiveStatus === "LIVE") {
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
    const payload = await response.json();
    const prices = Array.isArray(payload) ? payload : payload.prices || [];
    const source = Array.isArray(payload) ? "db" : payload.source || "unknown";

    const sourceEl = document.getElementById("priceSource");
    if (sourceEl) {
      sourceEl.classList.remove("is-live", "is-degraded", "is-error");
      if (source === "redis") {
        sourceEl.textContent = "redis";
        sourceEl.classList.add("is-live");
      } else if (source === "db") {
        sourceEl.textContent = "db";
        sourceEl.classList.add("is-degraded");
      } else if (source === "error") {
        sourceEl.textContent = "error";
        sourceEl.classList.add("is-error");
      } else {
        sourceEl.textContent = source;
      }
    }

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

// Update dip suggestions panel
async function updateDipSuggestions() {
  try {
    const response = await fetch("/api/dip-suggestions");
    const payload = await response.json();

    const cardEl = document.getElementById("dipSuggestionsCard");
    const listEl = document.getElementById("dipSuggestionsList");
    const updatedEl = document.getElementById("dipSuggestionsUpdated");
    const noteEl = document.getElementById("dipSuggestionsNote");
    if (!listEl) return;

    const enabled = payload.enabled === true;
    const items = payload.items || [];

    // User preference: show nothing when market closed or no live data.
    if (!enabled || items.length === 0) {
      if (cardEl) cardEl.style.display = "none";
      return;
    }

    if (cardEl) cardEl.style.display = "";
    if (updatedEl) updatedEl.textContent = payload.generated_at || "--:--";
    if (noteEl)
      noteEl.textContent =
        payload.notes ||
        "Heuristic signals from live prices; informational only.";

    const badgeClass = (priority) => {
      if (priority === "URGENT") return "bg-danger";
      if (priority === "HIGH") return "bg-warning text-dark";
      if (priority === "MEDIUM") return "bg-primary";
      return "bg-secondary";
    };

    listEl.innerHTML = items
      .map((s) => {
        const reasons = (s.reasons || []).slice(0, 3).join(" • ");
        return `
          <div class="dip-suggestion-item">
            <div class="d-flex justify-content-between align-items-center mb-1">
              <div class="d-flex align-items-center gap-2">
                <span class="ticker-badge">${s.ticker}</span>
                <span class="badge ${badgeClass(s.priority)}">${s.priority}</span>
              </div>
              <div class="text-end">
                <div class="dip-suggestion-price">$${Number(s.price).toFixed(2)}</div>
                <div class="dip-suggestion-score text-muted">Score ${Number(s.score).toFixed(1)}</div>
              </div>
            </div>
            <div class="dip-suggestion-reasons text-muted">${reasons}</div>
          </div>
        `;
      })
      .join("");
  } catch (error) {
    console.error("Error updating dip suggestions:", error);
  }
}

// Update critical monitoring panel
async function updateCriticalMonitor() {
  try {
    const response = await fetch("/api/critical-monitor");
    const payload = await response.json();

    const cardEl = document.getElementById("criticalMonitorCard");
    const updatedEl = document.getElementById("criticalMonitorUpdated");
    const noteEl = document.getElementById("criticalMonitorNote");
    const overallEl = document.getElementById("criticalMonitorOverall");
    const indEl = document.getElementById("criticalMonitorIndicators");
    const alertsEl = document.getElementById("criticalMonitorAlerts");
    if (!cardEl || !indEl || !alertsEl) return;

    if (updatedEl) updatedEl.textContent = payload.generated_at || "--:--";
    if (noteEl) noteEl.textContent = payload.notes || "";

    const overall = (payload.overall || "unknown").toString().toUpperCase();
    if (overallEl) {
      overallEl.textContent = overall;
      overallEl.className = "badge";
      if (overall === "CRITICAL") overallEl.classList.add("bg-danger");
      else if (overall === "WARNING")
        overallEl.classList.add("bg-warning", "text-dark");
      else if (overall === "OK") overallEl.classList.add("bg-success");
      else overallEl.classList.add("bg-secondary");
    }

    const indicators = payload.indicators || [];
    indEl.innerHTML = indicators
      .map((i) => {
        const st = (i.status || "unknown").toString().toUpperCase();
        const badge =
          st === "CRITICAL"
            ? "bg-danger"
            : st === "WARNING"
              ? "bg-warning text-dark"
              : st === "OK"
                ? "bg-success"
                : "bg-secondary";

        const val =
          i.value == null
            ? "—"
            : i.unit === "USD/bbl"
              ? `$${Number(i.value).toFixed(2)}`
              : Number(i.value).toFixed(2);

        const hint = i.guidance
          ? `<div class="text-muted small">${i.guidance}</div>`
          : "";

        return `
          <div class="critical-indicator-item">
            <div class="d-flex justify-content-between align-items-center">
              <div class="fw-semibold">${i.name}</div>
              <div class="d-flex align-items-center gap-2">
                <div class="critical-indicator-value">${val}</div>
                <span class="badge ${badge}">${st}</span>
              </div>
            </div>
            ${hint}
          </div>
        `;
      })
      .join("");

    const alerts = payload.alerts || [];
    if (alerts.length === 0) {
      alertsEl.innerHTML = `<div class="text-muted small">No external critical alerts.</div>`;
    } else {
      const escapeHtml = (s) =>
        String(s ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");

      alertsEl.innerHTML = alerts
        .map((a) => {
          const sev = (a.severity || "info").toString().toUpperCase();
          const badge =
            sev === "CRITICAL"
              ? "bg-danger"
              : sev === "WARNING"
                ? "bg-warning text-dark"
                : "bg-secondary";
          const ts = a.ts ? `<span class="text-muted">${a.ts}</span>` : "";
          const titleText = escapeHtml(a.title || "Alert");
          const url = (a.url || "").toString();
          const titleHtml = url
            ? `<a class="fw-semibold" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${titleText}</a>`
            : `<span class="fw-semibold">${titleText}</span>`;

          const matched = Array.isArray(a.matched) ? a.matched.slice(0, 6) : [];
          const matchedHtml = matched.length
            ? `<span class="d-inline-flex flex-wrap gap-1 ms-2">${matched
                .map(
                  (t) =>
                    `<span class="badge bg-light text-dark border">${escapeHtml(t)}</span>`,
                )
                .join("")}</span>`
            : "";
          return `
            <div class="critical-alert-item">
              <div class="d-flex justify-content-between align-items-center">
                <div class="d-flex align-items-center gap-2">
                  <span class="badge ${badge}">${sev}</span>
                  ${titleHtml}${matchedHtml}
                </div>
                ${ts}
              </div>
              <div class="text-muted">${escapeHtml(a.message || "")}</div>
            </div>
          `;
        })
        .join("");
    }
  } catch (error) {
    console.error("Error updating critical monitor:", error);
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
    updateDipSuggestions(),
    updateCriticalMonitor(),
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
