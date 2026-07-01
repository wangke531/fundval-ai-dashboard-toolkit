(function () {
  const ID = "local-pnl-summary-card";
  const ACCOUNT_NAME = "Alipay Fund";
  const REFRESH_MS = 60000;

  function authHeaders() {
    const token = localStorage.getItem("access_token") || "local-auto-login";
    return {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    };
  }

  function currentPositionPage() {
    return location.pathname === "/dashboard/positions";
  }

  function toRows(data) {
    if (Array.isArray(data)) return data;
    if (!data || typeof data !== "object") return [];
    return data.results || data.value || data.items || [];
  }

  function numberValue(value) {
    if (value === null || value === undefined || value === "") return NaN;
    return Number(String(value).replace(/,/g, ""));
  }

  function money(value, signed) {
    const number = numberValue(value);
    if (!Number.isFinite(number)) return "--";
    const text = number.toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return signed && number > 0 ? "+" + text : text;
  }

  function classFor(value) {
    const number = numberValue(value);
    if (!Number.isFinite(number) || Math.abs(number) < 0.005) return "neutral";
    return number > 0 ? "positive" : "negative";
  }

  function formatDate(value) {
    return value || "--";
  }

  function formatDateTime(value) {
    if (!value) return "--";
    const time = new Date(value);
    if (Number.isNaN(time.getTime())) return value;
    return time.toLocaleString("zh-CN", { hour12: false });
  }

  function navDateSummary(counts) {
    if (!counts || typeof counts !== "object") return "--";
    return Object.keys(counts)
      .sort((a, b) => counts[b] - counts[a])
      .map((key) => key + " " + counts[key])
      .join(" / ") || "--";
  }

  function sourceSummary(counts, fallbackCount) {
    const text = counts && typeof counts === "object"
      ? Object.keys(counts).map((key) => key + " " + counts[key]).join(" / ")
      : "";
    return (text || "--") + (fallbackCount ? " / 兜底 " + fallbackCount : "");
  }

  async function getJson(url) {
    const response = await fetch(url, { headers: authHeaders() });
    if (!response.ok) throw new Error(url + " HTTP " + response.status);
    return response.json();
  }

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(url + " HTTP " + response.status);
    return response.json();
  }

  function ensureStyles() {
    if (document.getElementById("local-pnl-summary-style")) return;
    const style = document.createElement("style");
    style.id = "local-pnl-summary-style";
    style.textContent = `
      #${ID} {
        --pnl-bg: #ffffff;
        --pnl-panel: #fafafa;
        --pnl-border: #e8e8e8;
        --pnl-text: #1a1a1a;
        --pnl-muted: #8c8c8c;
        --pnl-subtle: #595959;
        --pnl-positive: #cf1322;
        --pnl-negative: #389e0d;
        --pnl-shadow: 0 1px 8px rgba(0,0,0,.08);
        margin: 0 0 16px;
        padding: 16px;
        border: 1px solid var(--pnl-border);
        border-radius: 14px;
        background: var(--pnl-bg);
        box-shadow: var(--pnl-shadow);
        color: var(--pnl-text);
        font-family: inherit;
      }
      #${ID}.dark-mode {
        --pnl-bg: #141414;
        --pnl-panel: #1f1f1f;
        --pnl-border: #303030;
        --pnl-text: rgba(255,255,255,.88);
        --pnl-muted: rgba(255,255,255,.56);
        --pnl-subtle: rgba(255,255,255,.68);
        --pnl-positive: #ff7875;
        --pnl-negative: #73d13d;
        --pnl-shadow: 0 8px 28px rgba(0,0,0,.35);
      }
      #${ID} .pnl-head {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        justify-content: space-between;
        margin-bottom: 12px;
      }
      #${ID} .pnl-title {
        font-size: 16px;
        font-weight: 700;
        color: var(--pnl-text);
      }
      #${ID} .pnl-note {
        color: var(--pnl-muted);
        font-size: 12px;
        line-height: 1.7;
      }
      #${ID} .pnl-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }
      #${ID} .pnl-metric {
        border: 1px solid var(--pnl-border);
        border-radius: 12px;
        background: var(--pnl-panel);
        padding: 12px;
        min-height: 96px;
      }
      #${ID} .pnl-label {
        display: block;
        color: var(--pnl-muted);
        font-size: 12px;
        margin-bottom: 8px;
      }
      #${ID} .pnl-value {
        display: block;
        font-size: 24px;
        line-height: 1.1;
        font-weight: 800;
        font-family: "DIN Alternate", "Bahnschrift", monospace;
        color: var(--pnl-text);
      }
      #${ID} .pnl-sub {
        display: block;
        color: var(--pnl-muted);
        font-size: 12px;
        margin-top: 8px;
        line-height: 1.45;
      }
      #${ID} .pnl-detail {
        display: grid;
        grid-template-columns: 1.35fr 1fr;
        gap: 10px;
        margin-top: 10px;
      }
      #${ID} .pnl-panel {
        border: 1px solid var(--pnl-border);
        border-radius: 12px;
        background: var(--pnl-panel);
        padding: 10px 12px;
      }
      #${ID} .pnl-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        color: var(--pnl-subtle);
        font-size: 12px;
        line-height: 1.9;
      }
      #${ID} .pnl-row strong {
        color: var(--pnl-text);
        font-weight: 600;
      }
      #${ID} .positive { color: var(--pnl-positive); }
      #${ID} .negative { color: var(--pnl-negative); }
      #${ID} .neutral { color: var(--pnl-text); }
      .local-hide-today-pnl-metric {
        display: none !important;
      }
      .local-yesterday-pnl-metric {
        min-width: 220px;
      }
      .local-yesterday-pnl-label {
        color: #8c8c8c;
        font-size: 14px;
        margin-bottom: 8px;
      }
      .local-yesterday-pnl-value {
        font-size: 24px;
        line-height: 1.1;
        font-weight: 500;
      }
      .local-yesterday-pnl-sub {
        color: #8c8c8c;
        font-size: 12px;
        margin-top: 8px;
      }
      .local-yesterday-pnl-metric .positive { color: #cf1322; }
      .local-yesterday-pnl-metric .negative { color: #52c41a; }
      .local-yesterday-pnl-metric .neutral { color: #1a1a1a; }
      @media (max-width: 1100px) {
        #${ID} .pnl-grid { grid-template-columns: 1fr 1fr; }
        #${ID} .pnl-detail { grid-template-columns: 1fr; }
      }
      @media (max-width: 560px) {
        #${ID} .pnl-grid { grid-template-columns: 1fr; }
        #${ID} .pnl-head { display: block; }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureCard() {
    ensureStyles();
    let card = document.getElementById(ID);
    if (!card) {
      card = document.createElement("section");
      card.id = ID;
    }
    const content = document.querySelector(".ant-layout-content") || document.querySelector("main") || document.getElementById("root");
    const firstNativeCard = content ? Array.from(content.querySelectorAll(".ant-card")).find((node) => !node.closest("#" + ID)) : null;
    if (firstNativeCard && firstNativeCard.parentElement) {
      firstNativeCard.parentElement.insertBefore(card, firstNativeCard);
    } else if (content && content.firstChild !== card) {
      content.insertBefore(card, content.firstChild || null);
    } else if (!content && document.body.firstChild !== card) {
      document.body.insertBefore(card, document.body.firstChild || null);
    }
    return card;
  }

  function removeCard() {
    const card = document.getElementById(ID);
    if (card) card.remove();
  }

  function getYesterdayPnl(summary) {
    const rows = Array.isArray(summary.pnl_series) ? summary.pnl_series : [];
    const today = String((summary.daily_pnl && summary.daily_pnl.date) || (summary.today_live && summary.today_live.date) || "");
    const candidates = rows
      .filter((row) => row && row.daily_profit !== null && row.daily_profit !== undefined && row.daily_profit !== "")
      .filter((row) => !today || String(row.date || "") < today)
      .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
    if (candidates.length) return candidates[0];
    return null;
  }

  function renderYesterdayPnlMetric(summary) {
    if (!currentPositionPage()) return;
    const row = getYesterdayPnl(summary);
    const labels = Array.from(document.querySelectorAll("span, div"))
      .filter((node) => {
        if (node.closest("#" + ID)) return false;
        const text = (node.textContent || "").replace(/\s+/g, "");
        return text === "今日盈亏(预估)" || text === "今日盈亏预估";
      });
    for (const label of labels) {
      let target = label.parentElement;
      let best = null;
      for (let depth = 0; target && depth < 4; depth += 1) {
        const text = (target.textContent || "").replace(/\s+/g, "");
        const rect = target.getBoundingClientRect();
        if (text.includes("今日盈亏") && text.length < 120 && rect.width < 560 && rect.height < 220) best = target;
        if (rect.width > 760 || text.length > 180) break;
        target = target.parentElement;
      }
      if (!best || best === document.body) continue;
      best.classList.remove("local-hide-today-pnl-metric");
      best.classList.add("local-yesterday-pnl-metric");
      if (row) {
        best.innerHTML = `
          <div class="local-yesterday-pnl-label">昨日盈亏</div>
          <div class="local-yesterday-pnl-value ${classFor(row.daily_profit)}">${money(row.daily_profit, true)}</div>
          <div class="local-yesterday-pnl-sub">${formatDate(row.date)} 养基宝口径</div>
        `;
      } else {
        best.innerHTML = `
          <div class="local-yesterday-pnl-label">昨日盈亏</div>
          <div class="local-yesterday-pnl-value neutral">--</div>
          <div class="local-yesterday-pnl-sub">暂无已归档记录</div>
        `;
      }
    }
  }

  function hideNativeTodayPnlMetric() {
    if (!currentPositionPage()) return;
    const labels = Array.from(document.querySelectorAll("span, div"))
      .filter((node) => {
        if (node.closest("#" + ID)) return false;
        const text = (node.textContent || "").replace(/\s+/g, "");
        return text === "今日盈亏(预估)" || text === "今日盈亏预估";
      });
    for (const label of labels) {
      let target = label.parentElement;
      let best = null;
      for (let depth = 0; target && depth < 4; depth += 1) {
        const text = (target.textContent || "").replace(/\s+/g, "");
        const rect = target.getBoundingClientRect();
        if (text.includes("今日盈亏") && text.length < 80 && rect.width < 520 && rect.height < 180) {
          best = target;
        }
        if (rect.width > 700 || text.length > 140) break;
        target = target.parentElement;
      }
      if (best && best !== document.body) {
        best.classList.add("local-hide-today-pnl-metric");
      }
    }
  }

  async function refreshYangjibaoEstimates() {
    const positionsData = await getJson("/api/positions/");
    const positions = toRows(positionsData).filter((position) => position.account_name === ACCOUNT_NAME);
    const fundCodes = [...new Set(positions.map((position) => position.fund_code).filter(Boolean))];
    if (!fundCodes.length) return;
    await postJson("/api/funds/batch_estimate/", {
      fund_codes: fundCodes,
      source: "yangjibao",
    });
  }

  function pnlSeriesRows(summary) {
    const rows = Array.isArray(summary.pnl_series)
      ? summary.pnl_series.filter((row) => row && row.daily_profit !== null && row.daily_profit !== undefined && row.daily_profit !== "").slice().reverse()
      : [];
    if (!rows.length) {
      return '<div class="pnl-row"><span>暂无养基宝收益历史</span><strong>--</strong></div>';
    }
    return rows.slice(0, 3).map((row) => `
      <div class="pnl-row">
        <span>${formatDate(row.date)} ${row.label || ""}</span>
        <strong class="${classFor(row.daily_profit)}">${money(row.daily_profit, true)}</strong>
      </div>
    `).join("");
  }

  function topRows(summary) {
    const positions = Array.isArray(summary.positions) ? summary.positions : [];
    return positions.slice(0, 4).map((position) => `
      <div class="pnl-row">
        <span>${position.fund_name || position.fund_code}</span>
        <strong class="${classFor(position.estimated_delta_since_snapshot)}">${money(position.estimated_delta_since_snapshot, true)}</strong>
      </div>
    `).join("");
  }

  function render(summary) {
    const card = ensureCard();
    const alipay = summary.latest_alipay_snapshot || {};
    const today = summary.today_live || {};
    const daily = summary.daily_pnl || {};
    const portfolio = summary.current_portfolio || {};
    const quality = summary.quality || {};
    const dailyProfit = daily.daily_profit || today.estimated_profit;
    const stageLabel = daily.stage_label || today.label || "--";

    card.innerHTML = `
      <div class="pnl-head">
        <div>
          <div class="pnl-title">收益日历口径</div>
          <div class="pnl-note">支付宝截图只同步持仓；左侧显示养基宝/FundVal 按当前持仓估算的今日收益。</div>
        </div>
        <div class="pnl-note">刷新：${formatDateTime(summary.generated_at)}</div>
      </div>
      <div class="pnl-grid">
        <div class="pnl-metric">
          <span class="pnl-label">${formatDate(daily.date || today.date)} 今日收益估算</span>
          <span class="pnl-value ${classFor(dailyProfit)}">${money(dailyProfit, true)}</span>
          <span class="pnl-sub">${stageLabel}；23:59 归档为当日收益</span>
        </div>
        <div class="pnl-metric">
          <span class="pnl-label">持仓快照</span>
          <span class="pnl-value neutral">${formatDate(alipay.snapshot_date)}</span>
          <span class="pnl-sub">只同步持仓/成本/份额，不读取支付宝收益</span>
        </div>
        <div class="pnl-metric">
          <span class="pnl-label">当前持仓</span>
          <span class="pnl-value ${classFor(portfolio.holding_profit)}">${money(portfolio.holding_profit, true)}</span>
          <span class="pnl-sub">估值后收益 ${money(portfolio.estimate_total_profit, true)} / 市值 ${money(portfolio.holding_value)}</span>
        </div>
      </div>
      <div class="pnl-detail">
        <div class="pnl-panel">
          <div class="pnl-row"><span>市场阶段</span><strong>${stageLabel}</strong></div>
          <div class="pnl-row"><span>净值日期</span><strong>${navDateSummary(quality.nav_date_counts)}</strong></div>
          <div class="pnl-row"><span>估值源</span><strong>${sourceSummary(quality.estimate_source_counts, quality.fallback_count)}</strong></div>
        </div>
        <div class="pnl-panel">
          <div class="pnl-row"><span>收益变化记录</span><strong>养基宝口径</strong></div>
          ${pnlSeriesRows(summary)}
        </div>
      </div>
      <div class="pnl-detail">
        <div class="pnl-panel">
          <div class="pnl-row"><span>图表说明</span><strong>原生趋势不是每日收益</strong></div>
          <div class="pnl-row"><span>支付宝收益数字</span><strong>不参与计算</strong></div>
          <div class="pnl-row"><span>下方汇总空位</span><strong>显示昨日盈亏</strong></div>
        </div>
        <div class="pnl-panel">
          <div class="pnl-row"><span>主要贡献/拖累</span><strong>相对持仓快照</strong></div>
          ${topRows(summary) || '<div class="pnl-row"><span>暂无持仓明细</span><strong>--</strong></div>'}
        </div>
      </div>
    `;
    syncDarkMode();
    renderYesterdayPnlMetric(summary);
  }

  async function refreshSummary() {
    if (!currentPositionPage()) {
      removeCard();
      return;
    }
    try {
      await refreshYangjibaoEstimates();
      const summary = await getJson("/api/local/pnl-summary/");
      render(summary);
      renderYesterdayPnlMetric(summary);
    } catch (error) {
      const card = ensureCard();
      card.innerHTML = '<div class="pnl-note">收益日历口径读取失败：' + String(error) + '</div>';
    }
  }

  function getBgBrightness(el) {
    const bg = window.getComputedStyle(el).backgroundColor;
    const match = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (!match) return -1;
    const alpha = match[4] !== undefined ? parseFloat(match[4]) : 1;
    if (alpha < 0.1) return -1;
    return parseInt(match[1], 10) * 0.299 + parseInt(match[2], 10) * 0.587 + parseInt(match[3], 10) * 0.114;
  }

  function isDarkMode() {
    const classText = String(document.documentElement.className || "") + " " + String(document.body.className || "");
    if (classText.toLowerCase().includes("dark")) return true;
    const dataTheme = document.documentElement.getAttribute("data-theme") || document.body.getAttribute("data-theme");
    if (String(dataTheme).toLowerCase() === "dark") return true;
    const targets = [document.querySelector(".ant-layout"), document.querySelector(".ant-layout-content"), document.body].filter(Boolean);
    return targets.some((target) => {
      const value = getBgBrightness(target);
      return value >= 0 && value < 120;
    });
  }

  function syncDarkMode() {
    const card = document.getElementById(ID);
    if (!card) return;
    card.classList.toggle("dark-mode", isDarkMode());
  }

  function setupObservers() {
    let pending = false;
    const schedule = () => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        syncDarkMode();
        hideNativeTodayPnlMetric();
        pending = false;
      });
    };
    new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "style", "data-theme"] });
  }

  function start() {
    setupObservers();
    refreshSummary();
    setInterval(refreshSummary, REFRESH_MS);
  }

  window.addEventListener("load", start);
  window.addEventListener("popstate", refreshSummary);
  const originalPushState = history.pushState;
  history.pushState = function () {
    originalPushState.apply(this, arguments);
    setTimeout(refreshSummary, 100);
  };
})();
