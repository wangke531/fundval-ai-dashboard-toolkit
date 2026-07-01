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
        margin: 0 0 16px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 14px;
        background:
          linear-gradient(135deg, rgba(38,43,38,.96), rgba(28,35,31,.96)),
          radial-gradient(circle at 10% 0%, rgba(213,74,64,.18), transparent 34%);
        box-shadow: 0 8px 28px rgba(0,0,0,.22);
        color: rgba(255,255,255,.86);
        font-family: inherit;
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
      }
      #${ID} .pnl-note {
        color: rgba(255,255,255,.56);
        font-size: 12px;
        line-height: 1.7;
      }
      #${ID} .pnl-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
      }
      #${ID} .pnl-metric {
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 12px;
        background: rgba(255,255,255,.055);
        padding: 12px;
        min-height: 96px;
      }
      #${ID} .pnl-label {
        display: block;
        color: rgba(255,255,255,.56);
        font-size: 12px;
        margin-bottom: 8px;
      }
      #${ID} .pnl-value {
        display: block;
        font-size: 24px;
        line-height: 1.1;
        font-weight: 800;
        font-family: "DIN Alternate", "Bahnschrift", monospace;
      }
      #${ID} .pnl-sub {
        display: block;
        color: rgba(255,255,255,.50);
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
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 12px;
        background: rgba(0,0,0,.12);
        padding: 10px 12px;
      }
      #${ID} .pnl-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        color: rgba(255,255,255,.64);
        font-size: 12px;
        line-height: 1.9;
      }
      #${ID} .pnl-row strong {
        color: rgba(255,255,255,.84);
        font-weight: 600;
      }
      #${ID} .positive { color: #ff7b72; }
      #${ID} .negative { color: #5fd3a5; }
      #${ID} .neutral { color: rgba(255,255,255,.84); }
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
    if (card) return card;

    card = document.createElement("section");
    card.id = ID;
    card.innerHTML = '<div class="pnl-note">收益日历口径加载中...</div>';

    const root = document.querySelector(".ant-layout-content") || document.querySelector("main") || document.getElementById("root");
    if (root && root.firstChild) {
      root.insertBefore(card, root.firstChild);
    } else {
      document.body.insertBefore(card, document.body.firstChild);
    }
    return card;
  }

  function currentPositionPage() {
    return location.pathname === "/dashboard/positions";
  }

  function removeCard() {
    const card = document.getElementById(ID);
    if (card) card.remove();
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

  function topRows(summary) {
    const positions = Array.isArray(summary.positions) ? summary.positions : [];
    return positions.slice(0, 4).map((position) => `
      <div class="pnl-row">
        <span>${position.fund_name || position.fund_code}</span>
        <strong class="${classFor(position.estimated_delta_since_snapshot)}">${money(position.estimated_delta_since_snapshot, true)}</strong>
      </div>
    `).join("");
  }

  function pnlSeriesRows(summary) {
    const rows = Array.isArray(summary.pnl_series)
      ? summary.pnl_series.filter((row) => row && row.daily_profit !== null && row.daily_profit !== undefined && row.daily_profit !== "").slice().reverse()
      : [];
    if (!rows.length) {
      return '<div class="pnl-row"><span>暂无养基宝收益历史</span><strong>--</strong></div>';
    }
    return rows.slice(0, 5).map((row) => `
      <div class="pnl-row">
        <span>${formatDate(row.date)} ${row.label || ""}</span>
        <strong class="${classFor(row.daily_profit)}">${money(row.daily_profit, true)}</strong>
      </div>
    `).join("");
  }

  function render(summary) {
    const card = ensureCard();
    const alipay = summary.latest_alipay_snapshot || {};
    const closed = summary.last_closed_trade || summary.last_closed_trade_estimate || {};
    const today = summary.today_live || {};
    const daily = summary.daily_pnl || {};
    const portfolio = summary.current_portfolio || {};
    const market = summary.market_clock || {};
    const quality = summary.quality || {};
    const dailyDate = daily.date || closed.date || today.date;
    const dailyProfit = daily.daily_profit || closed.daily_profit || closed.estimated_profit || today.estimated_profit;
    const stageLabel = daily.stage_label || today.label || "--";
    const settlementLabel = daily.settlement_label || closed.settlement_label || "--";

    card.innerHTML = `
      <div class="pnl-head">
        <div>
          <div class="pnl-title">收益日历口径</div>
          <div class="pnl-note">支付宝截图只同步持仓；收益由当前持仓 + 养基宝估值/净值变化计算，不读取支付宝页面的收益数字。</div>
        </div>
        <div class="pnl-note">刷新：${formatDateTime(summary.generated_at)}</div>
      </div>
      <div class="pnl-grid">
        <div class="pnl-metric">
          <span class="pnl-label">${formatDate(dailyDate)} 当日收益</span>
          <span class="pnl-value ${classFor(dailyProfit)}">${money(dailyProfit, true)}</span>
          <span class="pnl-sub">境内/A股相关 ${money(daily.domestic_delta || today.domestic_delta, true)} / QDII海外参考 ${money(daily.qdii_delta_reference || today.qdii_delta_reference, true)}</span>
        </div>
        <div class="pnl-metric">
          <span class="pnl-label">${formatDate(today.date)} 当前阶段</span>
          <span class="pnl-value neutral">${stageLabel}</span>
          <span class="pnl-sub">${daily.range_label || ""}，${daily.archive_time || "23:59"} 归档为当日收益</span>
        </div>
        <div class="pnl-metric">
          <span class="pnl-label">持仓快照</span>
          <span class="pnl-value neutral">${formatDate(alipay.snapshot_date)}</span>
          <span class="pnl-sub">只用于同步持仓/成本，不用于收益判断</span>
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
          <div class="pnl-row"><span>结算判断</span><strong>${settlementLabel}</strong></div>
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
          <div class="pnl-row"><span>缺历史快照的日期</span><strong>不强行计算</strong></div>
          <div class="pnl-row"><span>每日收益来源</span><strong>收益变化记录</strong></div>
        </div>
        <div class="pnl-panel">
          <div class="pnl-row"><span>主要贡献/拖累</span><strong>相对持仓快照</strong></div>
          ${topRows(summary) || '<div class="pnl-row"><span>暂无持仓明细</span><strong>--</strong></div>'}
        </div>
      </div>
      <div class="pnl-note" style="margin-top:10px">
        规则：按北京时间自然日计算；凌晨美股和白天 A 股都归入当天；00:00-14:59 显示穿透中，15:00-23:59 显示结算中，期间都跟随养基宝实时变化；23:59 归档为当日收益，第二天显示为昨日收益。图 2 的原生收益趋势画的是账户市值/成本，不是我们计算的每日收益；每日收益从本卡片的“收益变化记录”看。
      </div>
    `;
  }

  async function refreshSummary() {
    if (!currentPositionPage()) {
      removeCard();
      return;
    }

    const card = ensureCard();
    try {
      await refreshYangjibaoEstimates();
      const summary = await getJson("/api/local/pnl-summary/");
      render(summary);
    } catch (error) {
      card.innerHTML = '<div class="pnl-note">收益日历口径读取失败：' + String(error) + "</div>";
    }
  }

  function scheduleRefresh() {
    refreshSummary();
    setInterval(refreshSummary, REFRESH_MS);
  }

  window.addEventListener("load", scheduleRefresh);
  window.addEventListener("popstate", refreshSummary);
  const originalPushState = history.pushState;
  history.pushState = function () {
    originalPushState.apply(this, arguments);
    setTimeout(refreshSummary, 100);
  };
})();
